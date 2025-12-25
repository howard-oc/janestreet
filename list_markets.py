"""Example script to call ListMarketInformation v2.

Usage:
    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... uv run python list_markets.py 1234 5678

If CITYINDEX_SESSION is not set, this will log on first.
"""

import json
import os
import sys

from augmenttrade.client import CityIndexClient


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("Usage: uv run python list_markets.py <marketId> [<marketId> ...]", file=sys.stderr)
        raise SystemExit(1)

    try:
        market_ids = [int(arg) for arg in argv[1:]]
    except ValueError:
        print("All market IDs must be integers", file=sys.stderr)
        raise SystemExit(1)

    client = CityIndexClient()
    data = client.list_market_information(market_ids)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main(sys.argv)
