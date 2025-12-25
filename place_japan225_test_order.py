"""Place a test entry order on Japan 225 using stored IDs in DuckDB.

Usage (example):
    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... \
      uv run python place_japan225_test_order.py

This script:
- Reads the Japan225 MarketId and primary TradingAccountId from data/stonex_meta.duckdb
- Uses CityIndexClient to ensure we have a valid session
- Calls the Order endpoint (newstoplimitorder) to place a GTC limit order at 41000

By default this will PLACE A REAL ORDER on the live environment if your
credentials/session are live. Only run in environments you are comfortable with.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import requests

from augmenttrade.client import API_BASE, CityIndexClient

DB_PATH = Path("data/stonex_meta.duckdb")


def get_ids_from_db() -> tuple[int, int, int]:
    """Return (market_id, trading_account_id, client_account_id) from DuckDB.

    Expects:
    - markets table with symbol = 'JAPAN225'
    - trading_accounts table with alias = 'primary_spread_bet'
    """

    if not DB_PATH.exists():
        print(f"DuckDB file not found at {DB_PATH}", file=sys.stderr)
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
        f"Using market_id={market_id} (market_name={market_name}), "
        f"trading_account_id={trading_account_id}, client_account_id={client_account_id}",
        file=sys.stderr,
    )

    return int(market_id), int(trading_account_id), int(client_account_id)


def build_order_payload(*, market_id: int, trading_account_id: int, price: float) -> dict:
    """Build NewStopLimitOrderRequestDTO payload for a simple GTC limit buy.

    This mirrors the StoneX documentation example but targets Japan 225.
    """

    # For a buy limit at `price`, we set TriggerPrice = price. We choose a
    # BidPrice slightly below to mimic current market, though the key field is
    # TriggerPrice.
    bid_price = price - 10

    payload = {
        "isTrade": False,
        "AutoRollover": False,
        "AuditId": "test-japan225-41000-001",
        "Currency": None,
        "Direction": "buy",
        "LastChangedDateTimeUTC": None,
        "MarketName": "Japan 225 DFT",
        "BidPrice": bid_price,
        "PositionMethodId": 1,
        "ExpiryDateTimeUTCDate": None,
        "Status": None,
        "MarketId": market_id,
        "LastChangedDateTimeUTCDate": None,
        "Reference": "test-order",
        "OfferPrice": price,
        "TriggerPrice": price,
        "OrderId": 0,
        "Quantity": 1,
        "QuoteId": None,
        "IfDone": [],
        "TradingAccountId": trading_account_id,
        "OcoOrder": None,
        "Type": None,
        "Applicability": "GTC",
        "ExpiryDateTimeUTC": None,
    }

    return payload


def main() -> None:
    price = 41000.0

    market_id, trading_account_id, client_account_id = get_ids_from_db()

    # Ensure we have a valid session via the existing client wrapper.
    client = CityIndexClient()

    headers = {
        "username": client.username,
        "session": client.session,
        "Content-Type": "application/json",
    }

    payload = build_order_payload(
        market_id=market_id,
        trading_account_id=trading_account_id,
        price=price,
    )

    url = f"{API_BASE}/TradingAPI/order/newstoplimitorder"

    print("About to POST order payload to:", url, file=sys.stderr)
    print("Payload:", json.dumps(payload, indent=2), file=sys.stderr)

    resp = requests.post(url, headers=headers, json=payload)

    print("Status:", resp.status_code, file=sys.stderr)
    print("Raw response:", resp.text, file=sys.stderr)

    # Raise for visibility if non-2xx
    resp.raise_for_status()

    data = resp.json()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
