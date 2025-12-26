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
- Integrates with Pinecone for vector-based news retrieval.

The combined context is printed as a single JSON document to stdout that can be
used as input to an LLM (for example, with the prompt in ``docs/claud.md``).

Usage (example):

    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... \
      PINECONE_API_KEY=... \
      uv run python janestreet.py > janestreet_context.json

"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import requests
import google.genai as genai

from augmenttrade.client import API_BASE, CityIndexClient
from agent.retriever import retrieve_similar_news
from agent.notion_publisher import publish_analysis_to_notion

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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


def get_meta_ids(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    """Return (market_id, trading_account_id, client_account_id) from DuckDB.

    Expects ``markets`` and ``trading_accounts`` tables populated by previous
    setup (see earlier scripts).
    """

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


def ensure_news_table(con: duckdb.DuckDBPyConnection) -> None:
    """Ensure the Japan 225 news table exists in the provided connection."""

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


def ensure_llm_meta(con: duckdb.DuckDBPyConnection) -> None:
    """Ensure DuckDB has metadata for the Gemini 'japan225' integration.

    Only non-sensitive metadata (no API keys) is stored.
    """

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


def ensure_pinecone_meta(con: duckdb.DuckDBPyConnection) -> None:
    """Ensure DuckDB has metadata for Pinecone vector database integration.

    Stores non-sensitive configuration like index name and environment.
    API key is read from environment variable PINECONE_API_KEY.
    """

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vector_db_integrations (
            name TEXT PRIMARY KEY,
            provider TEXT,
            index_name TEXT,
            environment TEXT,
            dimension INTEGER,
            metric TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        """
    )
    
    con.execute(
        """
        INSERT INTO vector_db_integrations 
            (name, provider, index_name, environment, dimension, metric, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, now(), now())
        ON CONFLICT (name) DO UPDATE SET
            provider = excluded.provider,
            index_name = excluded.index_name,
            environment = excluded.environment,
            dimension = excluded.dimension,
            metric = excluded.metric,
            updated_at = now();
        """,
        [
            "japan225_news",
            "pinecone",
            "japan225-news-vectors",
            os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws"),
            1536,  # Standard OpenAI embedding dimension
            "cosine",
        ],
    )


def init_pinecone_client():
    """Initialize Pinecone client with API key from environment.
    
    Returns:
        Pinecone client instance or None if API key is missing.
    """
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print(
            "Warning: PINECONE_API_KEY not set; vector search disabled.",
            file=sys.stderr,
        )
        return None
    
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=api_key)
        print("Pinecone client initialized successfully", file=sys.stderr)
        return pc
    except ImportError:
        print(
            "Warning: pinecone-client not installed; run 'pip install pinecone-client'",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(
            f"Warning: Failed to initialize Pinecone: {exc}",
            file=sys.stderr,
        )
        return None


def generate_embedding(text: str, model: str = "text-embedding-3-small") -> Optional[List[float]]:
    """Generate embedding vector for text using OpenAI.
    
    Args:
        text: Text to embed
        model: OpenAI embedding model to use
        
    Returns:
        List of floats representing the embedding, or None on failure
    """
    if not OPENAI_AVAILABLE:
        return None
        
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model=model,
            input=text[:8000]  # Truncate to avoid token limits
        )
        return response.data[0].embedding
    except Exception as exc:
        print(f"Warning: Embedding generation failed: {exc}", file=sys.stderr)
        return None


def ensure_pinecone_index(pinecone_client, index_name: str, dimension: int = 1536) -> bool:
    """Ensure Pinecone index exists, create if it doesn't.
    
    Args:
        pinecone_client: Initialized Pinecone client
        index_name: Name of the index
        dimension: Embedding dimension (1536 for text-embedding-3-small)
        
    Returns:
        True if index exists or was created, False on failure
    """
    if pinecone_client is None:
        return False
    
    try:
        from pinecone import ServerlessSpec
        
        # Check if index exists
        existing_indexes = pinecone_client.list_indexes()
        index_names = [idx.name for idx in existing_indexes]
        
        if index_name in index_names:
            print(f"Pinecone index '{index_name}' already exists", file=sys.stderr)
            return True
        
        # Create index
        print(f"Creating Pinecone index '{index_name}'...", file=sys.stderr)
        pinecone_client.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=os.getenv("PINECONE_CLOUD", "aws"),
                region=os.getenv("PINECONE_REGION", "us-east-1")
            )
        )
        print(f"Pinecone index '{index_name}' created successfully", file=sys.stderr)
        return True
        
    except Exception as exc:
        print(f"Warning: Failed to ensure Pinecone index: {exc}", file=sys.stderr)
        return False


def fetch_pinecone_similar_news(
    pinecone_client,
    query_text: str,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Query Pinecone for similar news articles using vector search.
    
    Args:
        pinecone_client: Initialized Pinecone client
        query_text: Text to search for similar articles
        top_k: Number of results to return
        
    Returns:
        List of similar news items with scores and metadata
    """
    if pinecone_client is None:
        return []
    
    try:
        # Get index name from environment or use default
        index_name = os.getenv("PINECONE_INDEX_NAME", "japan225-news-vectors")
        
        # Generate embedding for query
        query_embedding = generate_embedding(query_text)
        if query_embedding is None:
            print(
                "Warning: Could not generate query embedding (check OPENAI_API_KEY)",
                file=sys.stderr,
            )
            return []
        
        index = pinecone_client.Index(index_name)
        
        # Query Pinecone
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        
        similar_items = []
        for match in results.matches:
            item = {
                "score": float(match.score),
                "story_id": match.id,
                "headline": match.metadata.get("headline", ""),
                "publish_ts": match.metadata.get("publish_ts"),
                "summary": match.metadata.get("summary", ""),
                "type": match.metadata.get("type", "news"),
            }
            
            # Include user feedback if present (for analysis vectors)
            if match.metadata.get("user_status"):
                item["user_status"] = match.metadata.get("user_status")
            if match.metadata.get("user_feedback"):
                item["user_feedback"] = match.metadata.get("user_feedback")
            if match.metadata.get("generated_at"):
                item["generated_at"] = match.metadata.get("generated_at")
            if match.metadata.get("feedback_synced_at"):
                item["feedback_synced_at"] = match.metadata.get("feedback_synced_at")
            
            similar_items.append(item)
        
        print(f"Pinecone returned {len(similar_items)} similar items", file=sys.stderr)
        return similar_items
        
    except Exception as exc:
        print(
            f"Warning: Pinecone query failed: {exc}",
            file=sys.stderr,
        )
        return []


def upsert_news_to_pinecone(
    pinecone_client,
    news_items: List[NewsItem]
) -> Dict[str, Any]:
    """Upsert news items to Pinecone vector database.
    
    Args:
        pinecone_client: Initialized Pinecone client
        news_items: List of NewsItem objects to upsert
        
    Returns:
        Dictionary with upsert statistics
    """
    if pinecone_client is None or not news_items:
        return {"upserted": 0, "error": "no_client_or_items"}
    
    try:
        index_name = os.getenv("PINECONE_INDEX_NAME", "japan225-news-vectors")
        
        # Ensure index exists
        if not ensure_pinecone_index(pinecone_client, index_name):
            return {"upserted": 0, "error": "index_creation_failed"}
        
        index = pinecone_client.Index(index_name)
        
        vectors = []
        for item in news_items:
            # Combine headline and summary for richer embeddings
            text = f"{item.headline}\n\n{item.summary}"
            
            embedding = generate_embedding(text)
            if embedding is None:
                continue
            
            vectors.append({
                "id": f"news_{item.story_id}",
                "values": embedding,
                "metadata": {
                    "story_id": item.story_id,
                    "headline": item.headline[:500],  # Pinecone metadata size limit
                    "publish_ts": item.publish_ts.isoformat() if item.publish_ts else None,
                    "summary": item.summary[:1000],  # Pinecone metadata size limit
                    "type": "news",
                }
            })
        
        if vectors:
            # Batch upsert (Pinecone handles up to 1000 vectors per batch)
            batch_size = 100
            total_upserted = 0
            
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                index.upsert(vectors=batch)
                total_upserted += len(batch)
            
            print(f"Upserted {total_upserted} news vectors to Pinecone", file=sys.stderr)
            return {"upserted": total_upserted}
        else:
            return {"upserted": 0, "error": "no_embeddings_generated"}
        
    except Exception as exc:
        return {"upserted": 0, "error": str(exc)}


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
    """Pull recent daily price bars and derive the latest close for a market."""

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


def get_ishares_japan_market_id(con: duckdb.DuckDBPyConnection) -> Optional[int]:
    """Return the market_id for iShares MSCI Japan Index DFT, if present.

    This looks up the market by its human-readable name in the local DuckDB
    ``markets`` table. If the market is missing, we log a warning and return
    ``None`` instead of aborting the script.
    """

    row = con.execute(
        "SELECT market_id, name FROM markets "
        "WHERE name = 'iShares MSCI Japan Index DFT'"
    ).fetchone()

    if not row:
        print(
            "Warning: no 'iShares MSCI Japan Index DFT' entry found in markets table",
            file=sys.stderr,
        )
        return None

    market_id, market_name = row
    print(
        "Meta (related market):",
        f"ishares_market_id={market_id} (name={market_name})",
        file=sys.stderr,
    )
    return int(market_id)


# ---------------------------------------------------------------------------
# Economic calendar integration (free API)
# ---------------------------------------------------------------------------


# We use the public Economic Data Releases Calendar endpoint from Financial
# Modeling Prep, which offers a free tier (API key required). This uses the
# "stable" base URL and avoids scraping HTML from sites that actively block
# non-browser clients.
_FMP_ECON_BASE = "https://financialmodelingprep.com/stable/economic-calendar"


def fetch_economic_calendar(target_date: Optional[date] = None) -> Dict[str, Any]:
    """Fetch economic calendar events for a given date.

    The function calls the Financial Modeling Prep economic calendar endpoint
    for ``target_date`` (UTC) and normalises the response into a compact
    structure suitable for LLM consumption.

    Configuration:
    - FMP_API_KEY: required, free tier API key from Financial Modeling Prep.

    On failure, this returns a small ``{"error": ...}`` payload rather than
    raising, so the main script can continue.
    """

    if target_date is None:
        target_date = datetime.now(tz=UTC).date()

    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return {
            "source": "fmp_economic_calendar",
            "calendar_date": target_date.isoformat(),
            "error": "missing_api_key",
            "message": "Set FMP_API_KEY to enable economic calendar lookups.",
        }

    params = {
        "from": target_date.isoformat(),
        "to": target_date.isoformat(),
        "apikey": api_key,
    }

    try:
        resp = requests.get(_FMP_ECON_BASE, params=params, timeout=10)
        if not resp.ok:
            return {
                "source": "fmp_economic_calendar",
                "calendar_date": target_date.isoformat(),
                "error": "http_error",
                "status_code": resp.status_code,
                "body": resp.text[:500],
            }
        raw = resp.json() or []
    except Exception as exc:  # pragma: no cover - network
        return {
            "source": "fmp_economic_calendar",
            "calendar_date": target_date.isoformat(),
            "error": "request_exception",
            "message": str(exc),
        }

    events: List[Dict[str, Any]] = []
    for row in raw:
        try:
            country = str(row.get("country") or "")
            currency = str(row.get("currency") or "")

            # Focus on Japan / JPY events for Nikkei 225 trading.
            # In the stable economic-calendar API, country is an ISO code like
            # "JP" rather than the full name "Japan".
            if country.upper() not in {"JP", "JAPAN"} and currency != "JPY":
                continue

            events.append(
                {
                    "event": str(row.get("event") or ""),
                    "country": country,
                    "currency": currency or None,
                    "impact": row.get("impact"),
                    "actual": row.get("actual"),
                    # Stable API uses "estimate" instead of "forecast".
                    "forecast": row.get("forecast") or row.get("estimate"),
                    "previous": row.get("previous"),
                    "change": row.get("change"),
                    "change_percentage": row.get("changePercentage"),
                    # Stable API provides a "date" string like
                    # "2024-03-01 03:35:00".
                    "event_dt": row.get("dateTime")
                    or row.get("date")
                    or row.get("event_dt"),
                }
            )
        except Exception:
            # Skip malformed rows but keep the rest.
            continue

    return {
        "source": "fmp_economic_calendar",
        "calendar_date": target_date.isoformat(),
        "events": events,
        "raw_count": len(raw),
    }


def execute_trading_orders(
    client: CityIndexClient,
    trading_account_id: int,
    market_id: int,
    orders: List[Dict[str, Any]],
    dry_run: bool = True
) -> List[Dict[str, Any]]:
    """Execute parsed trading orders via City Index API.
    
    Uses the /TradingAPI/order/newstoplimitorder endpoint for placing resting orders.
    
    Args:
        client: Authenticated City Index client
        trading_account_id: Trading account ID
        market_id: Market ID for Japan 225
        orders: List of order dictionaries from parse_trading_recommendations
        dry_run: If True, validate but don't execute orders (default: True)
        
    Returns:
        List of execution results for each order
    """
    results = []
    
    for idx, order in enumerate(orders):
        try:
            order_result = {
                'order_index': idx,
                'original_order': order,
                'status': 'pending',
            }
            
            # Validate required fields
            if 'Direction' not in order:
                order_result['status'] = 'failed'
                order_result['error'] = 'missing_direction'
                results.append(order_result)
                continue
            
            # Map direction to API format
            direction = order['Direction'].lower()
            if direction not in ['buy', 'sell']:
                order_result['status'] = 'failed'
                order_result['error'] = f'invalid_direction: {direction}'
                results.append(order_result)
                continue
            
            # Build order payload according to City Index API spec
            # POST /TradingAPI/order/newstoplimitorder
            order_payload = {
                "MarketId": market_id,
                "Direction": direction,
                "Quantity": order.get('Quantity', 1.0),
                "TradingAccountId": trading_account_id,
                "isTrade": False,  # This is an order, not a trade
                "PositionMethodId": 1,  # LongOrShortOnly
                "Applicability": "GTC",  # Good Till Cancelled
                "AutoRollover": False,
                "OrderId": 0,  # Platform generates this
                "IfDone": [],  # No attached If/Done orders (NFA compliance)
                "OcoOrder": None,  # No OCO orders
            }
            
            # Add trigger price (required for limit/stop orders)
            if 'TriggerPrice' in order and order['TriggerPrice']:
                order_payload['TriggerPrice'] = float(order['TriggerPrice'])
            elif 'OfferPrice' in order and order['OfferPrice']:
                order_payload['TriggerPrice'] = float(order['OfferPrice'])
            elif 'entry_price' in order and order.get('entry_price'):
                order_payload['TriggerPrice'] = float(order['entry_price'])
            else:
                # No trigger price specified - cannot place limit order
                order_result['status'] = 'failed'
                order_result['error'] = 'missing_trigger_price'
                results.append(order_result)
                continue
            
            # Add BidPrice and OfferPrice (current market prices)
            # These should ideally come from a real-time quote
            # For now, use trigger price as approximation
            if 'BidPrice' in order:
                order_payload['BidPrice'] = float(order['BidPrice'])
            else:
                order_payload['BidPrice'] = order_payload['TriggerPrice']
                
            if 'OfferPrice' in order:
                order_payload['OfferPrice'] = float(order['OfferPrice'])
            else:
                order_payload['OfferPrice'] = order_payload['TriggerPrice']
            
            # Optional: Add stop loss as an If/Done order
            # Note: NFA regulated accounts cannot use If/Done orders
            if 'StopPrice' in order and order['StopPrice']:
                # You may need to create a separate stop order or use If/Done
                # For now, store it in metadata
                order_payload['_stop_price_metadata'] = float(order['StopPrice'])
            
            # Optional: Add take profit as an If/Done order
            if 'LimitPrice' in order and order['LimitPrice']:
                order_payload['_limit_price_metadata'] = float(order['LimitPrice'])
            
            # Optional fields
            if 'AuditId' in order:
                order_payload['AuditId'] = order['AuditId']
            if 'Reference' in order:
                order_payload['Reference'] = order['Reference']
            
            order_result['api_payload'] = order_payload
            
            if dry_run:
                order_result['status'] = 'dry_run_success'
                order_result['message'] = 'Order validated but not executed (dry_run=True)'
                print(
                    f"DRY RUN: Would execute order {idx + 1}: "
                    f"{direction.upper()} {order_payload['Quantity']} @ "
                    f"{order_payload['TriggerPrice']}",
                    file=sys.stderr,
                )
            else:
                # Actually execute the order via City Index API
                print(
                    f"EXECUTING: Order {idx + 1}: "
                    f"{direction.upper()} {order_payload['Quantity']} @ "
                    f"{order_payload['TriggerPrice']}",
                    file=sys.stderr,
                )
                
                try:
                    # Call the City Index API endpoint
                    headers = {
                        "username": client.username,
                        "session": client.session,
                        "Content-Type": "application/json",
                    }
                    url = f"{API_BASE}/TradingAPI/order/newstoplimitorder"
                    
                    resp = requests.post(
                        url,
                        headers=headers,
                        json=order_payload,
                        timeout=30,
                    )
                    
                    if resp.ok:
                        response_data = resp.json()
                        order_result['status'] = 'executed'
                        order_result['response'] = response_data
                        order_result['order_id'] = response_data.get('OrderId')
                        print(
                            f"Order executed successfully. OrderId: {order_result.get('order_id')}",
                            file=sys.stderr,
                        )
                    else:
                        order_result['status'] = 'failed'
                        order_result['error'] = f'api_error: {resp.status_code}'
                        order_result['response_body'] = resp.text
                        print(
                            f"Order execution failed: {resp.status_code} - {resp.text}",
                            file=sys.stderr,
                        )
                        
                except Exception as api_exc:
                    order_result['status'] = 'failed'
                    order_result['error'] = f'api_exception: {str(api_exc)}'
                    print(f"API call failed: {api_exc}", file=sys.stderr)
            
            results.append(order_result)
            
        except Exception as exc:
            results.append({
                'order_index': idx,
                'original_order': order,
                'status': 'failed',
                'error': str(exc),
            })
            print(f"Error processing order {idx + 1}: {exc}", file=sys.stderr)
    
    return results


def parse_trading_recommendations(analysis_markdown: str) -> List[Dict[str, Any]]:
    """Parse Gemini analysis to extract trading recommendations as order objects.
    
    Searches for JSON arrays containing City Index order objects in the analysis.
    The function looks for section 9 (Order Execution) which should contain a
    JSON array of properly formatted orders.
    
    Args:
        analysis_markdown: The markdown analysis from Gemini
        
    Returns:
        List of order dictionaries ready for API submission
    """
    orders = []
    
    if not analysis_markdown:
        return orders
    
    import re
    import json
    
    try:
        # Method 1: Look for JSON array blocks (primary method)
        # Pattern: ```json\n[\n  {...}\n]\n```
        json_array_match = re.search(
            r'```json\s*(\[\s*\{.*?\}\s*\])\s*```',
            analysis_markdown,
            re.DOTALL
        )
        
        if json_array_match:
            json_str = json_array_match.group(1)
            parsed_orders = json.loads(json_str)
            
            if isinstance(parsed_orders, list):
                print(
                    f"Found {len(parsed_orders)} order(s) in JSON array",
                    file=sys.stderr,
                )
                return parsed_orders
            elif isinstance(parsed_orders, dict):
                # Single order wrapped in dict instead of array
                return [parsed_orders]
        
        # Method 2: Look for individual JSON objects (fallback)
        json_object_matches = re.finditer(
            r'```json\s*(\{[^`]*?\})\s*```',
            analysis_markdown,
            re.DOTALL
        )
        
        for match in json_object_matches:
            try:
                order = json.loads(match.group(1))
                if isinstance(order, dict) and 'Direction' in order:
                    orders.append(order)
            except json.JSONDecodeError:
                continue
        
        if orders:
            print(
                f"Found {len(orders)} order(s) in separate JSON blocks",
                file=sys.stderr,
            )
            return orders
        
        # Method 3: Natural language parsing (last resort)
        print(
            "No JSON orders found, attempting natural language parsing",
            file=sys.stderr,
        )
        lines = analysis_markdown.lower().split('\n')
        
        current_order = {}
        
        for line in lines:
            line = line.strip()
            
            # Look for action indicators
            if 'recommend' in line or 'suggestion' in line or 'trade' in line or 'order' in line:
                # Extract direction
                if 'buy' in line or 'long' in line:
                    current_order['Direction'] = 'buy'
                elif 'sell' in line or 'short' in line:
                    current_order['Direction'] = 'sell'
                
                # Extract price levels using regex
                
                # Look for entry price patterns like "at 50,700" or "@ 50700"
                entry_match = re.search(r'(?:at|@|entry|price)[:\s]+([0-9,]+(?:\.[0-9]+)?)', line)
                if entry_match:
                    current_order['TriggerPrice'] = float(entry_match.group(1).replace(',', ''))
                
                # Look for quantity/size patterns
                size_match = re.search(r'(?:size|quantity|lots?)[:\s]+([0-9.]+)', line)
                if size_match:
                    current_order['Quantity'] = float(size_match.group(1))
            
            # If we've collected a complete order, add it to the list
            if current_order and 'Direction' in current_order and 'TriggerPrice' in current_order:
                # Set defaults if missing
                if 'Quantity' not in current_order:
                    current_order['Quantity'] = 1.0
                
                # Add required fields for City Index API
                current_order.setdefault('isTrade', False)
                current_order.setdefault('OrderId', 0)
                current_order.setdefault('IfDone', [])
                current_order.setdefault('OcoOrder', None)
                current_order.setdefault('Applicability', 'GTC')
                current_order.setdefault('PositionMethodId', 1)
                current_order.setdefault('AutoRollover', False)
                
                orders.append(current_order)
                current_order = {}
        
    except Exception as exc:
        print(f"Warning: Failed to parse trading recommendations: {exc}", file=sys.stderr)
    
    return orders


def extract_structured_recommendation(analysis_markdown: str) -> Dict[str, Any]:
    """Extract structured recommendation section from Gemini analysis.
    
    Looks for section 9 (Order Execution) or other structured sections
    that contain trading recommendations.
    
    Args:
        analysis_markdown: The markdown analysis from Gemini
        
    Returns:
        Dictionary with extracted recommendation data including parsed orders
    """
    import re
    import json
    
    if not analysis_markdown:
        return {}
    
    recommendation = {}
    
    try:
        # Extract Section 9: Order Execution if present
        section_9_match = re.search(
            r'##?\s*9\.?\s*Order Execution.*?(?=##|\Z)',
            analysis_markdown,
            re.IGNORECASE | re.DOTALL
        )
        
        if section_9_match:
            section_9_text = section_9_match.group(0)
            recommendation['order_execution_section'] = section_9_text[:500]
            
            # Try to extract JSON from this section
            json_match = re.search(
                r'```json\s*(\[.*?\]|\{.*?\})\s*```',
                section_9_text,
                re.DOTALL
            )
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    if isinstance(parsed, list):
                        recommendation['orders_from_json'] = parsed
                        recommendation['order_count'] = len(parsed)
                    elif isinstance(parsed, dict):
                        recommendation['orders_from_json'] = [parsed]
                        recommendation['order_count'] = 1
                except json.JSONDecodeError:
                    pass
        
        # Extract NT Ratio target if mentioned
        nt_ratio_match = re.search(
            r'NT Ratio.*?([0-9.]+)',
            analysis_markdown,
            re.IGNORECASE
        )
        if nt_ratio_match:
            recommendation['nt_ratio_target'] = float(nt_ratio_match.group(1))
        
        # Extract take profit level
        tp_match = re.search(
            r'(?:take profit|target).*?([0-9,]+(?:\.[0-9]+)?)',
            analysis_markdown,
            re.IGNORECASE
        )
        if tp_match:
            recommendation['take_profit'] = float(tp_match.group(1).replace(',', ''))
        
        # Extract stop loss level
        sl_match = re.search(
            r'(?:stop loss|stop).*?([0-9,]+(?:\.[0-9]+)?)',
            analysis_markdown,
            re.IGNORECASE
        )
        if sl_match:
            recommendation['stop_loss'] = float(sl_match.group(1).replace(',', ''))
        
        # Look for confidence/conviction level
        confidence_match = re.search(
            r'(?:confidence|conviction).*?(high|medium|low)',
            analysis_markdown,
            re.IGNORECASE
        )
        if confidence_match:
            recommendation['confidence'] = confidence_match.group(1).lower()
        
        # Look for any explicit JSON blocks (fallback)
        if not recommendation.get('orders_from_json'):
            json_blocks = re.findall(
                r'```json\s*(\{.*?\})\s*```',
                analysis_markdown,
                re.DOTALL
            )
            
            for block in json_blocks:
                try:
                    parsed = json.loads(block)
                    if isinstance(parsed, dict) and any(key in parsed for key in ['action', 'Direction', 'MarketId']):
                        recommendation.setdefault('recommendation_blocks', []).append(parsed)
                except json.JSONDecodeError:
                    continue
        
    except Exception as exc:
        print(f"Warning: Failed to extract structured recommendation: {exc}", file=sys.stderr)
    
    return recommendation


def upsert_analysis_to_pinecone(
    pinecone_client,
    analysis_markdown: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Upload Gemini analysis to Pinecone for future retrieval.
    
    Args:
        pinecone_client: Initialized Pinecone client
        analysis_markdown: The markdown analysis from Gemini
        context: Full context dictionary with metadata
        
    Returns:
        Dictionary with upsert statistics
    """
    if pinecone_client is None or not analysis_markdown:
        return {"upserted": 0, "error": "no_client_or_analysis"}
    
    try:
        index_name = os.getenv("PINECONE_INDEX_NAME", "japan225-news-vectors")
        
        # Ensure index exists
        if not ensure_pinecone_index(pinecone_client, index_name):
            return {"upserted": 0, "error": "index_creation_failed"}
        
        index = pinecone_client.Index(index_name)
        
        # Generate embedding for the full analysis
        embedding = generate_embedding(analysis_markdown)
        if embedding is None:
            return {"upserted": 0, "error": "embedding_generation_failed"}
        
        # Create unique ID based on timestamp
        analysis_id = f"analysis_{context.get('generated_at_utc', 'unknown').replace(':', '-').replace('.', '-')}"
        
        # Extract key metadata
        meta = context.get("meta", {})
        latest_close = context.get("price", {}).get("japan225_dft", {}).get("latest_close")
        
        # Extract order information
        orders = context.get("trading_recommendations", {}).get("orders", [])
        order_count = len(orders)
        order_directions = [o.get("Direction") for o in orders if o.get("Direction")]
        primary_direction = order_directions[0] if order_directions else None
        
        # Calculate total position size
        total_quantity = sum(o.get("Quantity", 0) for o in orders)
        
        # Prepare vector with metadata
        vector = {
            "id": analysis_id,
            "values": embedding,
            "metadata": {
                "type": "analysis",
                "generated_at": context.get("generated_at_utc"),
                "market_id": meta.get("market_id"),
                "latest_close": latest_close,
                "analysis_preview": analysis_markdown[:1000],  # First 1000 chars
                "headline_count": len(context.get("news", {}).get("latest_headlines", [])),
                "has_positions": len(context.get("open_positions", {}).get("OpenPositions", [])) > 0,
                "order_count": order_count,
                "primary_direction": primary_direction,
                "total_quantity": total_quantity,
                "has_orders": order_count > 0,
            }
        }
        
        # Upsert to Pinecone
        index.upsert(vectors=[vector])
        
        print(f"Uploaded analysis to Pinecone with ID: {analysis_id}", file=sys.stderr)
        return {"upserted": 1, "analysis_id": analysis_id}
        
    except Exception as exc:
        print(f"Warning: Failed to upload analysis to Pinecone: {exc}", file=sys.stderr)
        return {"upserted": 0, "error": str(exc)}


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
    
    # Extract feedback from RAG results to highlight it
    feedback_items = [
        item for item in context.get("rag_top_news", [])
        if item.get("user_status") or item.get("user_feedback")
    ]
    
    feedback_section = ""
    if feedback_items:
        feedback_section = "\n".join([
            "",
            "=== YOUR PAST DECISIONS AND FEEDBACK ===",
            "IMPORTANT: Review your previous feedback on similar situations.",
            "Learn from these past decisions to make better recommendations.",
            "",
        ])
        for i, item in enumerate(feedback_items[:3], 1):  # Show top 3
            feedback_section += f"\n**Past Analysis {i}:**\n"
            feedback_section += f"- **Date**: {item.get('generated_at', 'Unknown')}\n"
            feedback_section += f"- **Your Decision**: {item.get('user_status', 'N/A')}\n"
            feedback_section += f"- **Your Reasoning**: {item.get('user_feedback', 'N/A')}\n"
            feedback_section += f"- **Context**: {item.get('headline', '')[:100]}...\n"
        feedback_section += "\nConsider this feedback when making today's recommendation.\n"
    
    full_prompt = "\n".join(
        [
            "You are a senior quantitative trader at Jane Street specialising in Japanese equity index products.",
            "Follow the ANALYSIS FRAMEWORK and RESPONSE STRUCTURE below exactly when writing your answer.",
            "",
            feedback_section,  # Add feedback section EARLY in prompt
            "=== ANALYSIS FRAMEWORK (FROM docs/claud.md) ===",
            framework_prompt,
            "",
            "=== CRITICAL: ORDER EXECUTION FORMAT ===",
            "In section 9 (Order Execution), you MUST output orders in valid JSON format that can be parsed.",
            "Use this EXACT structure for each order:",
            "",
            "```json",
            "[",
            "  {",
            '    "isTrade": false,',
            '    "AutoRollover": false,',
            '    "AuditId": "jane_street_basis_trade",',
            '    "Currency": null,',
            '    "Direction": "buy",',
            '    "LastChangedDateTimeUTC": null,',
            '    "MarketName": "Japan 225 DFT",',
            '    "BidPrice": 50690.0,',
            '    "PositionMethodId": 1,',
            '    "ExpiryDateTimeUTCDate": null,',
            '    "Status": null,',
            '    "MarketId": 400616391,',
            '    "LastChangedDateTimeUTCDate": null,',
            '    "Reference": "Entry_Long_TOPIX_Leg",',
            '    "OfferPrice": 50710.0,',
            '    "TriggerPrice": 50700.0,',
            '    "OrderId": 0,',
            '    "Quantity": 1,',
            '    "QuoteId": null,',
            '    "IfDone": [],',
            '    "TradingAccountId": 400236033,',
            '    "OcoOrder": null,',
            '    "Type": null,',
            '    "Applicability": "GTC",',
            '    "ExpiryDateTimeUTC": null',
            "  }",
            "]",
            "```",
            "",
            "REQUIREMENTS:",
            "- Output orders as a JSON array wrapped in ```json code fence",
            "- Use actual MarketId: 400616391 (Japan 225 DFT)",
            "- Use actual TradingAccountId: 400236033",
            "- Set Direction to 'buy' or 'sell' (lowercase)",
            "- Set TriggerPrice based on last 4hr intraday moves",
            "- Include BidPrice and OfferPrice from current market data",
            "- Set Reference field to describe the order leg (e.g., 'Short_NKY_Leg', 'Long_TPX_Leg')",
            "- Set AuditId to 'jane_street_basis_trade' or similar",
            "- Always set OrderId to 0 (platform generates)",
            "- Always set IfDone to empty array []",
            "- Always set isTrade to false",
            "- Set Applicability to 'GTC' (Good Till Cancelled)",
            "",
            "For a typical SHORT NIKKEI / LONG TOPIX basis trade, you would output 2 orders:",
            "1. SELL order for Nikkei 225 (short leg)",
            "2. BUY order for TOPIX or equivalent (long leg - note: if TOPIX not available, use iShares MSCI Japan)",
            "",
            "=== CONTEXT JSON (news, positions, orders, prices, RAG hits) ===",
            json.dumps(context, indent=2, default=str),
            "",
            "Write your complete analysis following the framework structure.",
            "In section 9, output executable orders in the JSON format shown above.",
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


def collect_news_context(
    client: CityIndexClient,
    market_id: int,
    con: duckdb.DuckDBPyConnection,
    pinecone_client=None
) -> Dict[str, Any]:
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
    
    # Optionally upsert to Pinecone
    if pinecone_client is not None:
        pinecone_stats = upsert_news_to_pinecone(pinecone_client, items)
        print(f"Pinecone upsert stats: {pinecone_stats}", file=sys.stderr)

    yday_items = load_yesterdays_news(con)

    return {
        "latest_headlines": [asdict(i) for i in items],
        "yesterdays_news": [asdict(i) for i in yday_items],
    }


def main() -> None:
    prompt = load_prompt()

    # Initialize single DuckDB connection
    if not DB_PATH.exists():
        print(f"DuckDB metadata file not found at {DB_PATH}", file=sys.stderr)
        raise SystemExit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH.as_posix())

    # Initialize Pinecone client (optional)
    pinecone_client = init_pinecone_client()

    # Get metadata using shared connection
    market_id, trading_account_id, client_account_id = get_meta_ids(con)

    # Ensure tables exist using shared connection
    ensure_news_table(con)
    ensure_llm_meta(con)
    ensure_pinecone_meta(con)

    client = CityIndexClient()

    news_ctx = collect_news_context(client, market_id, con, pinecone_client)
    open_positions = fetch_open_positions(client, trading_account_id)
    active_orders = fetch_active_orders(client, trading_account_id)
    price_ctx_japan225 = fetch_price_context(client, market_id)

    # Optional: price history for iShares MSCI Japan Index DFT
    ishares_market_id = get_ishares_japan_market_id(con)
    price_ctx_ishares: Dict[str, Any]
    if ishares_market_id is not None:
        try:
            price_ctx_ishares = fetch_price_context(client, ishares_market_id)
        except Exception as exc:  # pragma: no cover - network
            price_ctx_ishares = {
                "error": "ishares_price_fetch_failed",
                "message": str(exc),
            }
    else:
        price_ctx_ishares = {"error": "ishares_market_not_found"}

    # Economic calendar snapshot for the current UTC day
    econ_calendar = fetch_economic_calendar()

    # Build a RAG query
    rag_query = (prompt or "").strip()
    if not rag_query:
        rag_query = (
            "Japan 225 index, Nikkei, BoJ policy, yen intervention, "
            "holiday liquidity, nuclear restart, equity risk sentiment"
        )

    # Try both traditional RAG and Pinecone vector search
    rag_top_news: List[Dict[str, Any]] = []
    
    try:
        rag_hits = retrieve_similar_news(rag_query, top_k=10)
        rag_top_news = [
            {
                "source": "traditional_rag",
                "score": h.score,
                "story_id": h.story_id,
                "publish_ts": h.publish_ts,
                "headline": h.headline,
                "summary": h.summary,
            }
            for h in rag_hits
        ]
    except Exception as exc:  # pragma: no cover - retrieval is best-effort
        rag_top_news.append({
            "source": "traditional_rag",
            "error": "retriever_error",
            "message": str(exc),
        })

    # Add Pinecone results if available
    if pinecone_client is not None:
        pinecone_results = fetch_pinecone_similar_news(
            pinecone_client,
            rag_query,
            top_k=10
        )
        if pinecone_results:
            rag_top_news.extend([
                {**item, "source": "pinecone"}
                for item in pinecone_results
            ])

    context: Dict[str, Any] = {
        "prompt": prompt,
        "meta": {
            "market_id": market_id,
            "trading_account_id": trading_account_id,
            "client_account_id": client_account_id,
            "pinecone_enabled": pinecone_client is not None,
        },
        "news": news_ctx,
        "open_positions": open_positions,
        "active_orders": active_orders,
        "price": {
            "japan225_dft": price_ctx_japan225,
            "ishares_msci_japan_dft": price_ctx_ishares,
        },
        "calendar": econ_calendar,
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

    # Parse trading recommendations from Gemini analysis
    trading_orders = []
    if analysis_md:
        trading_orders = parse_trading_recommendations(analysis_md)
        structured_recommendation = extract_structured_recommendation(analysis_md)
        
        if trading_orders:
            print(f"Parsed {len(trading_orders)} trading order(s) from analysis", file=sys.stderr)
            
            # Execute orders (dry run by default for safety)
            dry_run = os.getenv("EXECUTE_ORDERS", "false").lower() != "true"
            execution_results = execute_trading_orders(
                client=client,
                trading_account_id=trading_account_id,
                market_id=market_id,
                orders=trading_orders,
                dry_run=dry_run,
            )
            
            context["trading_recommendations"] = {
                "orders": trading_orders,
                "structured": structured_recommendation,
                "count": len(trading_orders),
                "execution_results": execution_results,
                "dry_run": dry_run,
            }
        else:
            context["trading_recommendations"] = {
                "orders": [],
                "structured": structured_recommendation,
                "count": 0,
                "message": "No actionable trading orders parsed from analysis",
            }

    # Upload Gemini analysis to Pinecone
    if pinecone_client is not None and analysis_md:
        pinecone_analysis_stats = upsert_analysis_to_pinecone(
            pinecone_client,
            analysis_md,
            context
        )
        context["pinecone_analysis_upload"] = pinecone_analysis_stats

    # Optionally publish to Notion if configured
    notion_db_id = os.getenv("NOTION_SECOND_BRAIN_DB_ID")
    if notion_db_id and analysis_md:
        try:
            # Use the generated_at_utc timestamp as the Notion PublishedDate.
            published_ts = context.get("generated_at_utc") or datetime.now(tz=UTC).isoformat()
            
            # Get Pinecone analysis ID for consistent naming
            pinecone_analysis_id = context.get("pinecone_analysis_upload", {}).get("analysis_id", "")
            
            # Create a human-readable title with timestamp
            dt = datetime.fromisoformat(published_ts.replace('Z', '+00:00'))
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M UTC')
            notion_title = f"Japan 225 Analysis - {timestamp_str}"
            
            # Extract order summary for title suffix
            orders = context.get("trading_recommendations", {}).get("orders", [])
            if orders:
                order_count = len(orders)
                primary_dir = orders[0].get("Direction", "").upper()
                notion_title += f" - {order_count} Order(s)"
                if primary_dir:
                    notion_title += f" ({primary_dir})"
            
            # Build Notion properties including Status, Reason, and PineconeID
            properties_extra_full = {
                "PublishedDate": {
                    "date": {"start": published_ts},
                },
                "Status": {
                    "status": {"name": "Pending"}  # Note: 'status' not 'select'
                },
                "Reason": {
                    "rich_text": []  # Empty - user fills this
                }
            }
            
            # Add Pinecone ID if available
            if pinecone_analysis_id:
                properties_extra_full["PineconeID"] = {
                    "rich_text": [{"text": {"content": pinecone_analysis_id}}]
                }
            
            # Merge with any extra properties passed in
            if context.get("properties_extra"):
                properties_extra_full.update(context["properties_extra"])
            
            page = publish_analysis_to_notion(
                database_id=notion_db_id,
                title=notion_title,
                analysis_markdown=analysis_md,
                tags=["Japan225", "Gemini", "SecondBrain"],
                properties_extra=properties_extra_full,
            )
            context["notion_page_id"] = page.get("id")
            context["notion_page_url"] = page.get("url")
            context["notion_title"] = notion_title
            print(f"Published to Notion: {notion_title}", file=sys.stderr)
        except Exception as exc:  # pragma: no cover - external API
            context.setdefault("notion_error", str(exc))
            print(f"Warning: Notion publishing failed: {exc}", file=sys.stderr)

    # Close the DuckDB connection
    con.close()

    print(json.dumps(context, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()