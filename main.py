import os
import sys
import json
import requests

API_BASE = "https://ciapi.cityindex.com"


def get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Environment variable {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def log_on() -> str:
    """Call LogOn v2 and return the session id."""
    username = get_env_var("CITYINDEX_USERNAME")
    password = get_env_var("CITYINDEX_PASSWORD")
    appkey = get_env_var("CITYINDEX_APPKEY")

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
        print(f"Unexpected logon response: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)

    return session


def get_news(session: str, source: str = "dj", category: str = "uk", max_results: int = 20):
    """Fetch news headlines for a given source/category."""
    headers = {
        "username": get_env_var("CITYINDEX_USERNAME"),
        "session": session,
    }
    url = f"{API_BASE}/TradingAPI/news/{source}/{category}"
    params = {"MaxResults": max_results}

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def get_trading_account_id(session: str) -> int:
    """Fetch the first trading account ID using User/ClientAndTradingAccount."""
    headers = {
        "username": get_env_var("CITYINDEX_USERNAME"),
        "session": session,
    }
    # Using v1 endpoint as per standard docs, though v2 might be available
    url = f"{API_BASE}/User/ClientAndTradingAccount"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    # Navigate the response to find a TradingAccountId
    # Typical structure: List of ClientAccountDTO, each has TradingAccountDTOs
    if isinstance(data, list) and data:
        client_account = data[0]
        trading_accounts = client_account.get("TradingAccounts", [])
        if trading_accounts:
            return trading_accounts[0].get("TradingAccountId")
            
    # Fallback or different structure?
    # Some endpoints return a dictionary directly
    if isinstance(data, dict):
         trading_accounts = data.get("TradingAccounts", [])
         if trading_accounts:
            return trading_accounts[0].get("TradingAccountId")

    raise ValueError(f"Could not find TradingAccountId in response: {json.dumps(data, indent=2)}")


def get_trade_history(session: str, trading_account_id: int, max_results: int = 100):
    """Fetch trade history."""
    headers = {
        "username": get_env_var("CITYINDEX_USERNAME"),
        "session": session,
    }
    url = f"{API_BASE}/order/tradehistory"
    params = {
        "TradingAccountId": trading_account_id,
        "MaxResults": max_results
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def print_monthly_pnl(trades: list) -> None:
    """Calculate and print PnL for the current month."""
    import datetime
    
    now = datetime.datetime.now(datetime.timezone.utc)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    monthly_pnl = 0.0
    count = 0
    
    print(f"\n--- Trade History & Monthly PnL (Current Month: {now.strftime('%B %Y')}) ---")
    
    # Sort trades by date, usually they are ordered but let's be sure or just process
    # The API 'tradehistory' usually returns recent first.
    
    for trade in trades:
        # Check date field. Usually 'ExecutedDateTimeUtc' or similar.
        date_str = trade.get("ExecutedDateTimeUtc")
        if not date_str:
            continue
            
        # Parse date - typical format: "2023-10-27T10:00:00" (sometimes with Z)
        try:
            # Handle potential Z or no Z
            if date_str.endswith('Z'):
                trade_date = datetime.datetime.fromisoformat(date_str[:-1]).replace(tzinfo=datetime.timezone.utc)
            else:
                 trade_date = datetime.datetime.fromisoformat(date_str).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            # Fallback for other formats if necessary
            continue
            
        pnl = trade.get("RealisedPnL", 0.0)
        
        # Print basic trade info
        print(f"{date_str} | {trade.get('Direction')} {trade.get('MarketName')} | PnL: {pnl}")

        if trade_date >= current_month_start:
            monthly_pnl += pnl
            count += 1
            
    print(f"\nTotal PnL for {now.strftime('%B %Y')}: {monthly_pnl:.2f} (over {count} trades)")


def main() -> None:
    # Reuse existing session if set, otherwise log on
    session = os.getenv("CITYINDEX_SESSION")
    if not session:
        session = log_on()
        print(f"Obtained session: {session}")

    try:
        trading_account_id = get_trading_account_id(session)
        print(f"Using TradingAccountId: {trading_account_id}")
        
        trades = get_trade_history(session, trading_account_id)
        # print(json.dumps(trades, indent=2)) # Debug
        
        print_monthly_pnl(trades)
        
    except Exception as e:
        print(f"Error fetching trade history: {e}", file=sys.stderr)

    print("\n--- News Headlines ---")
    news = get_news(session)
    print(json.dumps(news, indent=2))


if __name__ == "__main__":
    main()
