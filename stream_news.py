"""Stream StoneX / City Index news headlines via Lightstreamer.

Usage:
    CITYINDEX_USERNAME=... CITYINDEX_SESSION=... uv run python stream_news.py

Notes:
- CITYINDEX_SESSION is the `session` value returned from the LogOn v2 HTTP call.
- Username is your trading username.
- Lightstreamer connection details (endpoint, adapter set, item name and
  field list) come from the StoneX streaming documentation and may need
  adjustment if they change upstream.
"""

import os
import sys
import time

from lightstreamer_client import LightstreamerClient, LightstreamerSubscription


LIGHTSTREAMER_ENDPOINT = "https://push.cityindex.com/lightstreamer"
ADAPTER_SET = "STREAMINGALL"

NEWS_ITEMS = ["NEWSHEADLINES"]
NEWS_FIELDS = [
    "TimeStamp",
    "Headline",
    "StoryId",
]


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Environment variable {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


class PrintNewsListener:
    def on_update(self, item_update):
        print("UPDATE:")
        for field_name, value in item_update.get("values", {}).items():
            print(f"  {field_name}: {value}")
        print("----", flush=True)

    def on_subscription(self):
        print("Subscribed to news stream", flush=True)

    def on_unsubscription(self):
        print("Unsubscribed from news stream", flush=True)

    def on_clear_snapshot(self):
        print("Snapshot cleared", flush=True)

    def on_error(self, code, message):
        print(f"Subscription error {code}: {message}", file=sys.stderr, flush=True)


def main() -> None:
    username = _get_env("CITYINDEX_USERNAME")
    session = _get_env("CITYINDEX_SESSION")

    # LightstreamerClient(username, password, url, adapter_set='')
    client = LightstreamerClient(username, session, LIGHTSTREAMER_ENDPOINT, ADAPTER_SET)

    subscription = LightstreamerSubscription("MERGE", NEWS_ITEMS, NEWS_FIELDS)
    subscription.addlistener(PrintNewsListener())

    try:
        client.subscribe(subscription)
        client.connect()
        client.subscribe(subscription)
        print("Connected to Lightstreamer; listening for news updates (Ctrl+C to stop).", flush=True)

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...", flush=True)
    finally:
        try:
            client.unsubscribe(subscription)
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
