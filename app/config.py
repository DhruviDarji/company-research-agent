"""Settings, read from environment variables."""
import os

class Config:
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", 8000))
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")