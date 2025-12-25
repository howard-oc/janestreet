# Price history: GetPriceBarsAfterDate

## Overview
`GetPriceBarsAfterDate` returns historic OHLC price bars (open, high, low, close) for a specified market **after** a given UNIX timestamp. Results are in ascending time order starting from `fromTimestampUTC` and are suitable for candlestick or bar charts.

Like `GetLatestPriceBars` (`barhistory`), this endpoint may return "gaps" in the time series where there were no trades for a particular interval.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/barhistoryafter`
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
  - Start date/time in **UNIX seconds** (UTC). Only bars strictly after this timestamp are returned.
- `maxResults` (query, integer, optional)
  - Maximum number of price bars to return.
  - Default is `1000`, hard limit `4000`.
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Sample URLs
From the StoneX documentation:

- 15‑minute bars from a timestamp:
  - `/market/1234/barhistoryafter?interval=MINUTE&span=15&fromTimestampUTC=1390402198`
- Hourly bars from a timestamp with result limit:
  - `/market/735/barhistoryafter?interval=HOUR&span=1&fromTimestampUTC=1390402198&maxResults=10`
- Daily bars from a timestamp:
  - `/market/1577/barhistoryafter?interval=DAY&span=1&fromTimestampUTC=1390402198`

A full example request (authentication headers omitted here for clarity):

- `GET https://ciapi.cityindex.com/TradingAPI/market/401166448/barhistoryafter?interval=MINUTE&span=15&fromTimestampUTC=1390402198&maxResults=20&priceType=BID`

## Usage patterns

### Incremental price history sync
`GetPriceBarsAfterDate` is useful when you:

1. Store the timestamp of the last bar you have locally (for example, the `BarDate` of the last entry in `PriceBars`).
2. Convert that `BarDate` to UNIX seconds (UTC) and call `barhistoryafter` with:
   - `fromTimestampUTC=<last_bar_timestamp>`
   - Same `interval` / `span` / `priceType` used previously.
3. Append any new bars returned to your local cache.

This avoids repeatedly downloading the full history.

### Example: Japan 225 incremental daily bars
For Japan 225 DFT (`marketId 400616391`):

- First call `barhistory` for a historical backfill:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/barhistory?interval=DAY&span=1&PriceBars=200`
- Record the last `BarDate` you receive.
- To fetch new daily bars after that date:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/barhistoryafter?interval=DAY&span=1&fromTimestampUTC=<last_bar_unix_seconds>`

The response will contain only the bars that occurred after the stored timestamp, simplifying ongoing updates of your local price history.
