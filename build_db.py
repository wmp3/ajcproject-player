"""Populate the items table from the archive.org 'aadamjacobs' collection.

Run: python build_db.py [--limit N]

Idempotent: re-running updates rows via ON CONFLICT (primary key).
Safe to interrupt; resume by running again.
"""
import argparse
import re
import sys
import time

import requests
from sqlalchemy.dialects.postgresql import insert

from app import app
from models import Item, db

SCRAPE_URL = "https://archive.org/services/search/v1/scrape"
METADATA_URL = "https://archive.org/metadata/{identifier}"
COLLECTION = "aadamjacobs"
PAGE_SIZE = 1000

VENUE_RE = re.compile(r"\bLive at\s+(.+?)(?:\s+on)?\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE)


def first(val):
    if isinstance(val, list):
        return val[0] if val else None
    return val


def parse_venue(title: str | None) -> str | None:
    if not title:
        return None
    m = VENUE_RE.search(title)
    return m.group(1).strip() if m else None


def scrape_identifiers():
    session = requests.Session()
    cursor = None
    fields = "identifier,title,creator,date,description"
    while True:
        params = {
            "q": f"collection:{COLLECTION} AND mediatype:audio",
            "fields": fields,
            "count": PAGE_SIZE,
        }
        if cursor:
            params["cursor"] = cursor
        r = session.get(SCRAPE_URL, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            yield item
        cursor = data.get("cursor")
        if not cursor:
            break


def fetch_files(session: requests.Session, identifier: str) -> list[dict]:
    r = session.get(METADATA_URL.format(identifier=identifier), timeout=60)
    r.raise_for_status()
    data = r.json()
    files = []
    for f in data.get("files", []):
        fmt = (f.get("format") or "").upper()
        name = f.get("name", "")
        if "MP3" in fmt and name.lower().endswith(".mp3"):
            files.append({
                "name": name,
                "title": f.get("title") or name,
                "track": f.get("track"),
                "length": f.get("length"),
            })
    files.sort(key=lambda x: x["name"])
    return files


def upsert(rows: list[dict]):
    stmt = insert(Item).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["identifier"],
        set_={c: stmt.excluded[c] for c in ("title", "creator", "date", "venue", "description", "files")},
    )
    db.session.execute(stmt)
    db.session.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=25)
    args = ap.parse_args()

    http = requests.Session()
    http.headers["User-Agent"] = "ajcproject-player/0.1"

    processed = 0
    batch: list[dict] = []
    with app.app_context():
        for meta in scrape_identifiers():
            ident = meta["identifier"]
            try:
                files = fetch_files(http, ident)
            except requests.RequestException as e:
                print(f"  ! {ident}: {e}", file=sys.stderr)
                continue

            title = first(meta.get("title"))
            batch.append({
                "identifier": ident,
                "title": title,
                "creator": first(meta.get("creator")),
                "date": first(meta.get("date")),
                "venue": parse_venue(title),
                "description": first(meta.get("description")),
                "files": files,
            })
            processed += 1
            print(f"[{processed}] {ident} ({len(files)} mp3)")

            if len(batch) >= args.batch:
                upsert(batch)
                batch = []

            if args.limit and processed >= args.limit:
                break
            time.sleep(0.05)

        if batch:
            upsert(batch)

    print(f"Done. {processed} items.")


if __name__ == "__main__":
    main()
