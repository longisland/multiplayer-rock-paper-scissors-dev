import os
import secrets

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(16))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://rps_user:rps_password@localhost:5432/rps_db')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    INITIAL_COINS = 100
    MATCH_TIMEOUT = 30.0  # seconds
    
    # Telegram settings
    BOT_TOKEN = os.getenv('BOT_TOKEN', '7801495507:AAHhi-8ader_tX6_iJLOrdQQgKLcSP1uKbU')
    BASE_URL = os.getenv('BASE_URL', 'https://rockpaperscissors.fun')

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False