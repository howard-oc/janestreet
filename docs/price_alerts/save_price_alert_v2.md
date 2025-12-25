# SavePriceAlert v2

## Overview
`SavePriceAlert v2` creates or updates a client‑defined price alert. The same service is used both to create new alerts and to modify existing ones by saving new parameters over the previous alert settings.

## Endpoint
- **Target**: `priceAlert`
- **Relative path**: `/v2/priceAlert/save`
- **Method**: `POST`
- **Envelope**: JSON body
- **Content type**: `application/json`
- **Authentication**: requires `UserName` and `Session` (as with other v2 services).

## Request
- **Body DTO**: `SaveAlertRequestDTO v2`
- Example structure (fields may be optional/required per StoneX spec):

```json
{
  "clientAccountId": 0,
  "alertId": 0,
  "marketId": 0,
  "criterion": 1,
  "direction": 1,
  "fillRate": 0,
  "emailAddress": "string",
  "expiry": 1,
  "expiryDate": "2023-01-01T00:00:00.000Z",
  "comment": 0,
  "notificationMethod": 0
}
```

Key fields (high‑level):
- `clientAccountId`: numeric client account identifier.
- `alertId`: existing alert ID when updating, or `0`/omitted when creating a new alert (per StoneX rules).
- `marketId`: market for which the alert is defined.
- `criterion`, `direction`, `fillRate`: numeric flags describing the alert condition and trigger price.
- `emailAddress`: address to notify if email notifications are enabled.
- `expiry` / `expiryDate`: how and when the alert should expire.
- `comment`: optional user comment / label.
- `notificationMethod`: channel to use (e.g. platform notification, email, etc.).

## Response
- **DTO**: `SaveAlertResponseDTO v2`
- On success, the service returns HTTP `200` and JSON describing the saved alert (including its effective `alertId`).

## Example
Example call to the live environment (headers omitted):

- Request:
  - `POST https://ciapi.cityindex.com/v2/priceAlert/save`

- Example JSON body:

```json
{
  "clientAccountId": 400158546,
  "alertId": 0,
  "marketId": 400616391,
  "criterion": 1,
  "direction": 1,
  "fillRate": 50475.5,
  "emailAddress": "user@example.com",
  "expiry": 1,
  "expiryDate": "2025-12-31T00:00:00.000Z",
  "comment": "Japan 225 alert",
  "notificationMethod": 0
}
```

This would create or update a price alert on the Japan 225 market for the specified client account.

The response body contains the resulting `SaveAlertResponseDTO v2`, including the assigned `alertId` and any normalised values.
