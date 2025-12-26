# Pinecone Integration Setup

## What's Been Added

The updated `janestreet.py` now:

1. ✅ **Creates Pinecone index automatically** if it doesn't exist
2. ✅ **Generates embeddings** using OpenAI's `text-embedding-3-small` model
3. ✅ **Uploads news items** to Pinecone with vector embeddings
4. ✅ **Uploads Gemini analysis** to Pinecone for future retrieval
5. ✅ **Queries Pinecone** for similar historical news and analyses

## Required Dependencies

### Install OpenAI SDK
```bash
uv add openai
```

### Install Pinecone (already done)
```bash
uv add pinecone-client
```

## Environment Variables

You need to set these environment variables:

### Required
```bash
export PINECONE_API_KEY="your_pinecone_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

### Optional (with defaults)
```bash
export PINECONE_INDEX_NAME="japan225-news-vectors"  # Default: japan225-news-vectors
export PINECONE_CLOUD="aws"                         # Default: aws
export PINECONE_REGION="us-east-1"                  # Default: us-east-1
export PINECONE_ENVIRONMENT="us-east-1-aws"         # For metadata only
```

## How to Get API Keys

### Pinecone API Key
1. Go to https://www.pinecone.io/
2. Sign up for a free account
3. Navigate to "API Keys" in your project
4. Copy your API key

### OpenAI API Key
1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to "API Keys"
4. Create a new secret key
5. Copy the key (you won't be able to see it again)

## What Gets Uploaded to Pinecone

### 1. News Items
Each news headline/story is uploaded with:
- **ID**: `news_{story_id}`
- **Vector**: Embedding of headline + summary
- **Metadata**:
  - `story_id`: Original story ID
  - `headline`: News headline (max 500 chars)
  - `publish_ts`: Publication timestamp
  - `summary`: Story summary (max 1000 chars)
  - `type`: "news"

### 2. Gemini Analysis
Each daily analysis is uploaded with:
- **ID**: `analysis_{timestamp}`
- **Vector**: Embedding of full markdown analysis
- **Metadata**:
  - `type`: "analysis"
  - `generated_at`: UTC timestamp
  - `market_id`: Japan 225 market ID
  - `latest_close`: Latest closing price
  - `analysis_preview`: First 1000 chars of analysis
  - `headline_count`: Number of news items analyzed
  - `has_positions`: Boolean indicating if positions exist

## Running the Script

### Full Command
```bash
CITYINDEX_USERNAME=your_username \
CITYINDEX_PASSWORD=your_password \
CITYINDEX_APPKEY=your_appkey \
PINECONE_API_KEY=your_pinecone_key \
OPENAI_API_KEY=your_openai_key \
GOOGLE_GEMINI_API_KEY=your_gemini_key \
uv run python janestreet.py > janestreet.json
```

### What Happens

1. Script fetches latest Japan 225 news
2. Generates embeddings for each news item using OpenAI
3. Creates Pinecone index if it doesn't exist (first run only)
4. Uploads news vectors to Pinecone
5. Runs Gemini analysis on the context
6. Generates embedding for the Gemini analysis
7. Uploads analysis vector to Pinecone
8. Outputs full context JSON including Pinecone stats

## Expected Output

You should see logs like:
```
Pinecone client initialized successfully
Pinecone index 'japan225-news-vectors' already exists (or created)
Upserted 30 news vectors to Pinecone
Uploaded analysis to Pinecone with ID: analysis_2025-12-26T15-30-45-123456Z
```

## Costs

### OpenAI (text-embedding-3-small)
- $0.02 per 1 million tokens
- ~30 news items ≈ 15,000 tokens ≈ $0.0003 per run
- Very cheap!

### Pinecone (Free Tier)
- 1 free starter index (serverless)
- Up to 100,000 vectors
- Should be sufficient for daily runs

## Querying Your Data

The script automatically queries Pinecone when running to find similar historical news/analyses. Results appear in the output JSON under `rag_top_news` with `"source": "pinecone"`.

## Troubleshooting

### "Resource not found" error
- Index doesn't exist yet (will be auto-created on first run)
- Check your Pinecone API key is correct

### "Embedding generation failed"
- Check your OpenAI API key is set: `echo $OPENAI_API_KEY`
- Verify you have credits in your OpenAI account

### Index creation takes time
- First run may take 30-60 seconds to create the index
- Subsequent runs will be much faster

## Example: Querying Pinecone Manually

```python
from pinecone import Pinecone
from openai import OpenAI

# Initialize
pc = Pinecone(api_key="your_key")
index = pc.Index("japan225-news-vectors")

# Generate query embedding
openai_client = OpenAI(api_key="your_key")
query = "What happened with BoJ policy last week?"
response = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=query
)
query_vector = response.data[0].embedding

# Search
results = index.query(
    vector=query_vector,
    top_k=5,
    include_metadata=True
)

# View results
for match in results.matches:
    print(f"Score: {match.score}")
    print(f"Headline: {match.metadata['headline']}")
    print(f"Type: {match.metadata['type']}")
    print("---")
```

## Next Steps

1. **Install OpenAI**: `uv add openai`
2. **Get API keys** from Pinecone and OpenAI
3. **Set environment variables**
4. **Run the script** - it will auto-create the index
5. **Check the JSON output** for `pinecone_analysis_upload` stats
