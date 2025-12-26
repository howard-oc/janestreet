# Notion Feedback Loop Integration

## Overview

Your Notion database now stores **Status** and **Reason** columns where you can provide feedback on each analysis. This feedback is synced back to Pinecone so the LLM can learn from your decisions over time.

## 🎯 How It Works

### 1. **Analysis Published to Notion**
When you run `janestreet.py`:
```
Title: "Japan 225 Analysis - 2025-12-26 17:30 UTC - 1 Order(s) (BUY)"
Status: Pending (default)
Reason: (empty - you fill this)
PineconeID: analysis_2025-12-26T17-30-45-123456+00-00
```

### 2. **You Add Feedback in Notion**
Open the page and update:
- **Status**: Select from dropdown (Accepted, Rejected, Modified, etc.)
- **Reason**: Write why you made this decision

Example:
```
Status: Rejected
Reason: I dont think we need to close, I believe the market will correct lower
```

### 3. **Sync Feedback to Pinecone**
Run the sync script:
```bash
NOTION_SECOND_BRAIN_TOKEN=... \
PINECONE_API_KEY=... \
NOTION_SECOND_BRAIN_DB_ID=... \
uv run python sync_notion_feedback_complete.py
```

### 4. **LLM Learns from Feedback**
Next time you run `janestreet.py`, the RAG system will include your feedback:
```json
{
  "rag_top_news": [
    {
      "type": "analysis",
      "headline": "Japan 225 Analysis - 2025-12-26...",
      "user_status": "Rejected",
      "user_feedback": "I dont think we need to close...",
      "score": 0.92
    }
  ]
}
```

The LLM will see that you rejected similar recommendations before and adjust accordingly!

## 📊 Notion Database Setup

### Required Columns

| Column | Type | Purpose |
|--------|------|---------|
| **Name** | Title | Analysis title with timestamp |
| **Tags** | Multi-select | Japan225, Gemini, SecondBrain |
| **PublishedDate** | Date | When analysis was created |
| **Status** | Select | Your decision (Accepted/Rejected/Modified/Pending) |
| **Reason** | Rich Text | Your explanation/feedback |
| **PineconeID** | Rich Text | Link to Pinecone vector (auto-filled) |

### Setting Up Status Options

In your Notion database, click **Status** column → **Edit property**:

Add these options:
- ✅ **Accepted** - You followed the recommendation
- ❌ **Rejected** - You disagreed with the recommendation
- 🔄 **Modified** - You took a modified version
- ⏳ **Pending** - Not yet decided (default)
- 🎯 **Executed** - Order was placed
- 📊 **Reviewing** - Still analyzing

Choose colors that make sense for you!

## 🔄 Workflow

### Daily Routine

#### Morning: Generate Analysis
```bash
# Run analysis
uv run python janestreet.py > janestreet_$(date +%Y%m%d).json

# Check Notion for new analysis page
```

#### During Day: Add Feedback
1. Open Notion page
2. Set **Status** (Accepted/Rejected/etc)
3. Write **Reason** explaining your decision
4. Save

#### Evening: Sync Feedback
```bash
# Sync all feedback to Pinecone
uv run python sync_notion_feedback_complete.py
```

#### Next Morning: LLM Learns
Next analysis will include your previous feedback in the context!

## 📈 Example Feedback Loop

### Day 1 - LLM Recommends
```json
{
  "Direction": "sell",
  "TriggerPrice": 50800,
  "Reason": "Overbought conditions, RSI > 70"
}
```

**Your Feedback:**
```
Status: Rejected
Reason: Market momentum still strong, expecting continuation to 51000
```

### Day 2 - LLM Sees Feedback
When generating today's analysis, RAG retrieves:
```json
{
  "past_analysis": "Recommended SELL at 50800",
  "user_status": "Rejected",
  "user_feedback": "Market momentum still strong...",
  "actual_outcome": "Price went to 51200"
}
```

**New Recommendation:**
```json
{
  "Direction": "buy",
  "TriggerPrice": 51000,
  "Reason": "Strong momentum continuing as you predicted. Previous sell signal was premature."
}
```

