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
alembic upgrade head    # creates the full schema from scratch
python scripts/seed.py  # loads production content (provinces/routes/trips/
                         # users/etc.) — pass --force to allow running against
                         # an environment whose APP_ENV looks like production
```

Seed JSON lives in `app/infrastructure/persistence/seed_data/`.

Admin login after seeding: `admin@kingexpressbus.com` / `Admin@123`. The other
13 seeded users keep their existing bcrypt hashes (no known plaintext password —
reset required to log in as them).

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
