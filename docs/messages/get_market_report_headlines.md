# GetMarketReportHeadlines

## Overview

`GetMarketReportHeadlines` retrieves a list of current news headlines for a
specific market. This is useful for attaching news context to a particular
instrument (for example, GBP/USD or Japan 225).

The response is returned as a `NewsHeadlinesResponseDTO` in JSON format.

---

## Endpoint

- **Service**: `news`
- **Method**: `GET`
- **URI**: `/TradingAPI/news/marketreportheadlines`
- **Transport**: HTTP / HTTPS
- **Envelope**: URL
- **Content type**: `application/json`
- **Return type**: `NewsHeadlinesResponseDTO`

Live environment example base URL:

- `https://ciapi.cityindex.com`

Full example URL:

- `https://ciapi.cityindex.com/TradingAPI/news/marketreportheadlines`

Authentication (`username`, `session`) is required and is supplied as HTTP
headers in this project.

---

## Request

### Query parameters

- `marketID` (integer, required)
  - Unique identifier for the market to retrieve headlines for.
  - Example: `401166448` for GBP/USD.

- `cultureId` (integer, required)
  - Culture (language) identifier for the headlines.
  - Example: `69` for English.

- `maxResults` (integer, optional; default `25`, min `1`, max `500`)
  - Maximum number of news stories to return.

### Headers

- `username` – City Index username used to authenticate the session.
- `session` – Session token obtained from `LogOn v2`.
- `Accept: application/json` (optional but recommended).

### Body

- None – this is a `GET` request; all parameters are supplied in the query
  string.

---

## Response

- **HTTP status**:
  - `200 OK` – request succeeded and headlines were returned.
  - `4xx/5xx` – error conditions (validation, authentication, server error,
    and so on).

- **Body**: `NewsHeadlinesResponseDTO` JSON, for example:

```json path=null start=null
{
  "Headlines": [
    {
      "StoryId": "urn:newsml:reuters.com:20251224:nL1N3XU08F",
      "Headline": "Sterling steady near multi-month highs, BoE caution still top of mind ",
      "PublishDate": "/Date(1766578594028)/",
      "Provider": 1
    },
    {
      "StoryId": "...",
      "Headline": "...",
      "PublishDate": "...",
      "Provider": 1
    }
  ]
}
```

The `Headlines` array may be empty if there are no current stories for the
specified market.

---

## Example – GBP/USD headlines

Retrieve the most recent 20 English-language headlines for the GBP/USD market
(`marketID = 401166448`, `cultureId = 69`).

### HTTP

```http path=null start=null
GET https://ciapi.cityindex.com/TradingAPI/news/marketreportheadlines?marketID=401166448&cultureId=69&maxResults=20
username: {UserName}
session: {SessionToken}
Accept: application/json
```

### cURL

```bash path=null start=null
curl -sS \
  "https://ciapi.cityindex.com/TradingAPI/news/marketreportheadlines?marketID=401166448&cultureId=69&maxResults=20" \
  -H "username: ${CITYINDEX_USERNAME}" \
  -H "session: ${CITYINDEX_SESSION}" \
  -H "Accept: application/json"
```

Example of a first headline (from a successful test call):

```json path=null start=null
{
  "StoryId": "urn:newsml:reuters.com:20251224:nL1N3XU08F",
  "Headline": "Sterling steady near multi-month highs, BoE caution still top of mind ",
  "PublishDate": "/Date(1766578594028)/",
  "Provider": 1
}
```

This confirms that the news API is working and returning current market
headlines for the specified instrument.
