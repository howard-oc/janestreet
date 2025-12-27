# augmenttrade

## What is this?
An experimental personal project for exploring market data, trading ideas, and simple automation, using modern Python tooling and vector-based search.

It is **not** production-grade and is intended only for local, exploratory use.

## High-level overview
- Ingests and explores market data (see `docs/market/` and `docs/price_history/`).
- Experiments with alerts, news, and order/trade representations.
- Integrates with external services (Lightstreamer, Pinecone, OpenAI, Notion) for data, storage, and analysis.

## Project layout (rough)
- `src/augmenttrade/` – main Python package.
- `docs/` – notes and design sketches for specific areas:
  - `market/` – market data concepts and versions.
  - `messages/news/` – handling and normalising news.
  - `price_alerts/` – alert ideas and experiments.
  - `price_history/` – price history and storage.
  - `trades_and_orders/` – trade and order representations.
- `tests/` – tests (if/when added).

This structure will evolve as the project grows; update this section whenever you add or retire a major area.

## Getting started
### Prerequisites
- Python 3.12+
- A virtual environment manager (e.g. `uv`, `venv`, or `conda`).

### Setup
From the repository root:

```bash path=null start=null
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -e .
```

This installs `augmenttrade` in editable mode along with its core dependencies.

## Key dependencies (mental model)
- `duckdb` – local analytics and ad-hoc querying over structured data.
- `lightstreamer-client` – streaming market data client.
- `pinecone` – vector database for semantic search over stored content.
- `openai` / `google-genai` – LLM-based analysis and augmentation.
- `notion-client` – sync and notes in Notion.

You can comment out or stub any integrations you are not currently using.

## Running things

### Daily Japan 225 analysis (local)

This is the main end‑to‑end flow today.

```bash path=null start=null
# From repo root, after activating your venv and installing deps
$env:CITYINDEX_USERNAME = "..."
$env:CITYINDEX_PASSWORD = "..."
$env:CITYINDEX_APPKEY   = "..."
$env:PINECONE_API_KEY   = "..."    # optional but recommended
$env:OPENAI_API_KEY     = "..."    # for embeddings
$env:GOOGLE_GEMINI_API_KEY = "..." # for analysis
$env:NOTION_SECOND_BRAIN_TOKEN = "..."  # optional
$env:NOTION_SECOND_BRAIN_DB_ID = "..."  # optional
$env:FMP_API_KEY        = "..."    # optional economic calendar
$env:EXECUTE_ORDERS     = "false"  # keep as "false" while experimenting
$env:EXECUTE_ALERTS     = "false"  # alerts are optional

python janestreet.py > janestreet_$(Get-Date -Format 'yyyyMMdd_HHmm').json
```

What this does:
- Builds a full context for **Japan 225 DFT** (news, prices, econ calendar, positions, RAG hits).
- Runs the **Gemini** analysis using the framework in `docs/claud.md`.
- Optionally pushes the analysis and news to **Pinecone** and **Notion**.
- Writes a single JSON document with everything under `janestreet_YYYYMMDD_HHMM.json`.

Order execution is **dry‑run by default** (`EXECUTE_ORDERS="false"`); the JSON contains both the proposed orders and the simulated execution payload so you can review them safely.

### Daily Japan 225 analysis (GitHub Actions)

The workflow `.github/workflows/daily-analysis.yml` runs the same analysis on a schedule around Japan cash open/close and uploads the JSON as an artifact.

- It uses repo secrets for all API keys and credentials.
- By default, it also runs with `EXECUTE_ORDERS=false` for safety.
- You can trigger it manually with a custom `execute_orders` flag via **Run workflow** in GitHub.

If you change the prompt in `docs/claud.md` or the analysis logic in `janestreet.py`, both the local run and the workflow will pick it up.

## Development notes
- Keep everything **local and experimental**; no real-money trading without a deliberate promotion path.
- Prefer small, focused modules over large notebooks; treat notebooks as disposable scratchpads.
- When an experiment becomes useful, promote it into the package and document it here.

## Future tidy-up ideas
- Add a proper command-line entry point (e.g. `augmenttrade` console script).
- Standardise configuration (e.g. `config/` with `.env` support).
- Add tests for any non-trivial logic.
- Wire up simple CI (formatting, tests) when the project stabilises.
