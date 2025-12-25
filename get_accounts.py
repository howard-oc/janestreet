"""Fetch and print ClientAccountId and TradingAccounts using GetClientAndTradingAccount v2."""

import json

from augmenttrade.client import CityIndexClient


def main() -> None:
    client = CityIndexClient()
    data = client.get_client_and_trading_accounts()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
