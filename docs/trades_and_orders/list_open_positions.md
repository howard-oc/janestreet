# ListOpenPositions

## Overview
`ListOpenPositions` queries the open trades / positions for a specified trading account. It is designed primarily to support UI grids:

- Call once to obtain the **initial** set of open positions for display.
- Subscribe to the relevant streaming channels for ongoing updates.
- Call this HTTP service again when streaming events indicate changes, to refresh the grid in a consistent format.

## Endpoint
- **Target**: `order`
- **Relative path**: `/openpositions?TradingAccountId={TradingAccountId}`
- **Method**: `GET`
- **Envelope**: Query string
- **Content type**: `application/json`
- **Authentication**: requires `UserName` and `Session`.

Base URL example:

- `GET https://ciapi.cityindex.com/TradingAPI/order/openpositions?TradingAccountId={TradingAccountId}`

## Parameters

Although both `ClientAccountId` and `TradingAccountId` can conceptually drive which data is returned, the v1 docs state:

- `TradingAccountId` (query, integer, nullable=true but effectively **mandatory**)
  - The trading account ID to get open positions for.
  - If omitted, behaviour is API‑specific; the documentation notes that if neither `ClientAccountId` nor `TradingAccountId` is passed, the default scope is the `ClientAccount`, but also that `TradingAccountId` is mandatory in this URI.

In practice, `augmenttrade` should always pass a concrete `TradingAccountId` (for example, the one returned by `GetClientAndTradingAccount v2`).

## Response
- **DTO**: `ListOpenPositionsResponseDTO`
- Contains details of all current open positions for the requested trading account, typically including:
  - Position IDs / trade IDs
  - Market IDs and names
  - Direction (long/short), quantity, and open price
  - Current price and unrealised P&L
  - Associated stop/limit orders and margin information

Consult the StoneX DTO definition for the full schema.

## Usage in `augmenttrade`

A typical pattern for the Japan 225 trading account might be:

1. Use `GetClientAndTradingAccount v2` to obtain `tradingAccountId` (e.g. `400236033`).
2. Call:

   `GET https://ciapi.cityindex.com/TradingAPI/order/openpositions?TradingAccountId=400236033`

3. Render the returned positions in an open‑positions grid.
4. Subscribe to the relevant streaming channels (orders / trades) to receive updates.
5. On significant updates (e.g. position added/closed), re‑call `ListOpenPositions` to resynchronise the grid.
