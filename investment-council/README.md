# Investment Council PWA

AI investment research app with three advisor personas powered by Claude.

## Advisors
- **Systematic Analyst** — Macro, sectors, valuation, risk
- **Warren Buffett** — Moats, owner earnings, long-term compounding
- **Charlie Munger** — Mental models, inversion, concentrated bets

## Features
- Mention `$AAPL` or any ticker to auto-pull real financial data
- Mobile-first PWA — add to iPhone home screen
- No build step — pure vanilla HTML/JS

## Deploy to Vercel

```bash
npm i -g vercel
vercel --prod
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `FINANCIAL_DATASETS_API_KEY` | No | financialdatasets.ai key for real financial data |

## API Endpoints

- `GET /api/health` — Health check
- `POST /api/ask` — Ask advisors (no financial data)
- `POST /api/research` — Ask advisors with auto financial data pull
