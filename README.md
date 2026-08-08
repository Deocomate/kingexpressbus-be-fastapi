# kingexpressbus-backend-python

FastAPI + SQLAlchemy backend for King Express Bus.

## Architecture

Clean Architecture layers under `app/`:

```text
app/
  domain/            # domain errors
  application/       # use cases (booking, auth, catalog, website)
  infrastructure/    # SQLAlchemy, mail, SePay, uploads, security
  presentation/      # FastAPI routers + Pydantic schemas
  core/              # settings, deps
  templates/         # Jinja2 email templates
```

Dependency rule: `presentation` → `application` → `domain` ← `infrastructure`.

## Database setup

```bash
alembic upgrade head    # creates / upgrades schema
python scripts/seed.py  # LOCAL/DEV ONLY — truncates business tables then loads
                         # full content from seed_data/. Refuses APP_ENV that
                         # looks like production unless you pass --force.
```

Seed JSON lives in `app/infrastructure/persistence/seed_data/`.

Admin login after seeding: `admin@kingexpressbus.com` / `Admin@123`. The other
13 seeded users keep their existing bcrypt hashes (no known plaintext password —
reset required to log in as them).

### Additive seed updates (production-safe)

After deploying a migration that adds catalog tables (e.g. hotels/tours), apply
**insert-missing** updates instead of a full reseed. These never truncate
bookings or users; they key on slug/url and are idempotent.

```bash
python -m scripts.seeds.apply --list
python -m scripts.seeds.apply 20260808_hotels_tours_menus          # insert missing
python -m scripts.seeds.apply 20260808_hotels_tours_menus --dry-run
python -m scripts.seeds.apply 20260808_hotels_tours_menus --update # refresh existing too
python -m scripts.seeds.apply --all
```

New production content drops go in `scripts/seeds/` (register in
`scripts/seeds/registry.py`). Reuse JSON under `seed_data/` when possible.

## Scripts layout

| Path | Purpose |
|------|---------|
| `scripts/seed.py` | Full truncate+seed (local/dev) |
| `scripts/seeds/` | Additive updates for prod/staging |
| `scripts/mail_worker.py` | Mail queue worker |
| `scripts/prune_upload_staging.py` | GC for staged admin uploads |
| `scripts/docker-entrypoint.sh` | Container entry (migrations + app) |
| `scripts/dev/` | Local smoke / mail probes only |

## Maintenance scripts

### Upload staging garbage collection

Staged admin uploads (`app/infrastructure/storage/uploads.py`) live under
`{UPLOAD_ROOT}/admin-tmp/{session}/{uuid}/{filename}` until an admin commits
or reverts them. `scripts/prune_upload_staging.py` deletes any staged
directory older than `--hours` (default 24).

```bash
python -m scripts.prune_upload_staging            # default: 24h cutoff
python -m scripts.prune_upload_staging --hours 12 # custom cutoff
```

Cron (daily):

```cron
0 0 * * * cd /path/to/kingexpressbus-backend-python && .venv/bin/python -m scripts.prune_upload_staging >> /var/log/kingexpressbus/prune-uploads.log 2>&1
```

On Windows Task Scheduler, run `.venv\Scripts\python.exe -m scripts.prune_upload_staging` daily instead.

## Email (Gmail SMTP + MySQL queue)

Booking mails enqueue into `mail_jobs` (durable), then send via Gmail SMTP.

1. Copy SMTP settings from `.env.example` into `.env` (use a Gmail **App Password**).
2. Apply migration: `alembic upgrade head`
3. Local/dev: `MAIL_QUEUE_INLINE=true` processes one job inside the FastAPI BackgroundTask after enqueue.
4. Production: set `MAIL_QUEUE_INLINE=false` and run a worker:

```bash
python -m scripts.mail_worker
# or one-shot:
python -m scripts.mail_worker --once
```

Failed sends retry with backoff up to `MAIL_MAX_ATTEMPTS`, then move to `failed_mail_jobs`.
