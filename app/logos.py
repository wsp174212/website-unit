"""Logo storage: validation, stable naming, cleanup.

Stable naming by URL hash means re-fetching the same site overwrites the same
file (no duplicate growth) and two different sites can't collide. Deleting a
site removes its file; :func:`garbage_collect` reclaims any orphans.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .config import settings

# Recognized image formats by magic bytes. Returns the canonical extension or
# None for non-images (HTML error pages pretending to be favicons, etc.).
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"RIFF", "webp"),   # verified below with WEBP tag
)


def detect_image_format(content: bytes) -> str | None:
    """Return canonical image extension (png/jpg/gif/webp/svg/ico) or None."""
    if not content:
        return None
    for magic, ext in _MAGIC:
        if content.startswith(magic):
            if ext == "webp":
                return "webp" if content[8:12] == b"WEBP" else None
            return ext
    if content[:4] == b"\x00\x00\x01\x00" or content[:4] == b"\x00\x00\x02\x00":
        return "ico"
    head = content[:512].lower()
    if content.lstrip()[:1] == b"<" and (b"<svg" in head or b"xmlns" in head and b"svg" in head):
        return "svg"
    return None


def validate_logo(content: bytes) -> str | None:
    """Return the extension if ``content`` is a real, decodable image, else None."""
    if len(content) > settings.max_logo_size:
        return None
    ext = detect_image_format(content)
    if ext is None:
        return None
    # Reject anything that is clearly markup pretending to be an image.
    if content.lstrip()[:1] == b"<" and ext != "svg":
        return None
    return ext


def content_type_hint_to_ext(content_type: str) -> str | None:
    ctype = (content_type or "").split(";")[0].strip().lower()
    mapping = {
        "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
        "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg",
        "image/x-icon": "ico", "image/vnd.microsoft.icon": "ico",
        "image/ico": "ico", "image/x-ico": "ico",
    }
    if ctype in mapping:
        return mapping[ctype]
    if ctype.startswith("image/"):
        return ctype.split("/")[1].split("+")[0]
    return None


_FILE_RE = re.compile(r"^[0-9a-f]{16}\.(png|jpg|gif|webp|svg|ico)$")


def _safe_name(filename: str) -> bool:
    return bool(_FILE_RE.match(filename or ""))


def logo_key_for(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def save_logo(content: bytes, ext: str, *, url: str) -> str:
    """Save ``content`` under a stable name derived from ``url``.

    Overwrites any prior ``<key>.*`` so a re-fetch with a new format can't
    leave an orphan. Returns the filename (not the full path).
    """
    key = logo_key_for(url)
    filename = f"{key}.{ext}"
    path = settings.logo_dir / filename
    # Remove any existing file for this key (different extension).
    for old in settings.logo_dir.glob(f"{key}.*"):
        if old.name != filename:
            try:
                old.unlink()
            except OSError:
                pass
    settings.logo_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return filename


def remove_logo(filename: str | None) -> None:
    if not filename or not _safe_name(filename):
        return
    try:
        (settings.logo_dir / filename).unlink(missing_ok=True)
    except OSError:
        pass


def logo_url_for(filename: str | None) -> str | None:
    if not filename or not _safe_name(filename):
        return None
    return f"/logos/{filename}"


def garbage_collect(keep_filenames: set[str]) -> int:
    """Delete logo files not referenced by the DB. Returns the count removed."""
    removed = 0
    d = settings.logo_dir
    if not d.exists():
        return 0
    for p in d.iterdir():
        if not p.is_file() or not _safe_name(p.name):
            continue
        if p.name in keep_filenames:
            continue
        try:
            p.unlink()
            removed += 1
        except OSError:
            pass
    return removed
