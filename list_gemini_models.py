"""
List available Gemini models for the current project and show which support generateContent.

Usage:
    GOOGLE_GEMINI_API_KEY=... uv run python list_gemini_models.py
"""

import os
import sys

import google.genai as genai


def main() -> None:
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        print("GOOGLE_GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print("Listing Gemini models visible to this project:")
    print("-" * 80)

    # v1beta ListModels
    for model in client.models.list():
        # `model` can be a Pydantic model, attribute object, or plain dict depending on library version
        def _field(m, key, default=None):
            # Prefer attributes when available
            value = getattr(m, key, None)
            if value is not None:
                return value

            # Fallback for dict-like objects
            if isinstance(m, dict):
                return m.get(key, default)

            # Fallback for Pydantic models that expose `model_dump()`
            dump = getattr(m, "model_dump", None)
            if callable(dump):
                data = dump()
                if isinstance(data, dict):
                    return data.get(key, default)

            return default

        name = _field(model, "name", "<unknown>")
        display_name = _field(model, "display_name")
        supported_methods = _field(model, "supported_generation_methods", []) or []

        supports_generate_content = (
            "generateContent" in supported_methods or "generateText" in supported_methods
        )

        print(f"ID: {name}")
        if display_name:
            print(f"  Display name: {display_name}")
        print(f"  Supported methods: {supported_methods}")
        print(f"  Supports generateContent: {supports_generate_content}")
        print("-" * 80)


if __name__ == "__main__":
    main()
