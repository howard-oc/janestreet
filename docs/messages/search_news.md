# SearchNews

## Overview

`SearchNews` searches news within a specific **region** by headline and/or body
text.
Use this when you want to find regional stories (for example FX, UK, AUS,
SING) matching a particular keyword or phrase.

The response is returned as a `NewsResponseDTO` in JSON format.

---

## Endpoint

- **Service**: `news`  
- **Method**: `GET`  
- **URI**: `/TradingAPI/news/searchnews`  
- **Transport**: HTTP / HTTPS  
- **Envelope**: URL  
- **Content type**: `application/json`  
- **Return type**: `NewsResponseDTO`  

Live environment base URL:

- `https://ciapi.cityindex.com`

Full example URL:

- `https://ciapi.cityindex.com/TradingAPI/news/searchnews`

Authentication (`username`, `session`) is required and is supplied as HTTP
headers in this project.

---

## Request

### Query parameters

- `region` (string, required)  
  Region to search. Known values include:
  - `FX`
  - `UK`
  - `AUS`
  - `SING`

- `cultureId` (integer, required)  
  Culture (language) identifier for the stories.  
  Example: `69` for English.

- `maxResults` (integer, optional; default `25`, min `1`, max `500`)  
  Maximum number of news stories to return.

- `searchByHeadline` (boolean, optional)  
  If `true`, the `query` string is used to search within **headlines**.

- `searchByBody` (boolean, optional)  
  If `true`, the `query` string is used to search within the **body** text.

- `query` (string, required when either search flag is `true`)  
  Text to search for in headlines and/or body (for example, `"education"`).

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
      "Headline": "Example headline mentioning education",
      "PublishDate": "/Date(1766578594028)/",
      "Summary": "Short summary text ...",
      "Region": "FX",
      "Source": "Reuters",
      "Provider": 1
    }
  ]
}
```

The `News` array may be empty if there are no stories matching the query for
the specified region and culture.

---

## Example – Search FX news for “education”

Retrieve up to 20 English-language stories in the FX region whose body
contains the word `"education"`.

### HTTP

```http
GET https://ciapi.cityindex.com/TradingAPI/news/searchnews?region=FX&cultureId=69&maxResults=20&searchByBody=true&query=education
username: {UserName}
session: {SessionToken}
Accept: application/json
```

### cURL

```bash
curl -sS \
  "https://ciapi.cityindex.com/TradingAPI/news/searchnews?region=FX&cultureId=69&maxResults=20&searchByBody=true&query=education" \
  -H "username: ${CITYINDEX_USERNAME}" \
  -H "session: ${CITYINDEX_SESSION}" \
  -H "Accept: application/json"
```

A successful request returns `HTTP 200` and a `NewsResponseDTO` containing the
matching regional news stories.

---

_Last updated to match StoneX reference: 23 July 2024._
