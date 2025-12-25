# StoneX API Interaction Process

## Overview
The StoneX API operates as an asynchronous, event-driven system. Your client UI authenticates once, then receives a continuous push of relevant events (such as prices, news, and account changes) over streaming subscriptions.

## High-Level Flow
1. Application login
2. Subscribe to relevant event streams
3. Send trade and order requests
4. Handle asynchronous event responses
5. Application logout

## 1. Application Login
- Login is always the first step.
- Use the `LogOn v2` HTTP `POST` endpoint.
- Send:
  - Username
  - Password
  - AppKey (API key)
- The response returns a `Session` identifier used for subsequent calls and streaming authentication.

## 2. Subscriptions to Streams
To receive live updates without polling, the UI must subscribe to streaming channels.

- Before trading, subscribe to market price streams for the instruments of interest.
- Subscriptions require authentication:
  - Username
  - Session ID (used as the password for streaming).
- Once subscribed, the client receives live push updates until it:
  - Explicitly unsubscribes, or
  - Logs out / the session ends.

Streaming (implemented via Lightstreamer) can push:
- Real-time market prices (bid/offer)
- News headlines
- Account information (cash balance, margin used, available trading resources)
- Margin requirements and open trade equity
- Order state and updates
- Dealer requotes (where applicable)

## 3. Trade and Order Requests
After you have live prices:
- Place **immediate trades** by `POST`ing to the Trade service.
  - Optional stop loss and take profit orders can be attached to each trade.
- Place **resting/entry orders** by `POST`ing to the Order service.

These HTTP requests typically return an immediate acknowledgement, while further lifecycle events (fills, rejections, triggered orders) are delivered via the streaming channels.

## 4. Event Responses
Event responses can arise from:
- Trading activity:
  - Entry orders being triggered
  - Trades opened, partially filled, closed
  - Orders modified or cancelled
- Streaming data:
  - Market price ticks on subscribed instruments
  - New news headlines
  - Account or margin changes

The client UI should be designed to handle these asynchronous events, updating its state as they arrive rather than relying solely on synchronous HTTP responses.

## 5. Application Logout
When the user finishes with the UI application:
- The final action should be to **logout**.
- Send an HTTP `POST` request to the `DeleteSession` service.
- Logging out:
  - Terminates the trading session
  - Invalidates associated streaming subscriptions

This login → subscribe → trade/order → event handling → logout cycle is the core interaction pattern with the StoneX API.
