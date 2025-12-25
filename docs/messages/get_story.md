# GetStory

## Overview

`GetStory` retrieves the full detail for a specific news story identified by
its `storyID`.
Use this after obtaining a `StoryId` from one of the headlines or news list
endpoints (for example `GetNewsHeadlines`, `GetMarketReportHeadlines`,
`GetNews`).

The response is returned as a `StoryResponseDTO` in JSON format.

---

## Endpoint

- **Service**: `news`  
- **Method**: `GET`  
- **URI**: `/TradingAPI/news/story`  
- **Transport**: HTTP / HTTPS  
- **Envelope**: URL  
- **Content type**: `application/json`  
- **Return type**: `StoryResponseDTO`  

Live environment base URL:

- `https://ciapi.cityindex.com`

Full example URL:

- `https://ciapi.cityindex.com/TradingAPI/news/story`

Authentication (`username`, `session`) is required and is supplied as HTTP
headers in this project.

---

## Request

### Query parameters

- `storyID` (integer, required)  
  The identifier of the news story to retrieve in full.

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
  - `200 OK` – story found and returned.
  - `4xx/5xx` – validation, authentication or server errors.

- **Body**: `StoryResponseDTO` JSON. A typical shape is:

```json
{
  "Story": {
    "StoryId": 9483,
    "Headline": "Example headline",
    "PublishDate": "/Date(1766578594028)/",
    "Body": "Full story text ...",
    "Region": "FX",
    "Source": "Reuters",
    "Provider": 1
  }
}
```

Exact fields depend on the StoneX schema; the important part is that the full
story body and associated metadata are returned.

---

## Example – Retrieve a specific story

Retrieve the story details for story ID `9483`.

### HTTP

```http
GET https://ciapi.cityindex.com/TradingAPI/news/story?storyID=9483
username: {UserName}
session: {SessionToken}
Accept: application/json
```

### cURL

```bash
curl -sS \
  "https://ciapi.cityindex.com/TradingAPI/news/story?storyID=9483" \
  -H "username: ${CITYINDEX_USERNAME}" \
  -H "session: ${CITYINDEX_SESSION}" \
  -H "Accept: application/json"
```

A successful request returns `HTTP 200` and a `StoryResponseDTO` containing the
full market news story for the given `storyID`.

---

_Last updated to match StoneX reference: 23 July 2024._
