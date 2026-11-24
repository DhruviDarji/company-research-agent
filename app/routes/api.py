"""JSON and file-download API, mounted at /api."""
import io
import re

from flask import Blueprint, current_app, jsonify, request, send_file

from ..services import to_pdf, to_xlsx
from ..services.service import get_brief, public

api = Blueprint("api", __name__)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def brief_or_error():
    qs = {k: v.strip() for k, v in request.args.items()}
    if not qs.get("q"):
        return None, (jsonify(error="Missing required parameter 'q' (company name)"), 400)
    try:
        return get_brief(qs), None
    except Exception as e:  # one bad lookup must never crash the server
        current_app.logger.exception("brief failed")
        return None, (jsonify(error=str(e)), 500)


def filename(ext):
    return re.sub(r"\W+", "_", request.args["q"]) + "_brief." + ext


@api.get("/health")
def health():
    return jsonify(status="ok")


@api.get("/brief")
def brief():
    B, err = brief_or_error()
    return err or jsonify(public(B))


@api.get("/pdf")
def pdf():
    B, err = brief_or_error()
    if err:
        return err
    buf = io.BytesIO()
    to_pdf(B, buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename("pdf"))


@api.get("/xlsx")
def xlsx():
    B, err = brief_or_error()
    if err:
        return err
    buf = io.BytesIO()
    to_xlsx(B, buf)
    buf.seek(0)
    return send_file(buf, mimetype=XLSX, as_attachment=True, download_name=filename("xlsx"))
