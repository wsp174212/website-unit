# SiteUnit Architecture

```
Browser (Vue 3 ESM, no build step)
   │  fetch /api/*
   ▼
FastAPI (app/main.py — app factory, lifespan, handlers, static mounts)
   │
   ├── app/api/sites.py      CRUD, visit, refetch, reorder, bulk, search
   ├── app/api/system.py     tags, groups, gc-logos, db-info
   ├── app/api/health.py     health check, broken links, batch refresh
   └── app/api/io.py          import/export JSON+CSV+bookmarks, backup/restore
          │
          ▼
   app/services.py  (orchestration: create/update/refetch/health/refresh)
          │
   ┌──────┴────────────────────────┐
   ▼                                 ▼
app/fetcher.py                  app/db.py  ──► SQLite (sites.db, WAL)
(SafeFetcher: SSRF guard,           │
 body cap, redirects)               └── app/migrations.py (schema_version)
   │
   ▼
app/metadata.py  (pipeline: normalize → fetch HTML → parse → rank icons → download → validate)
   │
   ▼
app/logos.py  (validate image, stable url-hash naming, garbage collect → data/logos/)
   │
   ▼
 HTTP → target website
```

## Module responsibilities & dependency direction

Dependencies point downward (toward storage / network); no upward imports.

- **config.py** — single source of truth for settings; mutable singleton mutated
  in place by `configure()` so `from .config import settings` holders stay live.
- **errors.py** — `SiteUnitError(code, message, status)` + FastAPI handlers that
  emit the unified `{"error":{"code","message"}}` envelope. Routes raise, never
  format strings.
- **urlnorm.py** — scheme allowlist + canonical dedup key. Pure, tested.
- **fetcher.py** — the only module that opens real network sockets. Enforces
  scheme + per-hop SSRF (DNS-resolved IP inspection) + body cap. Knows nothing
  about sites or DB.
- **metadata.py** — HTML parsing & icon ranking. Depends on fetcher + logos.
- **logos.py** — image validation, on-disk naming, GC. Depends on config only.
- **migrations.py** — idempotent DDL, version table, pre-migrate file backup.
- **db.py** — all SQL lives here. Connection manager (WAL, busy_timeout,
  foreign_keys, close-on-exit). Service/router layers call functions, never raw SQL.
- **services.py** — orchestrates fetcher+metadata+logos+db for the multi-step
  flows (create-with-meta, refetch, health, bulk refresh).
- **api/*.py** — thin HTTP layer: validate with Pydantic schemas, call
  services/db, serialize responses.
- **schemas.py** — Pydantic request/response models; `serialize_site()` maps the
  db row (group_name/logo_path) to the API shape (group/logo_url).

## Data flow: adding a site

1. `POST /api/sites` → `SiteCreate` validated by Pydantic.
2. `services.create_site` → `urlnorm.normalize_url` (raises INVALID_URL etc.).
3. Dedup check via `db.get_by_normalized_url` (raises SITE_ALREADY_EXISTS).
4. `fetch_site_meta(SafeFetcher, url)` → title, description, logo bytes.
5. If logo: `logos.save_logo` (validate → stable `sha1(url)[:16].ext` name).
6. `db.insert_site` (tags set via junction table).
7. `serialize_site` → `SiteOut` JSON.

## Frontend

ESM modules loaded via `<script type="module">`. No bundler, no Node. The full
ESM Vue build (vendored) includes the template compiler, so components use
runtime template strings. State is a single root Vue instance (Options API);
prefs (theme/density/sort) persist in `localStorage` and apply via
`data-theme`/`data-density` on `<html>` (set by an inline script before mount to
avoid theme flash).
