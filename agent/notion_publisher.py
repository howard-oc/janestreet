"""Notion publishing helper for LLM analysis (SecondBrain integration).

This module provides a thin wrapper around the Notion API for sending
analysis output into a Notion database with proper markdown formatting.

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
import re
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


def _markdown_to_notion_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """Convert markdown text to Notion block format.
    
    Supports:
    - Headings (##, ###, ####)
    - Bullet lists (-, *)
    - Numbered lists (1., 2., etc)
    - Code blocks (```...```)
    - Bold (**text**)
    - Paragraphs
    """
    
    blocks: List[Dict[str, Any]] = []
    lines = markdown_text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            i += 1
            continue
        
        # Heading 2 (##)
        if stripped.startswith('## '):
            content = stripped[3:].strip()
            if content:  # Only add if not empty
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": _parse_inline_formatting(content)
                    }
                })
            i += 1
        
        # Heading 3 (###)
        elif stripped.startswith('### '):
            content = stripped[4:].strip()
            if content:
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": _parse_inline_formatting(content)
                    }
                })
            i += 1
        
        # Code block (```...```)
        elif stripped.startswith('```'):
            # Extract language if specified
            language = stripped[3:].strip() or "plain text"
            code_lines = []
            i += 1
            
            # Collect code lines until closing ```
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            code_content = '\n'.join(code_lines)
            if code_content.strip():  # Only add if not empty
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_content[:2000]}}],
                        "language": language if language in ["json", "python", "javascript", "bash", "sql"] else "plain text"
                    }
                })
            i += 1  # Skip closing ```
        
        # Bullet list (- or *)
        elif stripped.startswith('- ') or stripped.startswith('* '):
            content = stripped[2:].strip()
            if content:
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": _parse_inline_formatting(content)
                    }
                })
            i += 1
        
        # Numbered list (1., 2., etc)
        elif re.match(r'^\d+\.\s', stripped):
            content = re.sub(r'^\d+\.\s', '', stripped)
            if content:
                blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": _parse_inline_formatting(content)
                    }
                })
            i += 1
        
        # Regular paragraph
        else:
            if stripped:  # Only add non-empty paragraphs
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": _parse_inline_formatting(stripped)
                    }
                })
            i += 1
    
    return blocks


def _parse_inline_formatting(text: str) -> List[Dict[str, Any]]:
    """Parse inline markdown formatting (bold, code) into Notion rich text.
    
    Supports:
    - **bold**
    - `code`
    """
    
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    
    # Simple implementation: detect bold (**text**)
    # For production, consider using a proper markdown parser
    
    parts: List[Dict[str, Any]] = []
    
    # Split by bold markers
    bold_pattern = r'\*\*(.+?)\*\*'
    code_pattern = r'`(.+?)`'
    
    # Combine patterns
    combined_pattern = f'({bold_pattern}|{code_pattern})'
    
    current_pos = 0
    for match in re.finditer(combined_pattern, text):
        # Add text before match
        if match.start() > current_pos:
            plain_text = text[current_pos:match.start()]
            if plain_text:
                parts.append({
                    "type": "text",
                    "text": {"content": plain_text}
                })
        
        # Add formatted text
        matched_text = match.group(0)
        if matched_text.startswith('**') and matched_text.endswith('**'):
            # Bold text
            parts.append({
                "type": "text",
                "text": {"content": matched_text[2:-2]},
                "annotations": {"bold": True}
            })
        elif matched_text.startswith('`') and matched_text.endswith('`'):
            # Code text
            parts.append({
                "type": "text",
                "text": {"content": matched_text[1:-1]},
                "annotations": {"code": True}
            })
        
        current_pos = match.end()
    
    # Add remaining text
    if current_pos < len(text):
        remaining = text[current_pos:]
        if remaining:
            parts.append({
                "type": "text",
                "text": {"content": remaining}
            })
    
    # If no formatting found, return plain text
    if not parts:
        parts = [{"type": "text", "text": {"content": text}}]
    
    return parts


def _chunk_blocks(blocks: List[Dict[str, Any]], max_blocks: int = 100) -> List[List[Dict[str, Any]]]:
    """Chunk blocks into batches (Notion limit: 100 blocks per request)."""
    chunks = []
    for i in range(0, len(blocks), max_blocks):
        chunks.append(blocks[i:i + max_blocks])
    return chunks


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
        The analysis body in markdown format. Will be converted to Notion blocks.
    tags:
        Optional tags to set on the ``Tags`` multi_select property.
    properties_extra:
        Optional extra/override properties compatible with the Notion API.
    """

    headers = _build_headers()
    properties = build_properties(title=title, tags=tags, extra=properties_extra)

    # Convert markdown to Notion blocks
    children = _markdown_to_notion_blocks(analysis_markdown)
    
    # Notion has a 100-block limit per request, so we'll create the page first
    # then append remaining blocks if needed
    initial_children = children[:100]

    payload: Dict[str, Any] = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": initial_children,
    }

    # Create the page
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

    # Append remaining blocks if there are more than 100
    if len(children) > 100:
        page_id = data.get("id")
        remaining_chunks = _chunk_blocks(children[100:], max_blocks=100)
        
        for chunk in remaining_chunks:
            append_payload = {"children": chunk}
            append_resp = requests.patch(
                f"{NOTION_API_BASE}/blocks/{page_id}/children",
                headers=headers,
                json=append_payload,
                timeout=30,
            )
            
            if not append_resp.ok:
                print(
                    f"Warning: Failed to append blocks (status {append_resp.status_code})",
                    file=sys.stderr,
                )
                break

    return data


__all__ = ["publish_analysis_to_notion", "build_properties"]
