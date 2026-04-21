import calendar
import os
import random
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_migrate import Migrate
from sqlalchemy import func, select

from models import Item, db


def format_date(raw):
    """Render archive.org date strings as 'August 27, 1992'."""
    if not raw:
        return ""
    stem = raw[:10]
    for fmt, out in (("%Y-%m-%d", "%B %-d, %Y"), ("%Y-%m", "%B %Y"), ("%Y", "%Y")):
        try:
            return datetime.strptime(stem[: len(fmt) + 2], fmt).strftime(out)
        except ValueError:
            continue
    return raw


def pad_date(raw, *, end):
    """Pad a partial date ('YYYY' or 'YYYY-MM') to full 'YYYY-MM-DD'."""
    if not raw:
        return None
    stem = raw[:10]
    if len(stem) == 4:
        return f"{stem}-12-31" if end else f"{stem}-01-01"
    if len(stem) == 7:
        if end:
            year, month = int(stem[:4]), int(stem[5:7])
            last_day = calendar.monthrange(year, month)[1]
            return f"{stem}-{last_day:02d}"
        return f"{stem}-01"
    return stem


load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET", "dev")

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://localhost:5432/ajcproject"
    )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db)

    from build_db import build_db_command

    app.cli.add_command(build_db_command)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/bounds")
    def date_bounds():
        min_raw, max_raw = db.session.execute(
            select(func.min(Item.date), func.max(Item.date)).where(
                Item.date.isnot(None), Item.date != ""
            )
        ).one()
        return jsonify(
            {
                "min_date": pad_date(min_raw, end=False),
                "max_date": pad_date(max_raw, end=True),
            }
        )

    @app.route("/api/venues")
    def venues():
        rows = (
            db.session.execute(
                select(Item.venue)
                .where(Item.venue.isnot(None), Item.venue != "")
                .distinct()
                .order_by(Item.venue)
            )
            .scalars()
            .all()
        )
        return jsonify({"venues": rows})

    @app.route("/api/random")
    def random_track():
        start = request.args.get("start")
        end = request.args.get("end")
        venue = request.args.get("venue")
        date_prefix = func.substring(Item.date, 1, 10)
        query = select(Item).where(func.jsonb_array_length(Item.files) > 0)
        if start:
            query = query.where(date_prefix >= start)
        if end:
            query = query.where(date_prefix <= end)
        if venue:
            query = query.where(Item.venue == venue)
        item = db.session.execute(
            query.order_by(func.random()).limit(1)
        ).scalar_one_or_none()

        if item is None:
            return jsonify({"error": "no tracks in database"}), 404

        file_entry = random.choice(item.files)

        return jsonify(
            {
                "identifier": item.identifier,
                "artist": item.creator or "Unknown Artist",
                "date": format_date(item.date),
                "venue": item.venue or "",
                "title": item.title or "",
                "track_title": file_entry.get("title") or file_entry["name"],
                "audio_url": f"https://archive.org/download/{item.identifier}/{file_entry['name']}",
                "details_url": f"https://archive.org/details/{item.identifier}",
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
