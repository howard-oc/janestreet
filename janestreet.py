"""janestreet.py

Prepare context for a Jane Street–style Japan 225 trade decision.

This script:
- Reads an optional analysis prompt from ``docs/claud.md`` (if present).
- Looks up the Japan 225 market and primary trading account IDs from
  ``data/stonex_meta.duckdb``.
- Pulls recent Japan 225 news headlines via GetMarketReportHeadlines.
- For the latest headlines, fetches full stories via GetStory and stores
  title + summary/body in DuckDB.
- Loads any previous-day Japan 225 stories from DuckDB.
- Fetches open positions and open orders for the primary trading account.
- Pulls recent Japan 225 price history via barhistory.

The combined context is printed as a single JSON document to stdout that can be
used as input to an LLM (for example, with the prompt in ``docs/claud.md``).

Usage (example):

    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... \
      uv run python janestreet.py > janestreet_context.json

"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import requests
import google.genai as genai

from augmenttrade.client import API_BASE, CityIndexClient
from agent.retriever import retrieve_similar_news
from agent.notion_publisher import publish_analysis_to_notion

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "data" / "stonex_meta.duckdb"
PROMPT_PATH = ROOT_DIR / "docs" / "claud.md"


@dataclass
class NewsItem:
    story_id: str
    headline: str
    publish_ts: Optional[datetime]
    summary: str


def _parse_ms_date(raw: Any) -> Optional[datetime]:
    """Parse StoneX /Date(XXXXXXXXXXXX)/ format into a timezone-aware datetime.

    Returns None if parsing fails.
    """

    if not raw or not isinstance(raw, str):
        return None

    try:
        # Expect strings like "/Date(1766578594028)/"
        ms = int(raw.strip("/Date()/"))
        return datetime.fromtimestamp(ms / 1000, tz=UTC)
    except Exception:
        return None


def load_prompt() -> str:
    """Return the contents of docs/claud.md, failing if missing or empty.

    The janestreet context builder expects an explicit analysis prompt. If the
    prompt file is missing or contains only whitespace, we abort with a clear
    error so the user can fix it instead of running with an implicit default.
    """

    try:
        text = PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Prompt file not found: {PROMPT_PATH}", file=sys.stderr)
        raise SystemExit(1)

    if not text.strip():
        print(
            f"Prompt file {PROMPT_PATH} is empty; please add guidance text.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return text


def get_meta_ids() -> tuple[int, int, int]:
    """Return (market_id, trading_account_id, client_account_id) from DuckDB.

    Expects ``markets`` and ``trading_accounts`` tables populated by previous
    setup (see earlier scripts).
    """

    if not DB_PATH.exists():
        print(f"DuckDB metadata file not found at {DB_PATH}", file=sys.stderr)
        raise SystemExit(1)

    con = duckdb.connect(DB_PATH.as_posix(), read_only=True)

    market_row = con.execute(
        "SELECT market_id, name FROM markets WHERE symbol = 'JAPAN225'"
    ).fetchone()
    if not market_row:
        print("No JAPAN225 entry found in markets table", file=sys.stderr)
        raise SystemExit(1)
    market_id, market_name = market_row

    acct_row = con.execute(
        "SELECT trading_account_id, client_account_id "
        "FROM trading_accounts WHERE alias = 'primary_spread_bet'"
    ).fetchone()
    if not acct_row:
        print("No primary_spread_bet entry found in trading_accounts table", file=sys.stderr)
        raise SystemExit(1)
    trading_account_id, client_account_id = acct_row

    print(
        "Meta:",
        f"market_id={market_id} (name={market_name}),",
        f"trading_account_id={trading_account_id},",
        f"client_account_id={client_account_id}",
        file=sys.stderr,
    )

    return int(market_id), int(trading_account_id), int(client_account_id)


def ensure_news_table() -> duckdb.DuckDBPyConnection:
    """Open DuckDB and ensure the Japan 225 news table exists.

    Returns a read/write connection.
    """

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH.as_posix())

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS news_japan225 (
            story_id TEXT PRIMARY KEY,
            publish_ts TIMESTAMP,
            headline TEXT,
            summary TEXT,
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    return con


def ensure_llm_meta() -> None:
    """Ensure DuckDB has metadata for the Gemini 'japan225' integration.

    Only non-sensitive metadata (no API keys) is stored.
    """

    if not DB_PATH.exists():
        return

    con = duckdb.connect(DB_PATH.as_posix())
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_integrations (
            name TEXT PRIMARY KEY,
            provider TEXT,
            project_id TEXT,
            project_number TEXT
        );
        """
    )
    con.execute(
        """
        INSERT INTO llm_integrations (name, provider, project_id, project_number)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (name) DO UPDATE SET
            provider = excluded.provider,
            project_id = excluded.project_id,
            project_number = excluded.project_number;
        """,
        [
            "japan225",
            "google-gemini",
            "projects/834288299706",
            "834288299706",
        ],
    )
    con.close()


