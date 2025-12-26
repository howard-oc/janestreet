"""query_historical_analysis.py

Query and compare historical Japan 225 analyses stored in Pinecone.

This script retrieves analyses from Pinecone and displays them chronologically
to show how trading recommendations evolved over time.

Usage:
    PINECONE_API_KEY=... OPENAI_API_KEY=... uv run python query_historical_analysis.py

Options:
    --days N        Show analyses from last N days (default: 7)
    --limit N       Maximum number of analyses to retrieve (default: 20)
    --full          Show full analysis text (default: preview only)
    --compare       Compare recommendations side-by-side
"""

import os
import sys
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Optional
import json

try:
    from pinecone import Pinecone
except ImportError:
    print("Error: pinecone-client not installed. Run: uv add pinecone-client")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai not installed. Run: uv add openai")
    sys.exit(1)


def init_pinecone() -> Optional[Pinecone]:
    """Initialize Pinecone client."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("Error: PINECONE_API_KEY not set")
        return None
    
    try:
        pc = Pinecone(api_key=api_key)
        return pc
    except Exception as exc:
        print(f"Error initializing Pinecone: {exc}")
        return None


def generate_query_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for query text."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]
        )
        return response.data[0].embedding
    except Exception as exc:
        print(f"Error generating embedding: {exc}")
        return None


def query_all_analyses(
    pinecone_client,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Query all analyses from Pinecone by filtering on type=analysis.
    
    Args:
        pinecone_client: Initialized Pinecone client
        limit: Maximum number of results to return
        
    Returns:
        List of analysis records sorted by date (newest first)
    """
    if pinecone_client is None:
        return []
    
    try:
        index_name = os.getenv("PINECONE_INDEX_NAME", "japan225-news-vectors")
        index = pinecone_client.Index(index_name)
        
        # Query with a generic embedding to get all analyses
        # We'll filter by metadata type="analysis"
        query_text = "Japan 225 trading analysis market recommendation"
        query_embedding = generate_query_embedding(query_text)
        
        if query_embedding is None:
            return []
        
        # Query with metadata filter
        results = index.query(
            vector=query_embedding,
            top_k=limit,
            include_metadata=True,
            filter={"type": {"$eq": "analysis"}}
        )
        
        analyses = []
        for match in results.matches:
            metadata = match.metadata or {}
            
            # Parse the timestamp
            generated_at = metadata.get("generated_at", "")
            try:
                dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except:
                dt = None
            
            analyses.append({
                "id": match.id,
                "score": float(match.score),
                "generated_at": generated_at,
                "datetime": dt,
                "latest_close": metadata.get("latest_close"),
                "preview": metadata.get("analysis_preview", "")[:200],
                "headline_count": metadata.get("headline_count", 0),
                "has_positions": metadata.get("has_positions", False),
                "market_id": metadata.get("market_id"),
            })
        
        # Sort by datetime (newest first)
        analyses.sort(key=lambda x: x["datetime"] or datetime.min, reverse=True)
        
        return analyses
        
    except Exception as exc:
        print(f"Error querying analyses: {exc}")
        return []


def query_analyses_by_date(
    pinecone_client,
    days: int = 7,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Query analyses from the last N days.
    
    Args:
        pinecone_client: Initialized Pinecone client
        days: Number of days to look back
        limit: Maximum number of results
        
    Returns:
        List of analysis records
    """
    # Get all analyses and filter by date
    all_analyses = query_all_analyses(pinecone_client, limit=limit)
    
    cutoff_date = datetime.now(UTC) - timedelta(days=days)
    
    filtered = [
        a for a in all_analyses
        if a["datetime"] and a["datetime"] >= cutoff_date
    ]
    
    return filtered


def display_analysis_summary(analyses: List[Dict[str, Any]]) -> None:
    """Display a table summary of analyses."""
    if not analyses:
        print("No analyses found.")
        return
    
    print(f"\n{'='*80}")
    print(f"Found {len(analyses)} analyses")
    print(f"{'='*80}\n")
    
    for i, analysis in enumerate(analyses, 1):
        dt = analysis["datetime"]
        dt_str = dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "Unknown"
        
        print(f"{i}. {dt_str}")
        print(f"   ID: {analysis['id']}")
        print(f"   Latest Close: {analysis['latest_close']}")
        print(f"   Headlines: {analysis['headline_count']}")
        print(f"   Has Positions: {analysis['has_positions']}")
        print(f"   Preview: {analysis['preview']}...")
        print()


def display_full_analysis(analysis_id: str, pinecone_client) -> None:
    """Fetch and display full analysis text.
    
    Note: The full analysis is stored in the vector embedding, not metadata.
    To retrieve it, we would need to store it separately or fetch from the
    original janestreet.json output files.
    """
    print(f"\nFull analysis retrieval not yet implemented.")
    print(f"The analysis preview is stored in Pinecone metadata (200 chars).")
    print(f"Full analyses are in your janestreet.json output files.")
    print(f"\nTo implement full retrieval:")
    print(f"1. Store full analysis in a separate database (DuckDB)")
    print(f"2. Or store analysis_id -> file_path mapping")
    print(f"3. Or increase Pinecone metadata size limit")


def compare_analyses(analyses: List[Dict[str, Any]]) -> None:
    """Compare recommendations across multiple analyses."""
    if len(analyses) < 2:
        print("Need at least 2 analyses to compare.")
        return
    
    print(f"\n{'='*80}")
    print("COMPARISON: Price Movement Over Time")
    print(f"{'='*80}\n")
    
    print(f"{'Date':<20} {'Latest Close':<15} {'Change':<15} {'Headlines':<10}")
    print("-" * 80)
    
    prev_close = None
    for analysis in reversed(analyses):  # Show oldest to newest
        dt_str = analysis["datetime"].strftime("%Y-%m-%d %H:%M") if analysis["datetime"] else "Unknown"
        close = analysis["latest_close"]
        
        if close and prev_close:
            change = close - prev_close
            change_pct = (change / prev_close) * 100
            change_str = f"{change:+.1f} ({change_pct:+.2f}%)"
        else:
            change_str = "N/A"
        
        print(f"{dt_str:<20} {close or 'N/A':<15} {change_str:<15} {analysis['headline_count']:<10}")
        
        prev_close = close


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Query historical Japan 225 analyses from Pinecone")
    parser.add_argument("--days", type=int, default=7, help="Show analyses from last N days")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of analyses to retrieve")
    parser.add_argument("--full", action="store_true", help="Show full analysis text")
    parser.add_argument("--compare", action="store_true", help="Compare recommendations side-by-side")
    parser.add_argument("--id", type=str, help="Show specific analysis by ID")
    
    args = parser.parse_args()
    
    # Initialize Pinecone
    pc = init_pinecone()
    if pc is None:
        sys.exit(1)
    
    # Query analyses
    if args.id:
        display_full_analysis(args.id, pc)
    else:
        analyses = query_analyses_by_date(pc, days=args.days, limit=args.limit)
        
        if not analyses:
            print(f"No analyses found in the last {args.days} days.")
            sys.exit(0)
        
        display_analysis_summary(analyses)
        
        if args.compare:
            compare_analyses(analyses)
        
        if args.full:
            print("\nNote: Full analysis text is not stored in Pinecone metadata.")
            print("Check your janestreet.json output files for complete analyses.")


if __name__ == "__main__":
    main()
