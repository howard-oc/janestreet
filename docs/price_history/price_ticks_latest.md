# Price ticks: GetLatestPriceTicks

## Overview
`GetLatestPriceTicks` returns historic price ticks for a specified market. A **price tick** is a single point in time when the pricing engine is updated and includes Ask, Bid, and Mid prices; the API typically returns a single `Price` value per tick for the requested `priceType`.

Ticks are returned in ascending time order up to the current time. The elapsed time between ticks is irregular, as ticks occur only when prices change.

## Endpoint
- **Relative path**: `/TradingAPI/market/{MarketId}/tickhistory`
- **Method**: `GET`
- **Envelope**: Query string
- **Response**: `GetPriceTickResponseDTO`, containing:
  - `PriceTicks`: array of ticks, each with:
    - `TickDate`: timestamp as a JSON date (e.g. `/Date(1432137700614)/`)
    - `Price`: numeric value for the requested price type

## Parameters
- `MarketId` (path, string)
  - Market identifier, for example `401166448` (GBP/USD in the StoneX docs) or `400616391` (Japan 225 DFT in this project).
- `PriceTicks` (query, integer)
  - Total number of ticks to return, in ascending order up to the current time.
- `priceType` (query, string, optional)
  - Price type requested. If omitted, defaults to `MID`.
  - Allowed values: `ASK`, `MID`, `BID`.

## Sample URL
From the StoneX documentation:

- `GET https://ciapi.cityindex.com/TradingAPI/market/401166448/tickhistory?PriceTicks=20`

This returns the 20 most recent **Mid** price ticks for the GBP/USD market in ascending time order.

Example response snippet:

```json
{
  "PriceTicks": [
    {"TickDate":"/Date(1432137700614)/","Price":1.5427},
    {"TickDate":"/Date(1432137700760)/","Price":1.5433},
    ...
  ]
}
```

## Usage patterns

### Short‑term microstructure analysis
Use `GetLatestPriceTicks` when you need the most recent fine‑grained price moves, for example:

- Measuring short‑term volatility.
- Estimating slippage or spread behaviour.
- Building tick‑level or very short‑horizon intraday models.

Example for Japan 225 DFT (`marketId 400616391`):

- `GET https://ciapi.cityindex.com/TradingAPI/market/400616391/tickhistory?PriceTicks=500&priceType=MID`

This returns the latest 500 mid‑price ticks for Japan 225 in ascending time order.

### Combining with bar history
A typical pattern is:

1. Use `barhistory` (price bars) for larger‑scale charting and historical metrics such as daily highs/lows/close.
2. Use `tickhistory` (price ticks) when you need tick‑level detail around a narrow time window (for example, around an economic release or trade execution time).

Together, these endpoints provide both **coarse** (bars) and **fine** (ticks) historical views of market prices.
