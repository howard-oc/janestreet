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




def main() -> None:
    # Reuse existing session if set, otherwise log on
    session = os.getenv("CITYINDEX_SESSION")
    if not session:
        session = log_on()
        print(f"Obtained session: {session}")

    print("\n--- News Headlines ---")
    news = get_news(session)
    print(json.dumps(news, indent=2))


if __name__ == "__main__":
    main()
