import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

API_BASE = "https://ciapi.cityindex.com"


def _get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Environment variable {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


@dataclass
class CityIndexClient:
    """Thin wrapper around the City Index HTTP API."""

    username: Optional[str] = None
    session: Optional[str] = None

    def __post_init__(self) -> None:
        if self.username is None:
            self.username = _get_env_var("CITYINDEX_USERNAME")
        if self.session is None:
            # Try existing session from env, otherwise log on
            self.session = os.getenv("CITYINDEX_SESSION") or self.log_on()

    def log_on(self) -> str:
        """Call LogOn v2 and return the session id."""
        username = self.username or _get_env_var("CITYINDEX_USERNAME")
        password = _get_env_var("CITYINDEX_PASSWORD")
        appkey = _get_env_var("CITYINDEX_APPKEY")

        payload = {
            "Password": password,
            "AppVersion": "1",
            "AppComments": "augmenttrade-client",
            "UserName": username,
            "AppKey": appkey,
        }

        resp = requests.post(f"{API_BASE}/v2/Session", json=payload)
        resp.raise_for_status()
        data = resp.json()
        session = data.get("session")
        if not session:
            print(
                f"Unexpected logon response: {json.dumps(data, indent=2)}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Cache in env for this process / shell if desired
        os.environ["CITYINDEX_SESSION"] = session
        self.session = session
        return session

    # --- News API ---------------------------------------------------------

    def get_news_headlines(
        self,
        source: str = "dj",
        category: str = "uk",
        max_results: int = 20,
    ) -> Any:
        """Fetch news headlines for a given source/category."""

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
        }
        url = f"{API_BASE}/TradingAPI/news/{source}/{category}"
        params = {"MaxResults": max_results}

        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_news_story(self, source: str, story_id: str) -> Dict[str, Any]:
        """Fetch full details for a single news story."""

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
        }
        url = f"{API_BASE}/TradingApi/news/{source}/{story_id}"

        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    # --- Market Information API ------------------------------------------

    def list_market_information(self, market_ids: list[int]) -> Dict[str, Any]:
        """Call ListMarketInformation v2 for a list of market IDs.

        This wraps POST /v2/market/information with the required auth headers.
        """

        if not market_ids:
            raise ValueError("market_ids must not be empty")

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
            "Content-Type": "application/json",
        }
        url = f"{API_BASE}/v2/market/information"
        payload = {"MarketIds": market_ids}

        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    # --- Market search API -----------------------------------------------

    def full_search_with_tags(
        self,
        query: str = "",
        tag_id: int | None = None,
        max_results: int = 50,
        search_by_market_name: bool = True,
        search_by_market_code: bool = True,
        spread_product_type: bool = True,
        cfd_product_type: bool = True,
        binary_product_type: bool = True,
        include_options: bool = True,
        use_mobile_short_name: bool = False,
        client_account_id: int | None = None,
    ) -> Dict[str, Any]:
        """Call GetFullSearchWithTags v2.

        Wraps GET /TradingAPI/v2/market/fullSearchWithTags with auth headers.
        """

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
        }

        params: Dict[str, Any] = {
            "SearchByMarketName": str(search_by_market_name).lower(),
            "SearchByMarketCode": str(search_by_market_code).lower(),
            "SpreadProductType": str(spread_product_type).lower(),
            "CfdProductType": str(cfd_product_type).lower(),
            "BinaryProductType": str(binary_product_type).lower(),
            "IncludeOptions": str(include_options).lower(),
            "UseMobileShortName": str(use_mobile_short_name).lower(),
            "MaxResults": max_results,
        }

        # Query text (empty for all markets)
        if query is not None:
            params["Query"] = query

        if tag_id is not None:
            params["TagId"] = tag_id

        if client_account_id is not None:
            params["ClientAccountId"] = client_account_id

        url = f"{API_BASE}/TradingAPI/v2/market/fullSearchWithTags"
        resp = requests.get(url, headers=headers, params=params)
        import sys
        print("STATUS:", resp.status_code, file=sys.stderr)
        print("BODY:", resp.text, file=sys.stderr)
        resp.raise_for_status()
        return resp.json()


    # --- User account API -----------------------------------------------

    def get_client_and_trading_accounts(self) -> Dict[str, Any]:
        """Call GetClientAndTradingAccount v2.

        Wraps GET /v2/userAccount/ClientAndTradingAccount with auth headers
        and returns the parsed JSON response.
        """

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
        }

        url = f"{API_BASE}/v2/userAccount/ClientAndTradingAccount"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


    # --- Price history API ----------------------------------------------

    def get_price_bars(
        self,
        market_id: int,
        interval: str = "DAY",
        span: int = 1,
        price_bars: int = 5,
        price_type: str | None = None,
    ) -> Dict[str, Any]:
        """Call barhistory (GetLatestPriceBars) for a given market.

        Returns the raw GetPriceBarResponseDTO as a dict.
        """

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
        }

        params: Dict[str, Any] = {
            "interval": interval,
            "span": span,
            "PriceBars": price_bars,
        }
        if price_type is not None:
            params["PriceType"] = price_type

        url = f"{API_BASE}/TradingAPI/market/{market_id}/barhistory"
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_yesterday_close(
        self,
        market_id: int,
        price_type: str | None = None,
    ) -> float | None:
        """Return the latest full-day close for the given market.

        Uses daily bars from barhistory and returns the Close of the final
        element in PriceBars, ignoring PartialPriceBar.
        """

        data = self.get_price_bars(
            market_id=market_id,
            interval="DAY",
            span=1,
            price_bars=5,
            price_type=price_type,
        )

        bars = data.get("PriceBars") or []
        if not bars:
            return None

        last_bar = bars[-1]
        return float(last_bar.get("Close"))


    # --- Trades and orders API -----------------------------------------

    def list_open_positions(self, trading_account_id: int) -> Dict[str, Any]:
        """Call ListOpenPositions for a given trading account.

        Wraps GET /TradingAPI/order/openpositions?TradingAccountId=... with
        the required auth headers and returns the parsed JSON response.
        """

        headers = {
            "username": self.username or _get_env_var("CITYINDEX_USERNAME"),
            "session": self.session or _get_env_var("CITYINDEX_SESSION"),
        }

        url = f"{API_BASE}/TradingAPI/order/openpositions"
        params = {"TradingAccountId": trading_account_id}

        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
