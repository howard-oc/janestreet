"""Print yesterday's closing price for a given market using barhistory.

Usage:
    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... \
      uv run python get_yesterday_close.py 400616391
"""

import sys

from augmenttrade.client import CityIndexClient


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: uv run python get_yesterday_close.py <marketId>")
        raise SystemExit(1)

    market_id = int(argv[1])

    client = CityIndexClient()
    close = client.get_yesterday_close(market_id)

    if close is None:
        print(f"No daily bars available for market {market_id}")
    else:
        print(f"Yesterday close for market {market_id}: {close}")


if __name__ == "__main__":
    main(sys.argv)
