# GetOrder

## Overview

`GetOrder` queries the status and details of a single order by its `OrderId`.

The current implementation only returns **active orders**, i.e. orders whose
status is one of:

- `1` – Pending
- `2` – Accepted
- `3` – Open
- `6` – Suspended
- `8` – Yellow Card
- `11` – Triggered

If an order is fully closed, cancelled, or otherwise inactive, it will not be
returned by this service.

---

## Endpoint

- **Service**: `order`
- **Method**: `GET`
- **URI template**: `/{OrderId}`
- **Transport**: HTTP / HTTPS
- **Envelope**: URL
- **Content type**: `application/json`
- **Return type**: `GetOrderResponseDTO`

Live environment base URL (example):

- `https://ciapi.cityindex.com`

Full example URL:

- `https://ciapi.cityindex.com/TradingAPI/order/{OrderId}`

> Authentication (`username`, `session`) is required, typically supplied as
> HTTP headers in this project.

---

## Request

### Path parameters

- `OrderId` (integer, required) – the identifier of the order to query.

### Query parameters

- None for this operation itself; authentication details may be required by
  your client (for example, `username` and `session` headers).

### Body

- None – this is a `GET` request.

---

## Response

- **HTTP status**:
  - `200 OK` – order found and active.
  - `4xx/5xx` – error conditions (invalid ID, unauthorised, server error, etc.).

- **Body**: `GetOrderResponseDTO` in JSON format.

A typical successful response includes:

- Top-level fields such as `TradeOrder` and/or `StopLimitOrder`.
- For `StopLimitOrder`:
  - `OrderId`, `MarketId`, `TradingAccountId`
  - `Direction`, `Quantity`, `TriggerPrice`, `Price`
  - `StatusId` and `TypeId`
  - Time-in-force (`Applicability`, for example `GTC`)
  - Associated If/Done or OCO orders via `IfDone` and `OcoOrder`.

If the specified `OrderId` does not correspond to an active order (statuses 1,
2, 3, 6, 8, 11) the service will not return that order.

---

## Example – Query the Japan 225 test order

Assuming you have an active entry order on Japan 225 with ID `997328156`:

### HTTP

```http path=null start=null
GET https://ciapi.cityindex.com/TradingAPI/order/997328156
username: {UserName}
session: {SessionToken}
Accept: application/json
```

### cURL

```bash path=null start=null
curl -sS \
  "https://ciapi.cityindex.com/TradingAPI/order/997328156" \
  -H "username: ${CITYINDEX_USERNAME}" \
  -H "session: ${CITYINDEX_SESSION}" \
  -H "Accept: application/json"
```

Example response (truncated for clarity):

```json path=null start=null
{
  "TradeOrder": null,
  "StopLimitOrder": {
    "OrderId": 997328156,
    "OrderReference": "test-order",
    "MarketId": 400616391,
    "TradingAccountId": 400236033,
    "Direction": "buy",
    "Quantity": 1,
    "TriggerPrice": 41000.0,
    "Applicability": "GTC",
    "StatusId": 2,
    "TypeId": 3,
    "IfDone": [],
    "OcoOrder": null,
    "AssociatedOrders": {
      "Stop": null,
      "Limit": null
    }
  }
}
```

In this example the order is a GTC entry order to **buy 1 Japan 225 DFT at
41000**, with status `2` (Accepted) and no attached stop or limit orders.
