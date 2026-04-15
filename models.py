from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()


class Item(db.Model):
    __tablename__ = "items"

    identifier = db.Column(db.String, primary_key=True)
    title = db.Column(db.String)
    creator = db.Column(db.String)
    date = db.Column(db.String)
    venue = db.Column(db.String)
    description = db.Column(db.String)
    files = db.Column(JSONB, nullable=False, default=list)
    fetched_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
