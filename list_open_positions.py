"""List open positions for the current trading account.

Usage:
    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... \
      uv run python list_open_positions.py <tradingAccountId>

You can obtain `tradingAccountId` from GetClientAndTradingAccount v2.
"""

import json
import sys

from augmenttrade.client import CityIndexClient


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: uv run python list_open_positions.py <tradingAccountId>")
        raise SystemExit(1)

    trading_account_id = int(argv[1])

    client = CityIndexClient()
    data = client.list_open_positions(trading_account_id)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main(sys.argv)
