"""HTML pages (rendered from frontend/templates)."""
from flask import Blueprint, render_template

pages = Blueprint("pages", __name__)


@pages.get("/")
def index():
    return render_template("index.html")
