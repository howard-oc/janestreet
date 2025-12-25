# Price ticks: GetPriceTicksBetweenDates

## Overview
`GetPriceTicksBetweenDates` returns historic price ticks for a specified market **between** two UNIX timestamps. A price tick is a single update from the pricing engine containing Ask, Bid and Mid at that moment; the endpoint returns a single `Price` value per tick for the requested `priceType`.

Ticks are returned in ascending time order between `fromTimeStampUTC` and `toTimestampUTC`. The spacing between ticks is irregular, as updates only occur when prices change.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/tickhistorybetween`
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
  - Start date/time in **UNIX seconds** (UTC).
- `toTimestampUTC` (query, long integer)
  - End date/time in **UNIX seconds** (UTC).
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Usage patterns

### Event‑window analysis
Use `GetPriceTicksBetweenDates` when you need full tick‑level detail around a specific window, for example:

- Around an economic data release.
- Around a trade execution time to analyse slippage.
- During a specific volatility event.

Typical workflow:

1. Determine the start and end timestamps for your window (e.g. 5 minutes before to 5 minutes after an event).
2. Convert them to UNIX seconds (UTC).
3. Call `tickhistorybetween` with:
   - `fromTimeStampUTC=<event_start_unix>`
   - `toTimestampUTC=<event_end_unix>`
   - Optional `maxResults` large enough for expected tick volume.
   - Consistent `priceType` (e.g. `MID` or `BID`).
4. Use the returned `PriceTicks` to compute spreads, realised volatility, or execution quality across that window.

### Example: Japan 225 event window
For Japan 225 DFT (`marketId 400616391`):

- Suppose you want ticks around a Bank of Japan announcement at time `T_event`.
- Define:
  - `fromTimeStampUTC` = `T_event - 300` seconds.
  - `toTimestampUTC`   = `T_event + 300` seconds.
- Request mid‑price ticks:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/tickhistorybetween?fromTimeStampUTC=<T_event_minus_300>&toTimestampUTC=<T_event_plus_300>&maxResults=4000&priceType=MID`

The response will contain all mid‑price ticks between those timestamps, ordered in ascending time, which you can feed into any event‑study or microstructure analysis.
