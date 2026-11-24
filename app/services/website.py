"""Company website scraping, LinkedIn search snippet, OpenStreetMap, schema.org data."""
import json
import re
import urllib.parse as up
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from .search import search
from .utils import domain, get, tokens

SKIP_DOMAINS = ("wikipedia.org", "linkedin.com", "facebook.com", "twitter.com", "x.com",
                "crunchbase.com", "bloomberg.com", "youtube.com", "instagram.com",
                "glassdoor.com", "indeed.com", "reddit.com", "zoominfo.com")



def guess_site(name, hint=""):
    cands = [u for _, u, _ in search(f"{name} {hint} official website") if u.startswith("http")
             and not any(d in domain(u) for d in SKIP_DOMAINS)]
    key = "".join(sorted(tokens(name), key=len))[:6]
    for u in cands:  # prefer a domain that contains part of the company name
        if any(t in domain(u).replace("-", "") for t in tokens(name)) or key in domain(u):
            return f"{up.urlparse(u).scheme}://{up.urlparse(u).netloc}"
    return None  # refuse to guess: a wrong website is worse than none


def linkedin_info(name, hint=""):
    """Public LinkedIn search-result snippet only (we never scrape LinkedIn itself)."""
    for _, url, sn in search(f"{name} {hint} site:linkedin.com/company"):
        slug = url.split("linkedin.com/company/")[-1].split("/")[0].replace("-", " ")
        if "linkedin.com/company" in url and tokens(name) & tokens(slug):
            g = lambda pat: (re.search(pat, sn) or [None, None])[1]
            return {"url": url, "snippet": sn,
                    "size": g(r"(\d[\d,]*(?:\s*[-–]\s*\d[\d,]*)?\+?)\s+employees"),
                    "hq": g(r"Headquarters:?\s*([^·|]+?)(?:\s{2,}|·|\||Industry|$)"),
                    "industry": g(r"Industry:?\s*([^·|]+?)(?:\s{2,}|·|\||$)")}
    return {}


def osm_info(name, hint=""):
    """OpenStreetMap Nominatim (free): address and phone for local businesses."""
    r = get("https://nominatim.openstreetmap.org/search", params={
        "q": f"{name} {hint}".strip(), "format": "json", "limit": 1,
        "addressdetails": 1, "extratags": 1})
    try:
        d = r.json()[0]
    except Exception:
        return {}
    if not tokens(name) <= tokens(d["display_name"].split(",")[0]):
        return {}
    x = d.get("extratags") or {}
    return {"address": d["display_name"], "phone": x.get("phone") or x.get("contact:phone"),
            "email": x.get("email") or x.get("contact:email"),
            "url": f"https://www.openstreetmap.org/{d['osm_type']}/{d['osm_id']}"}



PATHS = ["", "/contact", "/contact-us", "/about", "/about-us", "/team", "/leadership",
         "/our-team", "/company", "/about/leadership", "/company/leadership"]
TITLE = re.compile(r"\b(CEO|CTO|CFO|COO|CMO|CRO|Chief [A-Z][a-z]+ Officer|Chief Executive|"
                   r"Co-?Founder|Founder|Owner|Proprietor|Partner|Principal|President|Chairman|"
                   r"Chair|Managing Director|Director|Vice President|VP|Head of [A-Z]\w+)\b")
NAME = re.compile(r"^[A-Z][a-zA-Z'’.-]+(?: [A-Z][a-zA-Z'’.-]+){1,3}$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
JUNK = (".png", ".jpg", ".svg", ".gif", "sentry", "example.", "wixpress", "@2x")
ORG = re.compile(r"Organization|Corporation|LocalBusiness|Store|Restaurant|Company|Service|Shop", re.I)


def parse_people(soup, url):
    soup = BeautifulSoup(str(soup), "html.parser")
    for t in soup(["script", "style", "nav", "footer", "noscript"]):
        t.decompose()
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    found = []
    for i, l in enumerate(lines):
        if len(l) > 90:
            continue
        parts = re.split(r"\s*[,|–—]\s*|\s+-\s+", l, maxsplit=1)
        if len(parts) == 2 and NAME.match(parts[0]) and TITLE.search(parts[1]):
            found.append((parts[0], parts[1], url))
        elif TITLE.search(l):
            for j in (i - 1, i + 1):
                if 0 <= j < len(lines) and NAME.match(lines[j]) and not TITLE.search(lines[j]):
                    found.append((lines[j], l, url))
                    break
    return found


def jsonld_profile(soup):
    """schema.org data that many small-business sites embed (address, phone, founder...)."""
    P = {}
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        items = []
        for d in (data if isinstance(data, list) else [data]):
            if isinstance(d, dict):
                items += d.get("@graph", [d])
        for d in items:
            if not isinstance(d, dict):
                continue
            t = d.get("@type")
            if not ORG.search(" ".join(t) if isinstance(t, list) else str(t or "")):
                continue
            for k, f in (("description", "description"), ("phone", "telephone"),
                         ("email", "email"), ("founded", "foundingDate")):
                if isinstance(d.get(f), str):
                    P.setdefault(k, d[f][:4] if k == "founded" else d[f])
            ad = d.get("address")
            if isinstance(ad, dict):
                P.setdefault("address", ", ".join(str(ad[k]) for k in (
                    "streetAddress", "addressLocality", "addressRegion", "postalCode",
                    "addressCountry") if isinstance(ad.get(k), (str, int))))
            elif isinstance(ad, str):
                P.setdefault("address", ad)
            ne = d.get("numberOfEmployees")
            if isinstance(ne, dict):
                ne = ne.get("value") or "-".join(str(ne[k]) for k in ("minValue", "maxValue") if ne.get(k))
            if ne:
                P.setdefault("employees", str(ne))
            fo = d.get("founder") or d.get("founders")
            for f in (fo if isinstance(fo, list) else [fo]):
                n = f.get("name") if isinstance(f, dict) else f
                if isinstance(n, str):
                    P.setdefault("founders", []).append(n)
    return P


def scrape_site(site):
    base = site.rstrip("/")
    with ThreadPoolExecutor(6) as ex:
        resps = list(ex.map(get, [base + p for p in PATHS]))
    emails, phones, socials, people, prof = [], [], [], [], {}
    for p, r in zip(PATHS, resps):
        url = base + p
        if not r or "html" not in r.headers.get("content-type", ""):
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for k, v in jsonld_profile(soup).items():
            prof.setdefault(k, (v, url))
        if p == "":
            m = (soup.find("meta", attrs={"name": "description"})
                 or soup.find("meta", attrs={"property": "og:description"}))
            if m and m.get("content"):
                prof.setdefault("meta", (m["content"].strip(), url))
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if h.startswith("mailto:"):
                emails.append((h[7:].split("?")[0], url))
            elif h.startswith("tel:"):
                phones.append((h[4:].strip(), url))
            elif re.search(r"linkedin\.com/company|twitter\.com/|x\.com/", h):
                socials.append((h, url))
        for e in EMAIL.findall(r.text):
            if not any(j in e.lower() for j in JUNK):
                emails.append((e, url))
        if any(k in p for k in ("team", "leader", "about", "company")):
            people += parse_people(soup, url)
    for k, kind in (("email", emails), ("phone", phones)):
        if k in prof:
            kind.append(prof[k])
    uniq = lambda xs: list({x[0].lower(): x for x in xs}.values())
    return uniq(emails)[:4], uniq(phones)[:3], uniq(socials)[:2], uniq(people)[:8], prof
