from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()
language = db.Column(db.String(10), default='en')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20))
    age = db.Column(db.Integer)
    genres = db.Column(db.String(200))
    language = language


class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    movie_title = db.Column(db.String(200))
    genres = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now())
