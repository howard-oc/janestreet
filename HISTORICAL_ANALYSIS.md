# Historical Analysis Tracking with Pinecone

## Overview

Every time you run `janestreet.py`, the Gemini analysis is automatically stored in Pinecone with metadata including:
- Timestamp
- Latest closing price
- Number of news headlines analyzed
- Order recommendations (count, direction, quantity)
- Whether you had open positions
- Analysis preview (first 1000 characters)

## Viewing Historical Analyses

### Quick View (Last 7 Days)

```bash
PINECONE_API_KEY=... OPENAI_API_KEY=... uv run python query_historical_analysis.py
```

**Output:**
```
================================================================================
Found 5 analyses
================================================================================

1. 2025-12-26 15:51 UTC
   ID: analysis_2025-12-26T15-51-43-388495+00-00
   Latest Close: 50570.0
   Headlines: 30
   Has Positions: False
   Orders: 2 (BUY)
   Preview: ## 1. PnL Summary Currently no open positions...

2. 2025-12-26 10:30 UTC
   ID: analysis_2025-12-26T10-30-15-123456+00-00
   Latest Close: 50420.0
   Headlines: 28
   Has Positions: True
   Orders: 1 (SELL)
   Preview: ## 1. PnL Summary Existing long position showing...
```

### Custom Date Range

```bash
# Last 30 days
uv run python query_historical_analysis.py --days 30

# Last 3 days, max 10 results
uv run python query_historical_analysis.py --days 3 --limit 10
```

### Compare Over Time

```bash
uv run python query_historical_analysis.py --days 14 --compare
```

**Output:**
```
================================================================================
COMPARISON: Price Movement Over Time
================================================================================

Date                 Latest Close    Change          Headlines
--------------------------------------------------------------------------------
2025-12-12 09:15     49850.0        N/A             25
2025-12-13 09:20     50100.0        +250.0 (+0.50%) 28
2025-12-14 09:18     50300.0        +200.0 (+0.40%) 32
2025-12-15 09:25     50150.0        -150.0 (-0.30%) 27
2025-12-16 09:22     50420.0        +270.0 (+0.54%) 30
2025-12-26 15:51     50570.0        +150.0 (+0.30%) 30
```

## What's Stored in Pinecone

### Metadata Fields

```json
{
  "id": "analysis_2025-12-26T15-51-43-388495+00-00",
  "type": "analysis",
  "generated_at": "2025-12-26T15:51:43.388495+00:00",
  "market_id": 400616391,
  "latest_close": 50570.0,
  "headline_count": 30,
  "has_positions": false,
  "order_count": 2,
  "primary_direction": "buy",
  "total_quantity": 2.42,
  "has_orders": true,
  "analysis_preview": "## 1. PnL Summary\n\nCurrently no open..."
}
```

### Vector Embedding

The full analysis text is embedded as a 1536-dimensional vector, allowing semantic search across all your historical analyses.

## Semantic Search Across Analyses

### Find analyses about specific topics

```python
from pinecone import Pinecone
from openai import OpenAI
import os

# Initialize
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("japan225-news-vectors")

# Generate query embedding
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
query = "analyses where I recommended selling due to overbought conditions"
response = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=query
)
query_vector = response.data[0].embedding

# Search
results = index.query(
    vector=query_vector,
    top_k=5,
    include_metadata=True,
    filter={"type": {"$eq": "analysis"}}
)

# View results
for match in results.matches:
    print(f"Score: {match.score}")
    print(f"Date: {match.metadata['generated_at']}")
    print(f"Direction: {match.metadata.get('primary_direction')}")
    print(f"Close: {match.metadata['latest_close']}")
    print(f"Preview: {match.metadata['analysis_preview'][:200]}")
    print("---")
```

## Analysis Over Time Dashboard

### Track Price vs Recommendations

```python
import json
from datetime import datetime
import matplotlib.pyplot as plt

# Query all analyses
analyses = query_analyses_by_date(pc, days=30, limit=100)

# Extract data
dates = [datetime.fromisoformat(a['generated_at']) for a in analyses]
prices = [a['latest_close'] for a in analyses]
buy_dates = [datetime.fromisoformat(a['generated_at']) 
             for a in analyses if a.get('primary_direction') == 'buy']
sell_dates = [datetime.fromisoformat(a['generated_at']) 
              for a in analyses if a.get('primary_direction') == 'sell']

# Plot
plt.figure(figsize=(14, 7))
plt.plot(dates, prices, 'b-', label='Japan 225 Close')
plt.scatter(buy_dates, [prices[dates.index(d)] for d in buy_dates], 
            c='green', marker='^', s=100, label='BUY Signal')
plt.scatter(sell_dates, [prices[dates.index(d)] for d in sell_dates], 
            c='red', marker='v', s=100, label='SELL Signal')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('Japan 225: Price Action vs Trading Signals')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

## Export Historical Data

### Export to CSV

```python
import csv
from datetime import datetime

