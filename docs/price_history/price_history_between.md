# Price history: GetPriceBarsBetweenDates

## Overview
`GetPriceBarsBetweenDates` returns historic OHLC price bars (open, high, low, close) for a specified market **between** two UNIX timestamps. Results are returned in ascending time order from `fromTimestampUTC` up to `toTimestampUTC`, making this endpoint ideal for fixed date‑range charting.

As with the other endpoints, time "gaps" may appear in the series where there were no trades for a particular interval.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/barhistorybetween`
- **Method**: `GET`
- **Envelope**: Query string
- **Response**: `GetPriceBarResponseDTO`, containing:
  - `PriceBars`: array of completed bars in ascending order
  - `PartialPriceBar`: optional, most recent incomplete bar

## Parameters
- `MarketId` (path, string)
  - Market identifier, for example `400616391` (Japan 225 DFT).
- `interval` (query, string)
  - Time unit for each bar: e.g. `MINUTE`, `HOUR`, `DAY`.
- `span` (query, integer)
  - Number of `interval` units per bar, e.g. `1` for daily bars, `15` for 15‑minute bars.
- `fromTimestampUTC` (query, long integer)
  - Start date/time in **UNIX seconds** (UTC).
- `toTimestampUTC` (query, long integer)
  - End date/time in **UNIX seconds** (UTC).
- `maxResults` (query, integer, optional)
  - Maximum number of price bars to return.
  - Default is `1000`, hard limit `4000`.
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Sample URLs
From the StoneX documentation:

- 15‑minute bars between timestamps:
  - `/market/1234/barhistorybetween?interval=MINUTE&span=15&fromTimestampUTC=1390402198&toTimestampUTC=1400770798`
- Hourly bars between timestamps with result limit:
  - `/market/735/barhistorybetween?interval=HOUR&span=1&fromTimestampUTC=1390402198&toTimestampUTC=1400770798&maxResults=10`
- Daily bars between timestamps:
  - `/market/1577/barhistorybetween?interval=DAY&span=1&fromTimestampUTC=1390402198&toTimestampUTC=1400770798`

A full example request (authentication headers omitted here for clarity) would look like:

- `GET https://ciapi.cityindex.com/TradingAPI/market/401166448/barhistorybetween?interval=MINUTE&span=15&fromTimestampUTC=1390402198&toTimestampUTC=1400770798&maxResults=20&priceType=BID`

## Usage patterns

### Fixed date‑range charts
Use `GetPriceBarsBetweenDates` when you need to draw charts or run analytics over a fixed date range.

Example workflow:

1. Convert your desired start and end datetimes to UNIX seconds (UTC).
2. Call `barhistorybetween` with:
   - `fromTimestampUTC=<start_unix>`
   - `toTimestampUTC=<end_unix>`
   - Appropriate `interval` / `span` / `priceType`.
3. Use the returned `PriceBars` as the canonical data set for that window (e.g. a 1‑year daily chart or a 1‑day intraday chart).

### Example: Japan 225 daily range
For Japan 225 DFT (`marketId 400616391`):

- Suppose you want daily bars for calendar year 2024.
- Compute UNIX timestamps for:
  - `fromTimestampUTC` → 2024‑01‑01 00:00:00 UTC
  - `toTimestampUTC` → 2024‑12‑31 23:59:59 UTC
- Request daily MID bars:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/barhistorybetween?interval=DAY&span=1&fromTimestampUTC=<2024-01-01_unix>&toTimestampUTC=<2024-12-31_unix>&maxResults=4000`

The response will contain one entry per trading day within that window (subject to market holidays), ordered in ascending time, ready for use in charts or historical analytics.
