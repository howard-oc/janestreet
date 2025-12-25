# GetNewsHeadlines

## Overview

`GetNewsHeadlines` retrieves a list of current **news headlines** for a
specified region (for example FX, UK, AUS, SING).
Use this when you want lightweight headlines rather than full story bodies.

The response is returned as a `NewsHeadlinesResponseDTO` in JSON format.

---

## Endpoint

- **Service**: `news`  
- **Method**: `GET`  
- **URI**: `/TradingAPI/news/newsheadlines`  
- **Transport**: HTTP / HTTPS  
- **Envelope**: URL  
- **Content type**: `application/json`  
- **Return type**: `NewsHeadlinesResponseDTO`  

Live environment base URL:

- `https://ciapi.cityindex.com`

Full example URL:

- `https://ciapi.cityindex.com/TradingAPI/news/newsheadlines`

Authentication (`username`, `session`) is required and is supplied as HTTP
headers in this project.

---

## Request

### Query parameters

- `region` (string, required)  
  Region to retrieve headlines for. Known values include:
  - `FX`
  - `UK`
  - `AUS`
  - `SING`

- `cultureId` (integer, required)  
  Culture (language) identifier for the headlines.  
  Example: `69` for English.

- `maxResults` (integer, optional; default `25`, min `1`, max `500`)  
  Maximum number of headlines to return.

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
  - `4xx/5xx` – validation, authentication or server errors.

- **Body**: `NewsHeadlinesResponseDTO` JSON, for example:

```json
{
  "Headlines": [
    {
      "StoryId": "urn:newsml:reuters.com:20251224:nL1N3XU08F",
      "Headline": "Sterling steady near multi-month highs, BoE caution still top of mind ",
      "PublishDate": "/Date(1766578594028)/",
      "Provider": 1
    }
  ]
}
```

The `Headlines` array may be empty if there are no current stories for the
selected region.

---

## Example – FX headlines in English

Retrieve the most recent 20 English-language FX headlines.

### HTTP

```http
GET https://ciapi.cityindex.com/TradingAPI/news/newsheadlines?region=FX&cultureId=69&maxResults=20
username: {UserName}
session: {SessionToken}
Accept: application/json
```

### cURL

```bash
curl -sS \
  "https://ciapi.cityindex.com/TradingAPI/news/newsheadlines?region=FX&cultureId=69&maxResults=20" \
  -H "username: ${CITYINDEX_USERNAME}" \
  -H "session: ${CITYINDEX_SESSION}" \
  -H "Accept: application/json"
```

A successful request returns `HTTP 200` and a `NewsHeadlinesResponseDTO`
containing the current FX headlines for the specified culture.

---

_Last updated to match StoneX reference: 23 July 2024._
