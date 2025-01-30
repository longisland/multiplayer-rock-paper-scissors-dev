import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/rps_game')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '*')