from app import app, db
from models import Player, Match

def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")