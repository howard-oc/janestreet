"""Notion publishing helper for LLM analysis (SecondBrain integration).

This module provides a thin wrapper around the Notion API for sending
analysis output into a Notion database.

Configuration
------------

- Create a Notion internal integration named **SecondBrain**.
- Copy the integration secret and store it in an environment variable, e.g.::

      export NOTION_SECOND_BRAIN_TOKEN="<your-secret>"

- Share the target database with the **SecondBrain** integration so it has
  permission to create pages.

Database requirements
---------------------

The helper assumes your database has at least:

- A ``Name`` property of type ``title``.
- Optionally a ``Tags`` property of type ``multi_select`` if you pass tags.

You can adapt ``build_properties`` below if your schema differs.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Iterable, List, Optional

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
TOKEN_ENV_VAR = "NOTION_SECOND_BRAIN_TOKEN"


def _get_token() -> str:
    """Return the Notion integration token from the environment.

    Exits with a clear error message if the token is not set.
    """

    token = os.getenv(TOKEN_ENV_VAR)
    if not token:
        print(
            f"Environment variable {TOKEN_ENV_VAR} is not set; "
            "export your SecondBrain Notion integration secret first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return token


def _build_headers() -> Dict[str, str]:
    token = _get_token()
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def build_properties(
    title: str,
    tags: Optional[Iterable[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a Notion properties payload.

    ``extra`` can be used to extend or override properties if your database
    schema differs from the default.
    """

    properties: Dict[str, Any] = {
        "Name": {
            "title": [
                {
                    "text": {"content": title},
                }
            ]
        }
    }

    if tags:
        properties["Tags"] = {
            "multi_select": [
                {"name": str(tag)} for tag in tags if str(tag).strip()
            ]
        }

    if extra:
        properties.update(extra)

    return properties


def publish_analysis_to_notion(
    *,
    database_id: str,
    title: str,
    analysis_markdown: str,
    tags: Optional[Iterable[str]] = None,
    properties_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a page in a Notion database containing LLM analysis.

    Parameters
    ----------
    database_id:
        The ID of the target Notion database (from the URL).
    title:
        Page title.
    analysis_markdown:
        The analysis body, usually markdown text produced by an LLM.
    tags:
        Optional tags to set on the ``Tags`` multi_select property.
    properties_extra:
        Optional extra/override properties compatible with the Notion API.
    """

    headers = _build_headers()
    properties = build_properties(title=title, tags=tags, extra=properties_extra)

    # Notion has limits on the length of a single rich_text object, so we
    # chunk the markdown into multiple paragraph blocks instead of truncating.
    def _chunk(text: str, size: int = 1800) -> List[str]:
        text = text or ""
        # Prefer splitting on paragraph boundaries where possible.
        paragraphs = text.replace("\r\n", "\n").split("\n\n")
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0
        for para in paragraphs:
            para_block = ("\n\n" if current else "") + para
            if current_len + len(para_block) > size and current:
                chunks.append("".join(current))
                current = [para]
                current_len = len(para)
            else:
                current.append(para_block if current else para)
                current_len += len(para_block)
        if current:
            chunks.append("".join(current))
        # Fallback: if any chunk is still too long, hard-split it.
        final_chunks: List[str] = []
        for c in chunks:
            if len(c) <= size:
                final_chunks.append(c)
            else:
                for i in range(0, len(c), size):
                    final_chunks.append(c[i : i + size])
        return final_chunks

    children: List[Dict[str, Any]] = []
    for block_text in _chunk(analysis_markdown, size=1800):
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": block_text},
                        }
                    ]
                },
            }
        )

    payload: Dict[str, Any] = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": children,
    }

    resp = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers=headers,
        json=payload,
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:  # pragma: no cover - network/JSON
        data = {"raw_text": resp.text}

    if not resp.ok:
        print(
            f"Failed to publish to Notion (status {resp.status_code}): {data}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return data


__all__ = ["publish_analysis_to_notion", "build_properties"]