analyses = query_analyses_by_date(pc, days=30, limit=100)

with open('historical_analyses.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Date', 'Latest Close', 'Direction', 'Order Count', 
        'Total Quantity', 'Headlines', 'Has Positions'
    ])
    
    for a in analyses:
        writer.writerow([
            a['generated_at'],
            a['latest_close'],
            a.get('primary_direction', 'N/A'),
            a.get('order_count', 0),
            a.get('total_quantity', 0),
            a['headline_count'],
            a['has_positions']
        ])

print("Exported to historical_analyses.csv")
```

### Export to JSON

```python
import json

analyses = query_analyses_by_date(pc, days=30, limit=100)

with open('historical_analyses.json', 'w') as f:
    json.dump(analyses, f, indent=2, default=str)

print("Exported to historical_analyses.json")
```

## Backtesting Your Signals

### Calculate Signal Performance

```python
def calculate_signal_performance(analyses):
    """Calculate how profitable your signals would have been."""
    
    performance = []
    
    for i in range(len(analyses) - 1):
        current = analyses[i]
        next_analysis = analyses[i + 1]
        
        if current.get('primary_direction') == 'buy':
            entry_price = current['latest_close']
            exit_price = next_analysis['latest_close']
            pnl = exit_price - entry_price
            pnl_pct = (pnl / entry_price) * 100
            
            performance.append({
                'date': current['generated_at'],
                'direction': 'BUY',
                'entry': entry_price,
                'exit': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct
            })
        
        elif current.get('primary_direction') == 'sell':
            entry_price = current['latest_close']
            exit_price = next_analysis['latest_close']
            pnl = entry_price - exit_price  # Reversed for short
            pnl_pct = (pnl / entry_price) * 100
            
            performance.append({
                'date': current['generated_at'],
                'direction': 'SELL',
                'entry': entry_price,
                'exit': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct
            })
    
    # Calculate statistics
    total_trades = len(performance)
    winning_trades = len([p for p in performance if p['pnl'] > 0])
    total_pnl = sum(p['pnl'] for p in performance)
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
    
    print(f"\n=== BACKTEST RESULTS ===")
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades} ({winning_trades/total_trades*100:.1f}%)")
    print(f"Total PnL: {total_pnl:.2f} points")
    print(f"Average PnL per Trade: {avg_pnl:.2f} points")
    
    return performance

# Usage
analyses = query_analyses_by_date(pc, days=30, limit=100)
performance = calculate_signal_performance(analyses)
```

## Integration with DuckDB

For more comprehensive historical tracking, you can also log analyses to DuckDB:

```python
import duckdb

# Create table for historical analyses
con = duckdb.connect('data/stonex_meta.duckdb')
con.execute("""
    CREATE TABLE IF NOT EXISTS historical_analyses (
        analysis_id TEXT PRIMARY KEY,
        generated_at TIMESTAMP,
        latest_close FLOAT,
        order_count INTEGER,
        primary_direction TEXT,
        total_quantity FLOAT,
        headline_count INTEGER,
        has_positions BOOLEAN,
        full_analysis TEXT,
        pinecone_id TEXT
    )
""")

# Insert after each run
con.execute("""
    INSERT INTO historical_analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", [
    context['generated_at_utc'],
    context['generated_at_utc'],
    latest_close,
    order_count,
    primary_direction,
    total_quantity,
    headline_count,
    has_positions,
    analysis_md,
    pinecone_id
])
```

## Query Examples

### Find all SELL signals
```bash
python -c "
from query_historical_analysis import *
pc = init_pinecone()
index = pc.Index('japan225-news-vectors')
results = index.query(
    vector=generate_query_embedding('sell signal'),
    top_k=20,
    filter={'type': 'analysis', 'primary_direction': 'sell'},
    include_metadata=True
)
for r in results.matches:
    print(r.metadata['generated_at'], r.metadata['latest_close'])
"
```

### Find analyses with multiple orders
```bash
python -c "
from query_historical_analysis import *
pc = init_pinecone()
index = pc.Index('japan225-news-vectors')
# Query for analyses with order_count > 1
# Note: Pinecone doesn't support > filter, so query all and filter locally
"
```

## Tips

1. **Run daily** to build a comprehensive history
2. **Compare patterns** before similar market conditions
3. **Track signal accuracy** to improve prompts
4. **Export regularly** for offline analysis
5. **Use semantic search** to find similar setups

## Cost Tracking

Pinecone free tier includes:
- 100,000 vectors
- 1 serverless index

At 1 analysis/day, you can store:
- ~270+ years of daily analyses
- Plus all news items

More than enough for trading analysis! 📊
