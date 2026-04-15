import os
import random

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from flask_migrate import Migrate
from sqlalchemy import func, select

from models import Item, db

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET", "dev")

    database_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/ajcproject")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/random")
    def random_track():
        item = db.session.execute(
            select(Item)
            .where(func.jsonb_array_length(Item.files) > 0)
            .order_by(func.random())
            .limit(1)
        ).scalar_one_or_none()

        if item is None:
            return jsonify({"error": "no tracks in database"}), 404

        file_entry = random.choice(item.files)
        track_index = item.files.index(file_entry) + 1

        return jsonify({
            "identifier": item.identifier,
            "artist": item.creator or "Unknown Artist",
            "date": item.date or "",
            "venue": item.venue or "",
            "title": item.title or "",
            "track_title": file_entry.get("title") or file_entry["name"],
            "track_index": track_index,
            "embed_url": f"https://archive.org/embed/{item.identifier}?playlist=1&track={track_index}",
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