def fetch_headlines(client: CityIndexClient, market_id: int, max_results: int = 30) -> List[Dict[str, Any]]:
    """Call GetMarketReportHeadlines for Japan 225 and return the raw list."""

    headers = {"username": client.username, "session": client.session}
    params = {"marketID": market_id, "cultureId": 69, "maxResults": max_results}
    url = f"{API_BASE}/TradingAPI/news/marketreportheadlines"

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("Headlines", []) or []


def fetch_story(client: CityIndexClient, story_id: str) -> Dict[str, Any]:
    """Call GetStory for a given story ID and return a normalised story dict.

    City Index may respond with different shapes:

    - ``{"Story": {..}, "StoryInHtml": "..."}``
    - ``{"Story": "plain text body", "StoryInHtml": "..."}``
    - a bare string or list of strings.

    This helper always returns a dict with at least a ``Body`` key so
    downstream code can safely read ``story["Body"]``.
    """

    headers = {"username": client.username, "session": client.session}
    url = f"{API_BASE}/TradingAPI/news/story"
    params = {"storyID": story_id}

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()

    # Normalise shape.
    if isinstance(data, dict):
        raw_story = data.get("Story")
        # Nested object with fields like Body, Headline, etc.
        if isinstance(raw_story, dict):
            # Ensure Body exists if content is stored under a different key.
            if "Body" not in raw_story and isinstance(raw_story.get("Story"), str):
                raw_story["Body"] = raw_story.get("Story")
            return raw_story
        # Common case: Story is just a plain-text body string.
        if isinstance(raw_story, str):
            normalised: Dict[str, Any] = {"Body": raw_story, "Story": raw_story}
            # Preserve any other top-level keys (e.g. StoryInHtml).
            for k, v in data.items():
                if k != "Story":
                    normalised[k] = v
            return normalised
        # Dict without a Story key – treat as already-normalised.
        return data

    if isinstance(data, list):
        # Treat list of paragraphs as a single body string.
        body = "\n".join(str(part) for part in data)
        return {"StoryId": story_id, "Body": body}

    # Fallback: wrap scalar.
    return {"StoryId": story_id, "Body": str(data)}


def upsert_news(con: duckdb.DuckDBPyConnection, items: List[NewsItem]) -> None:
    """Insert or update news items in the news_japan225 table."""

    if not items:
        return

    rows = [
        (
            item.story_id,
            item.publish_ts,
            item.headline,
            item.summary,
            "",  # raw_json placeholder (can be extended later)
        )
        for item in items
    ]

    con.executemany(
        """
        INSERT INTO news_japan225 (story_id, publish_ts, headline, summary, raw_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (story_id) DO UPDATE SET
            publish_ts = excluded.publish_ts,
            headline   = excluded.headline,
            summary    = excluded.summary;
        """,
        rows,
    )


def load_yesterdays_news(con: duckdb.DuckDBPyConnection) -> List[NewsItem]:
    """Return news items for the previous UTC calendar day, if any."""

    today = datetime.now(tz=UTC).date()
    yesterday: date = today - timedelta(days=1)

    rows = con.execute(
        """
        SELECT story_id, publish_ts, headline, summary
        FROM news_japan225
        WHERE DATE(publish_ts) = ?
        ORDER BY publish_ts
        """,
        [yesterday],
    ).fetchall()

    items: List[NewsItem] = []
    for story_id, publish_ts, headline, summary in rows:
        items.append(
            NewsItem(
                story_id=str(story_id),
                headline=str(headline or ""),
                publish_ts=publish_ts,
                summary=str(summary or ""),
            )
        )
    return items


