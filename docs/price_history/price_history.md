# Price history and latest price bars

## Overview
This project uses the StoneX / City Index `barhistory` endpoint to retrieve historic OHLC (open, high, low, close) price bars for a given market. The data can be used to calculate values such as yesterday's closing price or to plot candlestick charts.

## GetLatestPriceBars (barhistory)
The API exposes historic price bars per market via the `barhistory` service.

- **Endpoint (relative)**: `/TradingAPI/market/{MarketId}/barhistory`
- **Method**: `GET`
- **Envelope**: Query string
- **Response**: `GetPriceBarResponseDTO`, containing:
  - `PriceBars`: array of completed bars in ascending time order
  - `PartialPriceBar`: the most recent, possibly incomplete, bar

### Parameters
- `MarketId` (path): identifier of the market, for example `400616391` (Japan 225 DFT).
- `interval` (query): time unit for each bar, e.g. `MINUTE`, `HOUR`, `DAY`.
- `span` (query): number of `interval` units per bar, e.g. `1` for daily bars.
- `PriceBars` (query): maximum number of bars to return.
- `PriceType` (query, optional): `ASK`, `MID`, or `BID` (defaults to `MID` if omitted).

### Example requests
Some typical examples described in the vendor documentation:

- 15 minute bars:
  - `/market/1234/barhistory?interval=MINUTE&span=15&PriceBars=180`
- Hourly bars:
  - `/market/735/barhistory?interval=HOUR&span=1&PriceBars=240`
- Daily bars:
  - `/market/1577/barhistory?interval=DAY&span=1&PriceBars=10`

Full example with authentication (headers omitted here for brevity):

- `GET https://ciapi.cityindex.com/TradingAPI/market/401166448/barhistory?interval=MINUTE&span=15&PriceBars=20&PriceType=BID`

### Using price bars to derive yesterday's close
To obtain "yesterday's closing price" for a market:

1. Request **daily** bars:
   - `interval=DAY`
   - `span=1`
   - `PriceBars` large enough to cover at least the last two sessions (for example `PriceBars=5`).
2. Inspect the `PriceBars` array returned by the API:
   - The entries are ordered in **ascending** time order.
   - The last element represents the most recent **completed** day.
3. Take the `Close` field from the last bar as the latest full-day close.

The `PartialPriceBar` object may represent an intraday, still-open bar. For a strict "yesterday close" value, ignore `PartialPriceBar` and only use the final element of `PriceBars`.

### Japan 225 example
For the Japan 225 DFT market in this project:

- `MarketId`: `400616391`
- Daily MID price bars endpoint:
  - `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/barhistory?interval=DAY&span=1&PriceBars=5`

From the response, the last entry in `PriceBars` holds the most recent daily close, which the code can surface as "yesterday's closing price" in the application.
