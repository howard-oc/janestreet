# ListTradeHistory

## Overview
`ListTradeHistory` returns a list of historical trades for a specified trading account. It is used to analyze past performance, calculate realised P&L, and audit trading activity.

## Endpoint
- **Target**: `order`
- **Relative path**: `/tradehistory`
- **Method**: `GET`
- **Content type**: `application/json`
- **Authentication**: requires `UserName` and `Session`.

Base URL example:
- `GET https://ciapi.cityindex.com/TradingAPI/order/tradehistory`

## Parameters

### Query Parameters
- `TradingAccountId` (integer, required): The ID of the trading account to query.
- `MaxResults` (integer, optional): The maximum number of records to return. Defaults to 100 in many clients.

## Response
- **DTO**: `ListTradeHistoryResponseDTO`

### JSON Structure
The response is typically a JSON object containing a list of trade records under the key `TradeHistory`.

```json
{
  "TradeHistory": [
    {
      "OrderId": 123456789,
      "OpeningOrderIds": [ 987654321 ],
      "MarketId": 400616391,
      "MarketName": "Japan 225 DFT",
      "Direction": "buy",
      "Quantity": 1.0,
      "Price": 38500.0,
      "RealisedPnL": 150.0,
      "RealisedPnLConverted": 150.0,
      "Currency": "JPY",
      "ExecutedDateTimeUtc": "2024-03-15T08:30:00Z"
    },
    ...
  ]
}
```

## Usage in `augmenttrade`
Used in `janestreet.py` to calculate the "Monthly Realised PnL".

1. **Fetch**: Call `fetch_trade_history` which hits this endpoint.
2. **Extract**: The client extracts the `TradeHistory` array.
3. **Analyze**: `calculate_monthly_pnl` iterates through the list to sum `RealisedPnL` for trades executed in the current month.
