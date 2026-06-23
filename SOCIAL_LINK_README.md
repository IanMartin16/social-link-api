# social_link

Python/FastAPI engine in the **evilink ecosystem**. Provides social/market signals
consumed internally by the CryptoLink portal. Not a sold product — it feeds the
portal alongside the CryptoLink API.

**Stack:** Python · FastAPI · uvicorn · httpx
**Role:** internal signal engine (basic-signals + symbols 360°)
**Deployment:** Railway

---

## What it does

social_link exposes internal endpoints that the CryptoLink portal calls server-side.
It is intentionally lightweight: no database, no auth secrets, no external paid
services beyond the market data provider (CoinGecko).

### Endpoints

| Method | Path                         | Purpose                                                        |
|--------|------------------------------|----------------------------------------------------------------|
| GET    | `/internal/v1/basic-signals` | Social/attention signals (leaders). *Note: losers not yet computed.* |
| GET    | `/internal/v1/symbols`       | Rich per-asset market data (CoinGecko): price, 24h, volume, mkt cap, rank, ATH. Powers Market 360°. |

Both routes are registered directly in `main.py` (not under `api/routes/`).

Sample response (`/internal/v1/symbols?symbols=BTC,ETH&fiat=USD`):
```json
{"ok":true,"source":"social-link-coingecko-markets-v1","fiat":"USD",
 "symbols":[{"symbol":"BTC","rank":1,"price":63902.0,"change24h":0.27,
 "marketCap":1281268578792.0,"volume24h":28092731607.0,"ath":126080.0,...}],
 "missing":[]}
```

---

## Project structure

```
social-link/
├── main.py                 # FastAPI app + route registration
├── requirements.txt
├── adapters/               # map provider responses -> internal models
│   ├── coingecko_adapter.py
│   └── alternative_adapter.py
├── clients/                # HTTP clients to data providers
│   ├── coingecko_client.py
│   └── alternative_client.py
├── api/routes/
│   └── basic_signals.py     # handler logic (route registered in main.py)
├── models/                 # Pydantic models
│   ├── basic_signals.py
│   └── symbols.py
├── services/               # business logic
│   ├── basic_signals_service.py
│   └── symbols_service.py
└── utils/
    ├── symbol_ids.py       # symbol -> coingecko-id resolver (mirror of crypto's table)
    └── symbol_policy.py    # ALLOWED_SOCIAL_ASSETS (governs social scope only)
```

Pattern: **client → adapter → service → route**. Clients fetch raw provider data,
adapters reduce it to internal models, services hold the logic, routes expose it.

---

## Run locally

```bash
# create / activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8080
```

Test:
```bash
curl "http://localhost:8080/internal/v1/symbols?symbols=BTC,ETH,SOL&fiat=USD"
```

---

## Deployment (Railway)

- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
  (also in `Procfile`).
- Python version pinned in `runtime.txt`.
- No environment variables required (self-contained; only outbound calls to CoinGecko).
- `$PORT` is provided by Railway automatically.

---

## Notes & conventions

- `symbol_ids.py` is a **conscious local copy** of crypto's `cryptolink_symbols`
  table (social_link does not touch that DB). Keep it in sync when symbols change.
- `symbol_policy.py` (`ALLOWED_SOCIAL_ASSETS`) governs **only** social scope, separate
  from the symbol resolver.
- Default display currency is **USD** (aligned with the international audience).

## Pending

- **basic-signals losers** — engine computes leaders only; `attentionLosers` is `[]`.

## History

- `/internal/v1/trends` — **kept, NOT obsolete.** Originally thought to be a dead MVP
  placeholder, but removing it broke Market 360° in the portal (symbols stopped
  rendering despite 200s — likely a shared/parallel fetch where the trends 404
  poisoned the result set). Restored as a temporary fix. Acoplamiento with the front
  under investigation: either confirm it as required, or decouple the front so it can
  be retired cleanly. Do NOT remove until the coupling is understood.
- Repo separated from the crypto monorepo (was: branch `monorepov2`, root
  `/services/social-link`). Now standalone.
