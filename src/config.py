import os
import secrets

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(16))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    INITIAL_COINS = 100
    MATCH_TIMEOUT = 10.0  # seconds