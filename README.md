# Quanta

**Quanta Social** — a mock/demo social network with a built-in **glass-box programmatic
ad cabinet** (*Quanta Ads*). Non-commercial learning & portfolio project.

Two goals:
1. **The dream ad cabinet** — a genuinely well-designed, *transparent* ad manager. Real
   cabinets (Meta Ads Manager, Google Ads, DV360) hide the auction; Quanta shows it —
   the bid request, the clearing price, the learning phase — live, in the UI.
2. **Learn programmatic on a live example** — the engine is modeled on the **OpenRTB 2.6**
   spec, but generates *synthetic* requests/impressions/clicks/conversions (no real
   exchanges). Desktop-only, USD, English.

## Architecture

- **backend/** — FastAPI + SQLAlchemy + Alembic + SQLite (WAL). A single in-process
  engine (`app/adsim`) models both sides of RTB (SSP/exchange + DSP) and a real-time
  simulation "world" (one asyncio task) that statistically aggregates synthetic delivery
  into compact per-minute buckets. `uvicorn --workers 1` is mandatory (single world loop).
- **frontend/** — React 19 + Vite + TypeScript. Light-default theme, live updates over SSE.

The full plan lives in the design doc; build proceeds in verifiable phases (engine + live
slice first, social network later).

## Local development

```sh
# backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # (Windows) / source .venv/bin/activate on *nix
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
.venv/Scripts/python -m pytest                            # tests

# frontend (separate terminal)
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxies /api -> :8000)
```

## Deploy

Home server behind Cloudflare Tunnel + Caddy (shared external `web` network, no published
ports). See `compose.yaml` and `deploy/homeserver/quanta.Caddyfile`. Domain:
`quanta-social.com`.
