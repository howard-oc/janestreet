# Price history: GetPriceBarsBeforeDate

## Overview
`GetPriceBarsBeforeDate` returns historic OHLC price bars (open, high, low, close) for a specified market **before** a given UNIX timestamp. Results are returned in ascending time order up to `toTimestampUTC` and are suitable for candlestick or bar charts.

As with the other price history endpoints, there may be "gaps" in the series where there were no trades for a particular interval.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/barhistorybefore`
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
- `toTimestampUTC` (query, long integer)
  - End date/time in **UNIX seconds** (UTC). Only bars strictly **before** this timestamp are returned.
- `maxResults` (query, integer, optional)
  - Maximum number of price bars to return.
  - Default is `1000`, hard limit `4000`.
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Sample URLs
From the StoneX documentation:

- 15‑minute bars before a timestamp:
  - `/market/1234/barhistorybefore?interval=MINUTE&span=15&toTimestampUTC=1400770798`
- Hourly bars before a timestamp with result limit:
  - `/market/735/barhistorybefore?interval=HOUR&span=1&toTimestampUTC=1400770798&maxResults=10`
- Daily bars before a timestamp:
  - `/market/1577/barhistorybefore?interval=DAY&span=1&toTimestampUTC=1400770798`

A full example request (authentication headers omitted here for clarity) would look like:

- `GET https://ciapi.cityindex.com/TradingAPI/market/401166448/barhistorybefore?interval=MINUTE&span=15&toTimestampUTC=1400770798&maxResults=20&priceType=BID`

## Usage patterns

### Backfilling older history
`GetPriceBarsBeforeDate` is useful when you want to backfill older data without re‑downloading the most recent history.

Typical workflow:

1. Choose an initial cut‑off timestamp (for example, "one year ago") and call `barhistorybefore` with:
   - `toTimestampUTC=<cutoff_timestamp>`
   - Appropriate `interval` / `span` / `priceType`.
2. Store the returned bars locally.
3. For deeper history, repeat with an earlier `toTimestampUTC` (for example, the first bar's `BarDate` minus one second) until you have as much back history as required.

### Example: Japan 225 older daily history
For Japan 225 DFT (`marketId 400616391`):

- Suppose you know the UNIX timestamp for 01‑Jan‑2020 00:00:00 UTC.
- Request daily bars before that date:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/barhistorybefore?interval=DAY&span=1&toTimestampUTC=<2020-01-01_unix>&maxResults=200`

This returns the last `maxResults` daily bars **prior** to `toTimestampUTC`, allowing you to page backwards through historical price data.
