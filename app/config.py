"""Settings, read from environment variables."""
import os


class Config:
<<<<<<< HEAD
    HOST = os.environ.get("HOST", "127.0.0.1")
=======
    HOST = os.environ.get("HOST", "0.0.0.0")
>>>>>>> cca472d4b1c5a06c875bb010895590d5edf2269a
    PORT = int(os.environ.get("PORT", 8000))
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
