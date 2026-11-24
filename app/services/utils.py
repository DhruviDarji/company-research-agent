"""Shared helpers: HTTP GET wrapper, URL/text utilities."""
import logging
import os
import re
import time
import urllib.parse as up

import requests

UA = {"User-Agent": os.environ.get("USER_AGENT", "CompanyResearchAgent/1.0 (personal research tool)")}
WIKI_HOSTS = ("wikipedia.org", "wikidata.org", "wikimedia.org")
FAILS = []  # (host, reason) for failed Wikipedia/Wikidata calls during the current brief
log = logging.getLogger(__name__)


def get(url, **kw):
    """GET with a timeout. Wikipedia/Wikidata calls are retried on rate limits and network errors;
    failures are logged and remembered so the brief can say what is missing."""
    host = up.urlparse(url).netloc
    wiki = host.endswith(WIKI_HOSTS)
    reason = None
    for attempt in range(3 if wiki else 1):
        try:
            r = requests.get(url, headers=UA, timeout=8, **kw)
            if wiki and r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                reason = f"HTTP {r.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            reason = f"HTTP {e.response.status_code}"
            break
        except Exception as e:
            reason = type(e).__name__
            if wiki and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
    if wiki and reason:
        FAILS.append((host, reason))
        log.warning("GET %s failed: %s", url.split("?")[0], reason)
    return None


def domain(u):
    return up.urlparse(u).netloc.replace("www.", "")



def tokens(x):
    return {t for t in re.findall(r"[a-z0-9]+", x.lower()) if len(t) > 1}



def first_sentences(text, n=3):
    return " ".join(re.split(r"(?<=[.!?])\s+", text.strip())[:n])

