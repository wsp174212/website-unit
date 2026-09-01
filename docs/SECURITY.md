# SiteUnit Security Notes

SiteUnit is a **local-first, single-user** tool. The threat model assumes the
operator runs it on their own machine (or exposes it to a trusted LAN). It is
**not** a multi-tenant SaaS and ships without authentication by design.

## Network exposure

- Default bind is `127.0.0.1` — reachable only on the local machine.
- `--host 0.0.0.0` (or `SITEUNIT_HOST=0.0.0.0`) exposes it to the LAN. Anyone
  on the network can then read/modify your site registry and trigger fetches.
  Only do this on a trusted network. An optional password gate is on the
  roadmap (Phase 44), not yet implemented.

## SSRF

Because SiteUnit fetches arbitrary user-supplied URLs (to scrape titles/icons),
SSRF is the primary risk. Mitigations in `app/fetcher.py`:

- **Scheme allowlist**: only `http`/`https`. `file:`, `ftp:`, `data:`,
  `javascript:` are rejected at normalize time.
- **Per-hop validation**: every request (including redirects) is checked
  against a request hook that resolves the hostname and inspects IPs.
- **Always-blocked ranges**: link-local (`169.254.0.0/16`, `fe80::/10`),
  unspecified, multicast, and reserved addresses are blocked **regardless** of
  the private-fetch toggle — this closes cloud-metadata SSRF
  (`169.254.169.254`) even when private fetch is allowed.
- **Private/loopback toggle**: `SITEUNIT_ALLOW_PRIVATE_NETWORK_FETCH`
  (default `true` for local-first use, so LAN/localhost sites remain
  navigable). Set `false` in cloud deployments to block all RFC1918/loopback.
- **DNS rebind**: defended by resolving the hostname ourselves and checking
  the resolved IPs (not trusting the URL string alone).
- **Body cap**: HTML and logo downloads are capped (`SITEUNIT_MAX_HTML_SIZE`,
  `SITEUNIT_MAX_LOGO_SIZE`); streaming stops at the limit.
- **Redirect cap**: `fetch_redirect_limit` (default 5).

## TLS

`SITEUNIT_VERIFY_TLS` defaults to `true`. Self-signed sites will fail logo
fetch and fall back to a letter avatar; set `false` only if you understand the
MITM risk on your network.

## Untrusted HTML / XSS

- Page HTML from fetched sites is parsed server-side by BeautifulSoup and
  **never** sent to the browser. Only the extracted title/description strings
  are stored and returned — Vue escapes them in templates.
- Logos are served from `/logos/*` as static files. SVG icons are stored as
  `.svg` but only ever rendered via `<img>` (sandboxed; scripts in SVG do not
  run under `<img>`).

## Import / backup safety

- **Bookmarks/JSON/CSV import** is server-parsed; URLs are re-normalized, so
  `javascript:`/`file:` bookmarks are dropped as invalid.
- **Restore** validates every zip entry against a path-traversal guard (no
  absolute paths, no `..`, only `sites.db` / `manifest.json` / `logos/*`),
  backs up current data before replacing, and runs migrations on the restored DB.

## Authentication absence

There is no login. If you expose SiteUnit beyond localhost, put it behind a
reverse proxy with auth, or restrict by network ACL. Do not expose it directly
to the public internet as-is.

## Reporting

Found a security issue? Treat this as a personal tool and harden locally per
the knobs above.
