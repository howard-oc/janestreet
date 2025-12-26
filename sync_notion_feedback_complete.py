"""sync_notion_feedback_complete.py

Complete implementation: Sync user feedback from Notion to Pinecone.

This script reads Status and Reason columns from your Notion database and
updates the corresponding Pinecone vectors so future LLM analyses can learn
from your feedback.

Usage:
    NOTION_SECOND_BRAIN_TOKEN=... \
    PINECONE_API_KEY=... \
    NOTION_SECOND_BRAIN_DB_ID=... \
    uv run python sync_notion_feedback_complete.py

"""

import os
import sys
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

import requests

try:
    from pinecone import Pinecone
except ImportError:
    print("Error: pinecone-client not installed. Run: uv add pinecone-client")
    sys.exit(1)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def init_clients():
    """Initialize Notion headers and Pinecone client."""
    
    notion_token = os.getenv("NOTION_SECOND_BRAIN_TOKEN")
    pinecone_key = os.getenv("PINECONE_API_KEY")
    
    if not notion_token:
        print("Error: NOTION_SECOND_BRAIN_TOKEN not set")
        return None, None
    
    if not pinecone_key:
        print("Error: PINECONE_API_KEY not set")
        return None, None
    
    notion_headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    
    try:
        pc = Pinecone(api_key=pinecone_key)
        return notion_headers, pc
    except Exception as exc:
        print(f"Error initializing Pinecone: {exc}")
        return None, None


def get_notion_feedback(notion_headers: Dict[str, str], database_id: str) -> List[Dict[str, Any]]:
    """Query Notion database for all analyses with feedback.
    
    Returns:
        List of dicts with pinecone_id, status, reason, title
    """
    
    try:
        print("Querying Notion database...")
        
        # Query database using requests
        url = f"{NOTION_API_BASE}/databases/{database_id}/query"
        
        resp = requests.post(url, headers=notion_headers, json={}, timeout=30)
        
        if not resp.ok:
            print(f"Error: Notion API returned {resp.status_code}")
            print(f"Response: {resp.text}")
            return []
        
        results = resp.json()
        
        feedback_items = []
        
        for page in results.get("results", []):
            props = page.get("properties", {})
            
            # Check if page has Japan225 tag
            tags_prop = props.get("Tags", {}).get("multi_select", [])
            tags = [tag.get("name") for tag in tags_prop]
            
            if "Japan225" not in tags:
                continue
            
            # Extract title
            title_prop = props.get("Name", {}).get("title", [])
            title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""
            
            # Extract PineconeID
            pinecone_prop = props.get("PineconeID", {}).get("rich_text", [])
            pinecone_id = pinecone_prop[0].get("text", {}).get("content", "") if pinecone_prop else None
            
            # Extract Status (using 'status' type not 'select')
            status_prop = props.get("Status", {})
            # Try both 'status' and 'select' types
            if "status" in status_prop:
                status_obj = status_prop.get("status")
                status = status_obj.get("name") if status_obj else None
            elif "select" in status_prop:
                status_obj = status_prop.get("select")
                status = status_obj.get("name") if status_obj else None
            else:
                status = None
            
            # Extract Reason
            reason_prop = props.get("Reason", {}).get("rich_text", [])
            reason = reason_prop[0].get("text", {}).get("content", "") if reason_prop else ""
            
            # Only include if we have feedback and PineconeID
            if pinecone_id and (status or reason):
                feedback_items.append({
                    "pinecone_id": pinecone_id,
                    "title": title,
                    "status": status,
                    "reason": reason,
                })
            elif not pinecone_id and (status or reason):
                # Found feedback but no Pinecone ID
                print(f"  Warning: '{title[:50]}...' has feedback but no PineconeID")
        
        print(f"Found {len(feedback_items)} analyses with feedback\n")
        return feedback_items
        
    except Exception as exc:
        print(f"Error querying Notion: {exc}")
        import traceback
        traceback.print_exc()
        return []


def update_pinecone_metadata(
    pc: Pinecone,
    pinecone_id: str,
    status: Optional[str],
    reason: str
) -> bool:
    """Update Pinecone vector with user feedback metadata.
    
    Args:
        pc: Pinecone client
        pinecone_id: Exact vector ID
        status: User's status (Accepted, Rejected, etc)
        reason: User's feedback text
        
    Returns:
        True if successful
    """
    
    try:
        index_name = os.getenv("PINECONE_INDEX_NAME", "japan225-news-vectors")
        index = pc.Index(index_name)
        
        # Build metadata update
        metadata_update = {
            "user_status": status or "Unknown",
            "user_feedback": reason or "",
            "feedback_synced_at": datetime.now(UTC).isoformat(),
        }
        
        # Update the vector metadata
        index.update(
            id=pinecone_id,
            set_metadata=metadata_update
        )
        
        return True
        
    except Exception as exc:
        print(f"  Error updating Pinecone: {exc}")
        return False


def main():
    """Main sync function."""
    
    print("="*70)
    print("Syncing Notion Feedback to Pinecone")
    print("="*70)
    print()
    
    # Initialize clients
    notion_headers, pc = init_clients()
    if not notion_headers or not pc:
        sys.exit(1)
    
    # Get database ID
    db_id = os.getenv("NOTION_SECOND_BRAIN_DB_ID")
    if not db_id:
        print("Error: NOTION_SECOND_BRAIN_DB_ID not set")
        sys.exit(1)
    
    # Get feedback from Notion
    feedback_items = get_notion_feedback(notion_headers, db_id)
    
    if not feedback_items:
        print("No feedback to sync (analyses without Status/Reason are skipped)")
        print("\nTo add feedback:")
        print("1. Open Notion database")
        print("2. Set Status column (Accepted, Rejected, etc)")
        print("3. Add comments in Reason column")
        print("4. Run this script again")
        return
    
    # Sync each item
    print("Syncing feedback to Pinecone...\n")
    
    success_count = 0
    error_count = 0
    
    for item in feedback_items:
        print(f"Analysis: {item['title'][:60]}...")
        print(f"  Pinecone ID: {item['pinecone_id']}")
        print(f"  Status: {item['status']}")
        print(f"  Reason: {item['reason'][:100]}{'...' if len(item['reason']) > 100 else ''}")
        
        success = update_pinecone_metadata(
            pc,
            item['pinecone_id'],
            item['status'],
            item['reason']
        )
        
        if success:
            print("  ✓ Synced successfully")
            success_count += 1
        else:
            print("  ✗ Failed to sync")
            error_count += 1
        
        print()
    
    # Summary
    print("="*70)
    print(f"Sync Complete")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    print("="*70)
    
    if success_count > 0:
        print("\n✓ Feedback is now stored in Pinecone!")
        print("Next time you run janestreet.py, the LLM will see:")
        print("  - Your past status decisions (Accepted/Rejected)")
        print("  - Your reasoning for each decision")
        print("  - This helps improve future recommendations!")


if __name__ == "__main__":
    main()