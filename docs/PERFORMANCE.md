# SiteUnit Performance Notes

A personal tool with tens-to-hundreds of sites. No benchmarks were run for
their own sake; this records the deliberate choices and known limits.

## Backend

- **Single connection per operation**, closed on exit. Writes are short; with
  WAL + `busy_timeout=5000`, concurrent reads don't block a writer and a
  single-user load never sees `database is locked`.
- **No N+1**: `list_sites` fetches all matching rows in one query, then bulk
  loads tags for those ids in a second query (`_attach_tags`), attaching the
  result in Python. O(rows) not O(rows×tags).
- **Indexes** (migration 002) on `normalized_url` (dedup), `group_name`,
  `sort_order`, `archived`, `status`, `pinned`, and `site_tags(tag_id)` cover
  the common filter/sort paths.
- **Metadata fetch** is the only synchronous-ish cost on the create path. It
  is capped: connect/read timeouts, redirect limit, and a streaming body cap
  (`max_html_size` / `max_logo_size`) so a huge or malicious page can't exhaust
  memory or hang the request.
- **Visit recording** (`POST /api/sites/{id}/visit`) is a single fast UPDATE;
  the frontend fires it without `await` so the click-to-open latency is just
  `window.open`.
- **Bulk health/refresh** use an `asyncio.Semaphore` (default 6) so hundreds
  of sites don't produce hundreds of simultaneous outbound requests.

## Frontend

- **No build, no bundler**: the browser loads ESM modules directly. Vue's
  full ESM build (with compiler) is ~larger than a runtime-only build, but it
  is cached forever as a static asset and never re-fetched.
- **Client-side search/sort** over the loaded list — instant, no per-keystroke
  API round-trips. The server also supports token search (`group:` `tag:` …)
  for when the list is large, but for personal scale the client path is faster.
- **Logos** load lazily (`loading="lazy"`) and are addressed by stable
  url-hash filenames so they cache well and survive refetch.
- **Reactivity**: `busyIds`/`selection` are `Set`s; we reassign a new `Set` to
  trigger Vue's reactivity (cheaper than re-keying the whole list).

## Known limits / future

- `list_sites` returns all rows (no pagination). Fine to ~1k sites; revisit
  with server-side pagination or SQLite FTS5 if the registry grows into the
  thousands (ROADMAP M6).
- The module-level `app = create_app()` runs at import and is unused by the
  test path; harmless, could be made lazy.
