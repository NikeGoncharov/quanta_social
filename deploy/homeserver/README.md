# Deploying Quanta on the home server

Quanta runs next to Report and Classroom on the home server, behind **one shared Cloudflare
Tunnel → shared Caddy**. Nothing publishes host ports: the tunnel forwards every hostname to
the `caddy` container on the external `web` Docker network, and Caddy routes by `Host` header
to each project's containers by name.

```
Cloudflare (TLS)  →  cloudflared (tunnel)  →  caddy:80  →  quanta-backend:8000  (/api/*)
                                                        →  quanta-frontend:80   (SPA)
```

`--workers 1` is mandatory: the real-time world loop is a single in-process asyncio task and
must not be forked. The backend image's entrypoint runs `alembic upgrade head` before uvicorn,
so **Alembic owns the production schema**.

## One-time first deploy

1. **Cloudflare tunnel** — on the existing tunnel, add a Public Hostname
   `quanta-social.com` → `http://caddy:80` (SSL/TLS mode: Full). *(Already done via the
   dashboard — this also created the `quanta-social.com` CNAME.)* Add `www.quanta-social.com`
   the same way if you want the www alias.

2. **Clone** the (private) repo on the server, e.g. under `~/apps`:
   ```sh
   git clone git@github.com:NikeGoncharov/quanta_social.git ~/apps/quanta_social
   cd ~/apps/quanta_social
   ```
   (Uses the server's GitHub deploy key, like Classroom.)

3. **Backend env** — create `backend/.env` from the template and set the production values:
   ```sh
   cp backend/.env.example backend/.env
   # then edit backend/.env:
   #   ENVIRONMENT=production
   #   SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
   #   ALLOWED_REGISTRATION_EMAILS=you@example.com,friend@example.com
   ```
   The app refuses to boot in production if `SECRET_KEY` or `ALLOWED_REGISTRATION_EMAILS`
   is unset — that's intentional (registration is invite-only; the guest demo is the open door).

4. **Data dir** — the SQLite file is a bind mount owned by the container's `1000:1000` (see
   `compose.yaml`). Make sure it exists and is writable by uid 1000 (the deploy user usually is):
   ```sh
   mkdir -p backend/data
   ```

5. **Caddy site block** — append the contents of `deploy/homeserver/quanta.Caddyfile` to the
   shared Caddyfile (next to Report's block) and reload:
   ```sh
   docker exec caddy caddy reload --config /etc/caddy/Caddyfile
   ```

6. **Build & start** (the `web` network already exists from Report/Classroom; create it only if
   `docker network inspect web` fails: `docker network create web`):
   ```sh
   docker compose up -d --build
   ```

7. **Verify**:
   ```sh
   curl -s https://quanta-social.com/api/health          # {"status":"ok","service":"quanta"}
   ```
   Then open https://quanta-social.com, click **Explore the live demo** (guest), and confirm the
   feed fills with sponsored posts and the cabinet updates live (SSE through the tunnel).

## Updating

```sh
cd ~/apps/quanta_social
git pull
docker compose up -d --build          # entrypoint runs `alembic upgrade head` on boot
```

## Backups

`deploy/homeserver/backup-quanta-db.sh` takes a WAL-safe snapshot into `backend/data/backups/`
and rotates to the newest `KEEP` (default 14). Add to the deploy user's crontab:

```cron
0 */6 * * * /home/<user>/apps/quanta_social/deploy/homeserver/backup-quanta-db.sh >> /tmp/quanta-backup.log 2>&1
```
