# Price ticks: GetPriceTicksBeforeDate

## Overview
`GetPriceTicksBeforeDate` returns historic price ticks for a specified market **before** a given UNIX timestamp. A price tick is a single update from the pricing engine containing Ask, Bid and Mid at that instant; the endpoint returns a single `Price` value per tick for the chosen `priceType`.

Ticks are returned in ascending time order up to `toTimeStampUTC`. The time between ticks is irregular, since updates only occur when prices change.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/tickhistorybefore`
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
- `toTimeStampUTC` (query, long integer)
  - End date/time in **UNIX seconds** (UTC). Only ticks strictly **before** this timestamp are returned.
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Usage patterns

### Backfilling older tick history
`GetPriceTicksBeforeDate` lets you page backwards through tick data without re‑fetching more recent ticks.

Typical workflow:

1. Pick a cut‑off timestamp (e.g. the first tick you currently hold).
2. Convert it to UNIX seconds (UTC).
3. Call `tickhistorybefore` with:
   - `toTimeStampUTC=<cutoff_unix>`
   - Optional `maxResults` (e.g. 1000).
   - Consistent `priceType` (e.g. `MID`).
4. Prepend the returned ticks to your local series.
5. Repeat with an earlier `toTimeStampUTC` (e.g. the first returned `TickDate` minus one second) until you have enough historical depth.

### Example: Japan 225 older ticks
For Japan 225 DFT (`marketId 400616391`):

- Suppose your earliest stored tick corresponds to some timestamp `T0`.
- To backfill older data:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/tickhistorybefore?toTimeStampUTC=<T0_unix>&maxResults=1000&priceType=MID`

This returns up to `maxResults` ticks immediately prior to `T0`, in ascending order, which you can prepend to your existing tick series.
