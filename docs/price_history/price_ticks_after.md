# Price ticks: GetPriceTicksAfterDate

## Overview
`GetPriceTicksAfterDate` returns historic price ticks for a specified market **after** a given UNIX timestamp. A price tick represents a single update from the pricing engine and includes Ask, Bid and Mid at that instant; the endpoint returns a single `Price` value for the requested `priceType`.

Ticks are returned in ascending time order starting from `fromTimeStampUTC`. The time between ticks is irregular, since updates only occur when prices change.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/tickhistoryafter`
- **Method**: `GET`
- **Envelope**: Query string
- **Response**: `GetPriceTickResponseDTO`, containing:
  - `PriceTicks`: array of ticks, each with:
    - `TickDate`: timestamp as JSON date (e.g. `/Date(1432137700614)/`)
    - `Price`: numeric value for the requested price type

## Parameters
- `MarketId` (path, string)
  - Market identifier.
- `maxResults` (query, integer, optional)
  - Maximum number of price ticks to return.
  - Default is `1000`, hard limit `4000`.
- `fromTimeStampUTC` (query, long integer)
  - Start date/time in **UNIX seconds** (UTC). Only ticks strictly after this timestamp are returned.
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Usage patterns

### Incremental tick history
`GetPriceTicksAfterDate` is useful for incrementally updating a local tick store without re‑downloading the latest history.

Typical workflow:

1. Store the `TickDate` of the last tick you have locally.
2. Convert `TickDate` to UNIX seconds (UTC).
3. Call `tickhistoryafter` with:
   - `fromTimeStampUTC=<last_tick_unix>`
   - Optional `maxResults` (e.g. 1000).
   - Consistent `priceType` (e.g. `MID`).
4. Append the returned `PriceTicks` to your local store.

### Example: Japan 225 incremental ticks
For Japan 225 DFT (`marketId 400616391`):

- Assume you have stored the UNIX timestamp of the last tick you processed.
- Request newer ticks:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/tickhistoryafter?fromTimeStampUTC=<last_tick_unix>&maxResults=1000&priceType=MID`

The response will contain all available ticks after that time (up to `maxResults`), in ascending order, making it straightforward to keep a tick‑level series up to date.