def fetch_open_positions(client: CityIndexClient, trading_account_id: int) -> Dict[str, Any]:
    """Use the client wrapper to fetch open positions for the account."""

    return client.list_open_positions(trading_account_id)


def fetch_active_orders(client: CityIndexClient, trading_account_id: int) -> Dict[str, Any]:
    """Fetch active orders for the trading account, if supported.

    Some environments may not expose the ListActiveOrders endpoint or may
    require a different URL, in which case we return a structured error
    payload instead of raising.
    """

    headers = {"username": client.username, "session": client.session}
    url = f"{API_BASE}/TradingAPI/order/activeorders"
    params = {"TradingAccountId": trading_account_id}

    try:
        resp = requests.get(url, headers=headers, params=params)
        if not resp.ok:
            return {
                "error": "activeorders_endpoint_error",
                "status_code": resp.status_code,
                "url": url,
                "body": resp.text,
            }
        return resp.json()
    except Exception as exc:  # pragma: no cover - network
        return {
            "error": "activeorders_request_exception",
            "url": url,
            "exception": str(exc),
        }


def fetch_price_context(client: CityIndexClient, market_id: int) -> Dict[str, Any]:
    """Pull recent daily price bars and derive the latest close for Japan 225."""

    # Use existing helper to fetch daily bars; ignore PartialPriceBar.
    data = client.get_price_bars(
        market_id=market_id,
        interval="DAY",
        span=1,
        price_bars=10,
        price_type=None,
    )

    bars = data.get("PriceBars") or []
    latest_close: Optional[float] = None
    if bars:
        latest_close = float(bars[-1].get("Close"))

    return {
        "price_bars": bars,
        "latest_close": latest_close,
        "partial_price_bar": data.get("PartialPriceBar"),
    }


def run_gemini_analysis(context: Dict[str, Any]) -> str:
    """Run Google Gemini on the janestreet context and return markdown analysis.

    The API key is read from the GOOGLE_GEMINI_API_KEY environment variable.
    If it is not set, this function returns an empty string and logs a warning.
    """

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        print(
            "GOOGLE_GEMINI_API_KEY not set; skipping Gemini analysis.",
            file=sys.stderr,
        )
        return ""

    # google.genai uses a Client-based API rather than a global configure.
    client = genai.Client(api_key=api_key)

    # Use a currently supported Gemini model. Allow override via env so we can
    # switch models without changing code when Google deprecates families.
    model_name = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash")

    # The claud.md file already defines the full analysis framework and the
    # exact response structure we want. Treat that as the primary set of
    # instructions and avoid hard-coding our own headings here.
    framework_prompt = context.get("prompt", "")

    # Compose a single prompt string for the newer client API. Put the
    # framework first so Gemini sees the required response structure before
    # the noisy JSON context.
    full_prompt = "\n".join(
        [
            "You are a senior quantitative trader at Jane Street specialising in Japanese equity index products.",
            "Follow the ANALYSIS FRAMEWORK and RESPONSE STRUCTURE below exactly when writing your answer.",
            "",
            "=== ANALYSIS FRAMEWORK (FROM docs/claud.md) ===",
            framework_prompt,
            "",
            "=== CONTEXT JSON (news, positions, orders, prices, RAG hits) ===",
            json.dumps(context, indent=2, default=str),
            "",
            "Using ONLY the framework's required response structure, write a single markdown analysis.",
        ]
    )

    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
        )
        return (resp.text or "").strip()
    except Exception as exc:
        # Log Gemini failures so callers can see what went wrong.
        print(
            f"Gemini analysis failed: {exc}",
            file=sys.stderr,
        )
        return ""


