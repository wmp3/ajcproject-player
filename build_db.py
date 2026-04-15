"""Populate the items table from the archive.org 'aadamjacobs' collection.

Registered as a Flask CLI command:

    flask build-db                 # full run (~2,121 items)
    flask build-db --limit 50      # smoke test
    flask build-db --batch 50      # larger commit batches

Idempotent: re-running updates rows via ON CONFLICT.
"""

import re
import sys
import time

import click
import requests
from flask.cli import with_appcontext
from sqlalchemy.dialects.postgresql import insert

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


def parse_venue(title):
    if not title:
        return None
    m = VENUE_RE.search(title)
    return m.group(1).strip() if m else None


def scrape_identifiers(http):
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
        r = http.get(SCRAPE_URL, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            yield item
        cursor = data.get("cursor")
        if not cursor:
            break


def fetch_files(http, identifier):
    r = http.get(METADATA_URL.format(identifier=identifier), timeout=60)
    r.raise_for_status()
    data = r.json()
    files = []
    for f in data.get("files", []):
        fmt = (f.get("format") or "").upper()
        name = f.get("name", "")
        if "MP3" in fmt and name.lower().endswith(".mp3"):
            files.append(
                {
                    "name": name,
                    "title": f.get("title") or name,
                    "track": f.get("track"),
                    "length": f.get("length"),
                }
            )
    files.sort(key=lambda x: x["name"])
    return files


def upsert(rows):
    stmt = insert(Item).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["identifier"],
        set_={
            c: stmt.excluded[c]
            for c in ("title", "creator", "date", "venue", "description", "files")
        },
    )
    db.session.execute(stmt)
    db.session.commit()


@click.command("build-db")
@click.option("--limit", type=int, default=None, help="Only process first N items")
@click.option(
    "--batch", type=int, default=25, show_default=True, help="DB commit batch size"
)
@click.option(
    "--sleep",
    type=float,
    default=0.05,
    show_default=True,
    help="Seconds between metadata calls",
)
@with_appcontext
def build_db_command(limit, batch, sleep):
    """Scrape the aadamjacobs collection and upsert into the items table."""
    http = requests.Session()
    http.headers["User-Agent"] = "ajcproject-player/0.1"

    processed = 0
    pending = []
    for meta in scrape_identifiers(http):
        ident = meta["identifier"]
        try:
            files = fetch_files(http, ident)
        except requests.RequestException as e:
            click.echo(f"  ! {ident}: {e}", err=True)
            continue

        title = first(meta.get("title"))
        pending.append(
            {
                "identifier": ident,
                "title": title,
                "creator": first(meta.get("creator")),
                "date": first(meta.get("date")),
                "venue": parse_venue(title),
                "description": first(meta.get("description")),
                "files": files,
            }
        )
        processed += 1
        click.echo(f"[{processed}] {ident} ({len(files)} mp3)")

        if len(pending) >= batch:
            upsert(pending)
            pending = []

        if limit and processed >= limit:
            break
        time.sleep(sleep)

    if pending:
        upsert(pending)

    click.echo(f"Done. {processed} items.")
