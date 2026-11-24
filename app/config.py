"""Settings, read from environment variables."""
import os


class Config:
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", 8000))
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