def collect_news_context(client: CityIndexClient, market_id: int, con: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Fetch latest headlines, upsert news, and return a structured context."""

    headlines = fetch_headlines(client, market_id, max_results=30)

    # Convert to NewsItem + also fetch full stories for a small subset to obtain
    # body text we can use as a summary.
    items: List[NewsItem] = []
    detailed: List[Dict[str, Any]] = []

    for h in headlines:
        story_id = str(h.get("StoryId"))
        headline = str(h.get("Headline") or "")
        publish_ts = _parse_ms_date(h.get("PublishDate"))

        # For now, fetch full story for the first N items to get a body
        # (sufficient for daily analysis).
        # Default summary to the headline so it is never empty.
        summary_text = headline
        if len(detailed) < 10 and story_id:
            try:
                story = fetch_story(client, story_id)
            except Exception as exc:  # pragma: no cover - network
                print(f"Warning: failed to fetch story {story_id}: {exc}", file=sys.stderr)
                story = {}
            body = str(story.get("Body") or "")
            if body:
                # Use the first ~500 characters as a crude summary placeholder.
                summary_text = body[:500]
            detailed.append(story)

        items.append(
            NewsItem(
                story_id=story_id,
                headline=headline,
                publish_ts=publish_ts,
                summary=summary_text,
            )
        )

    upsert_news(con, items)

    yday_items = load_yesterdays_news(con)

    return {
        "latest_headlines": [asdict(i) for i in items],
        "yesterdays_news": [asdict(i) for i in yday_items],
    }


def main() -> None:
    prompt = load_prompt()

    market_id, trading_account_id, client_account_id = get_meta_ids()

    ensure_llm_meta()

    con = ensure_news_table()
    client = CityIndexClient()

    news_ctx = collect_news_context(client, market_id, con)
    open_positions = fetch_open_positions(client, trading_account_id)
    active_orders = fetch_active_orders(client, trading_account_id)
    price_ctx = fetch_price_context(client, market_id)

    # Build a RAG query: prefer the user prompt if present, otherwise use a
    # Japan 225 macro template focusing on BoJ, yen, and liquidity conditions.
    rag_query = (prompt or "").strip()
    if not rag_query:
        rag_query = (
            "Japan 225 index, Nikkei, BoJ policy, yen intervention, "
            "holiday liquidity, nuclear restart, equity risk sentiment"
        )

    try:
        rag_hits = retrieve_similar_news(rag_query, top_k=10)
        rag_top_news = [
            {
                "score": h.score,
                "story_id": h.story_id,
                "publish_ts": h.publish_ts,
                "headline": h.headline,
                "summary": h.summary,
            }
            for h in rag_hits
        ]
    except Exception as exc:  # pragma: no cover - retrieval is best-effort
        rag_top_news = [{
            "error": "retriever_error",
            "message": str(exc),
        }]

    context: Dict[str, Any] = {
        "prompt": prompt,
        "meta": {
            "market_id": market_id,
            "trading_account_id": trading_account_id,
            "client_account_id": client_account_id,
        },
        "news": news_ctx,
        "open_positions": open_positions,
        "active_orders": active_orders,
        "price": price_ctx,
        "rag_top_news": rag_top_news,
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
    }

    # Run Gemini analysis (best-effort)
    analysis_md = run_gemini_analysis(context)
    if not analysis_md:
        print(
            "Gemini returned empty analysis; skipping Notion publishing.",
            file=sys.stderr,
        )
    context["gemini_analysis_markdown"] = analysis_md

    # Optionally publish to Notion if configured
    notion_db_id = os.getenv("NOTION_SECOND_BRAIN_DB_ID")
    if notion_db_id and analysis_md:
        try:
            # Use the generated_at_utc timestamp as the Notion PublishedDate.
            published_ts = context.get("generated_at_utc") or datetime.now(tz=UTC).isoformat()
            page = publish_analysis_to_notion(
                database_id=notion_db_id,
                title="Japan 225  Daily Playbook",
                analysis_markdown=analysis_md,
                tags=["Japan225", "Gemini", "SecondBrain"],
                properties_extra={
                    "PublishedDate": {
                        "date": {"start": published_ts},
                    }
                },
            )
            context["notion_page_id"] = page.get("id")
        except Exception as exc:  # pragma: no cover - external API
            context.setdefault("notion_error", str(exc))

    print(json.dumps(context, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
