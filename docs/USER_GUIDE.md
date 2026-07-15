# Trading Engine V2 User Guide

This repo is the source of truth. Excel is only a viewer.

## 1. Daily workflow

1. Run or wait for the GitHub workflow.
2. Refresh Excel.
3. Open Dashboard.
4. Review rows from top to bottom.
5. Act on SELL or TRIM before considering new buys.
6. Check Holdings, Performance Summary, and Weekly Review.

## 2. Dashboard columns

### Action Required
- SELL: exit the position.
- TRIM: sell part of the position.
- BUY: strong buy candidate.
- BUY SMALL: smaller starter buy.
- HOLD: keep current holding.
- WATCH: do nothing now.

### Plan / Why
Plain-English reason for the action.

### Buy USD / Shares To Buy
How much to buy if actionable. If Buy USD is zero, do not buy now.

### Sell USD / Shares To Sell
How much to sell if SELL or TRIM.

### Risk Note
Main warnings and stop level.

## 3. Trade logging

Edit:

```text
data/trades.csv
```

For buys, shares and value can be blank.

Example buy:

```csv
2026-07-15,ANET,Buy,182.57,12,0.20,,,11,Initial buy
```

For full sells, use `ALL`:

```
2026-07-20,ANET,Sell,200.00,13.00,0.20,ALL,,11,Full exit
```

For partial sells, enter exact shares sold:

```csv
2026-07-20,ANET,Sell,200.00,6.50,0.10,0.03,,11,Partial trim
```

## 4. Holding keys

Use one holding key per buy lot.

Example:
- First ANET buy: holding_key 11
- Sell that ANET lot: holding_key 11
- Second ANET buy later: holding_key 12

## 5. Deposits

Edit:

```text
data/deposits.csv
```

Use actual Sharesies numbers:
- amount_nzd = NZD deposited
- fx_rate = FX conversion rate
- amount_usd = USD actually credited

Example:

```
2026-07-15,100,0.6100,61.00,Sharesies,Fortnight deposit
```

## 6. Watchlist

Edit:

```text
data/watchlist.csv
```

Columns:
- ticker
- sector
- tier
- enabled
- notes

## 7. Tiers

### QUALITY
Stable or established companies. Sized more conservatively.

### MOMENTUM
Stocks with strong trend or price momentum. Receives a score boost.

### MOONSHOT
Highly speculative, high-risk opportunities. Use carefully:
- smaller starting size
- wider risk
- no averaging down
- only a small number at once

## 8. Risk rules

Current aggressive setup:
- Max positions: 6
- Cash reserve: 0%
- Risk per trade: 5% of equity
- Max position cap: 35% of equity
- Add only to winners
- Do not average down

## 9. Performance review

Use:
- Performance Summary
- Weekly Review

Important metrics:
- Account equity
- Account P&L
- Account return %
- Realized P&L
- Win rate
- Average win/loss

## 10. Troubleshooting

### Cash does not match Sharesies
Check:
- deposits.csv amount_usd
- trades.csv usd_amount
- transaction_fee
- buy/sell type spelling

### Tiny leftover holdings
For full sells, use `shares = ALL`.

### Dashboard looks stale
Run GitHub workflow, wait for success, then refresh Excel.

### New buys show WATCH
Likely max positions reached. Sell or trim something first.

## 11. Important reminder

The workbook does not make trades for you.

The engine gives decision support only. You approve every trade manually.
