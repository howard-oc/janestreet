# GetNews

## Overview

`GetNews` retrieves a list of current news stories for a specified **region**.
Use this when you want broad market or regional news (for example FX, UK, AUS,
SING), not tied to a single instrument.

The response is returned as a `NewsResponseDTO` in JSON format.

---

## Endpoint

- **Service**: `news`  
- **Method**: `GET`  
- **URI**: `/TradingAPI/news/news`  
- **Transport**: HTTP / HTTPS  
- **Envelope**: URL  
- **Content type**: `application/json`  
- **Return type**: `NewsResponseDTO`  

Live environment base URL:

- `https://ciapi.cityindex.com`

Full example URL:

- `https://ciapi.cityindex.com/TradingAPI/news/news`

Authentication (`username`, `session`) is required and is supplied as HTTP
headers in this project.

---

## Request

### Query parameters

- `region` (string, required)  
  The news region to retrieve stories for. Known values include:
  - `FX`
  - `UK`
  - `AUS`
  - `SING`

- `cultureId` (integer, required)  
  The culture (language) identifier for the stories.  
  Example: `69` for English.

- `maxResults` (integer, optional; default `25`, min `1`, max `500`)  
  Maximum number of news stories to return.

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
  - `200 OK` – request succeeded and stories were returned.
  - `4xx/5xx` – validation, authentication or server errors.

- **Body**: `NewsResponseDTO` JSON. A typical shape is:

```json
{
  "News": [
    {
      "StoryId": "urn:newsml:reuters.com:20251224:nL1N3XU08F",
      "Headline": "Sterling steady near multi-month highs, BoE caution still top of mind ",
      "PublishDate": "/Date(1766578594028)/",
      "Summary": "Short summary text (if provided)...",
      "Region": "FX",
      "Source": "Reuters",
      "Provider": 1
    }
  ]
}
```

The `News` array may be empty if there are currently no stories for the
requested region.

---

## Example – FX news in English

Retrieve the most recent 20 English-language news stories for the FX region.

### HTTP

```http
GET https://ciapi.cityindex.com/TradingAPI/news/news?region=FX&cultureId=69&maxResults=20
username: {UserName}
session: {SessionToken}
Accept: application/json
```

### cURL

```bash
curl -sS \
  "https://ciapi.cityindex.com/TradingAPI/news/news?region=FX&cultureId=69&maxResults=20" \
  -H "username: ${CITYINDEX_USERNAME}" \
  -H "session: ${CITYINDEX_SESSION}" \
  -H "Accept: application/json"
```

A successful request returns `HTTP 200` and a `NewsResponseDTO` containing the
current FX news stories for the specified culture.

---

_Last updated to match StoneX reference: 23 July 2024._