The LLM learned from your feedback! 🎯

## 🔍 Querying Feedback in Pinecone

### View Analyses with Feedback

```python
from pinecone import Pinecone

pc = Pinecone(api_key="...")
index = pc.Index("japan225-news-vectors")

# Query for rejected recommendations
results = index.query(
    vector=query_embedding,
    top_k=10,
    filter={
        "type": "analysis",
        "user_status": "Rejected"
    },
    include_metadata=True
)

for match in results.matches:
    print(f"Analysis: {match.metadata['generated_at']}")
    print(f"Status: {match.metadata['user_status']}")
    print(f"Feedback: {match.metadata['user_feedback']}")
    print("---")
```

### Track Accuracy Over Time

```python
# Get all analyses with outcomes
accepted = index.query(
    vector=query_embedding,
    filter={"user_status": "Accepted"},
    top_k=100
)

rejected = index.query(
    vector=query_embedding,
    filter={"user_status": "Rejected"},
    top_k=100
)

print(f"Accepted: {len(accepted.matches)}")
print(f"Rejected: {len(rejected.matches)}")
print(f"Accuracy: {len(accepted.matches) / (len(accepted.matches) + len(rejected.matches)) * 100:.1f}%")
```

## 🎨 Customizing Status Options

Edit your Notion database to add custom statuses:

- 💰 **Profitable** - Trade was successful
- 📉 **Loss** - Trade resulted in loss
- ⚠️ **Risk-Off** - Decided not to trade due to risk
- 🔄 **Scaled** - Adjusted position size
- 🎯 **Partial** - Took partial position

Each status helps the LLM understand your decision-making process!

## 📊 Feedback Analytics Dashboard

Create a Notion view to track your feedback:

### By Status
- Filter: Status = "Accepted" → See what worked
- Filter: Status = "Rejected" → See what didn't
- Chart: Count by Status

### By Month
- Group by: PublishedDate (Month)
- Show: Status distribution over time

### By Direction
- Filter: Extract direction from title
- Compare: BUY vs SELL acceptance rate

## ⚡ Automation Ideas

### Auto-Sync with Cron
```bash
# Add to crontab
0 */6 * * * cd /path/to/project && uv run python sync_notion_feedback_complete.py
```

Syncs feedback every 6 hours automatically!

### Slack Notifications
When you add feedback, send a Slack message:
```python
import requests

def notify_slack(title, status, reason):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    requests.post(webhook_url, json={
        "text": f"📊 Feedback Added\n{title}\nStatus: {status}\nReason: {reason}"
    })
```

## 🐛 Troubleshooting

### "No feedback to sync"
- Check if Status or Reason columns have values
- Verify PineconeID column exists and is populated
- Make sure pages have "Japan225" tag

### "PineconeID is empty"
- Old analyses won't have PineconeID
- Run janestreet.py again to generate new analyses
- Or manually copy ID from Pinecone query results

### "Failed to sync"
- Verify PINECONE_API_KEY is correct
- Check Pinecone index name matches
- Ensure PineconeID exactly matches a vector

## 📝 Best Practices

1. **Be Specific** - Instead of "Bad idea", write "RSI indicator conflicted with price action"
2. **Include Outcomes** - "Rejected. Price moved as predicted, saved -300 points"
3. **Consistent Statuses** - Use same status values consistently
4. **Update Promptly** - Add feedback while market context is fresh
5. **Sync Regularly** - Run sync daily or automated

## 🚀 Advanced: Custom Feedback Metrics

Add custom columns to track:
- **Outcome** (number): Actual P&L in points
- **Confidence** (select): How confident you were
- **MarketCondition** (select): Market state when decided

Then sync these to Pinecone for even richer context!

## 🎯 Result

Over time, the LLM will:
- ✅ Recognize patterns you accept/reject
- 📈 Adjust to your risk tolerance
- 🎯 Make recommendations that align with your style
- 🧠 Learn from your expertise

**Your feedback makes the AI better at helping you!** 🚀
