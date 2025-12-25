"""Example script to call GetFullSearchWithTags v2.

Usage:
    CITYINDEX_USERNAME=... CITYINDEX_PASSWORD=... CITYINDEX_APPKEY=... \
      uv run python search_markets.py "GBP/USD" --tag 80 --max 10

If CITYINDEX_SESSION is not set, this will log on first.
"""

import argparse
import json
import sys

from augmenttrade.client import CityIndexClient


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search markets with tags")
    parser.add_argument("query", nargs="?", default="", help="Search query (e.g. 'GBP/USD')")
    parser.add_argument("--tag", type=int, default=None, help="Market tag ID (e.g. 80 for FX)")
    parser.add_argument("--max", type=int, default=10, help="Max results (<= 200)")
    parser.add_argument("--client-account-id", default=None, help="ClientAccountId for the search")
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> None:
    args = parse_args(argv)

    client = CityIndexClient()
    data = client.full_search_with_tags(
        query=args.query,
        tag_id=args.tag,
        max_results=args.max,
        client_account_id=args.client_account_id,
    )

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main(sys.argv)
