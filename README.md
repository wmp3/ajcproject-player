# ajcproject-player

A small Flask app that builds a database of tracks from the
[aadam jacobs collection](https://archive.org/details/@aadam_jacobs_collection)
on the Internet Archive and plays a random track on demand.

## Stack

- Flask + Flask-SQLAlchemy + Flask-Migrate (Alembic)
- PostgreSQL
- Vanilla JS + native `<audio>` element (streams directly from `archive.org/download/...`)
- Styled to match [aadamjacobscollection.org](https://aadamjacobscollection.org) (Manrope / Fira Code, Twenty Twenty-Five palette)

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

createdb ajcproject
cp .env.example .env   # edit DATABASE_URL if needed

export FLASK_APP=app.py
flask db upgrade           # apply migrations
flask build-db --limit 50  # seed a small subset for testing (drop --limit for all ~2,121)

flask run                  # http://localhost:5000
```

## Project layout

```
app.py                 # Flask app factory, routes, CLI registration
models.py              # SQLAlchemy models (single Item table)
build_db.py            # `flask build-db` click command — scrapes archive.org + upserts
templates/index.html   # Single-page UI
migrations/            # Alembic migrations (managed via flask-migrate)
Procfile               # Railway/Heroku-style process definitions
railway.json           # Railway build + deploy config
```

### Data model

One row per archive.org item. The `files` JSONB column holds an array of MP3
files for that item, e.g.:

```json
[{"name": "01 Tim Tuten intro.mp3", "title": "Tim Tuten intro", "track": "1", "length": "09:38"}, ...]
```

`/api/random` picks a random item (where `files` is non-empty) and then a
random file within it.

### Venue parsing

Archive.org items don't have a `venue` field populated on this collection.
Titles follow the pattern `"<artist> Live at <venue> YYYY-MM-DD"`, so
`build_db.py` parses the venue out of the title via regex.

## Deployment (Railway)

1. Push this repo to GitHub.
2. Create a new Railway project and connect the GitHub repo.
3. Add the **Postgres** plugin — `DATABASE_URL` is injected automatically.
4. On the web service, set environment variables:
   - `FLASK_APP=app.py`
   - `FLASK_SECRET=<random string>`
5. Deploy. The `release` phase in `Procfile` runs `flask db upgrade` before the
   web server starts.
6. Seed the DB once:
   ```bash
   railway run flask build-db
   ```

## Schema changes

```bash
# edit models.py, then:
flask db migrate -m "describe the change"
# review migrations/versions/<new file>
flask db upgrade
```
