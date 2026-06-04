# Browser-safe Market Time Display

## Problem

Dashboards and reports need to show market time to humans, but browser code
should not decide business meaning. JavaScript should not compute market phase,
business date, price basis, or replay admissibility.

## API Request

```json
{
  "perspective": "PRE_TRADE_INTENT",
  "market": "XNYS",
  "market_timezone": "America/New_York",
  "as_of_utc": "2026-05-12T14:00:00Z"
}
```

The API response includes server-resolved fields:

```json
{
  "resolved_at_utc": "2026-05-12T14:00:00Z",
  "market": "XNYS",
  "market_timezone": "America/New_York",
  "market_datetime": "2026-05-12T10:00:00-04:00",
  "market_date": "2026-05-12",
  "business_date": "2026-05-12",
  "market_phase": "MARKET_OPEN",
  "price_basis": "LAST_TRADE"
}
```

## Browser Display

```html
<time id="market-time"></time>
<span id="market-date"></span>
<span id="business-date"></span>
<span id="market-phase"></span>
```

```js
async function renderAsOf() {
  const response = await fetch("/asof/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      perspective: "PRE_TRADE_INTENT",
      market: "XNYS",
      market_timezone: "America/New_York",
      as_of_utc: "2026-05-12T14:00:00Z"
    })
  });

  const asof = await response.json();

  document.getElementById("market-time").textContent = asof.market_datetime;
  document.getElementById("market-date").textContent = asof.market_date;
  document.getElementById("business-date").textContent = asof.business_date;
  document.getElementById("market-phase").textContent = asof.market_phase;
}
```

## Safe Formatting

If the UI wants locale-specific formatting, format the server-provided instant
for display only:

```js
const label = new Intl.DateTimeFormat("en-US", {
  timeZone: asof.market_timezone,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short"
}).format(new Date(asof.resolved_at_utc));
```

That formatted string is display-only. The browser must not use it to compute
`business_date`, `market_phase`, or `price_basis`.

Do not recompute `business_date` in JavaScript. Do not recompute
`market_phase` in JavaScript. Do not infer market-open state from wall-clock
calculations. Use the values already resolved by `AsOf`.

## What The Result Means

The server resolves business meaning. The browser displays it.

Use:

- `asof.market_datetime` for the market-local convenience timestamp;
- `asof.market_date` for the market-local calendar date;
- `asof.business_date` for the resolved business date;
- `asof.market_phase` for market-open checks;
- `asof.price_basis` for price-basis decisions.

Do not reimplement market calendar logic in JavaScript.
