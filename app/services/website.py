"""Company website scraping, LinkedIn search snippets, OpenStreetMap, schema.org data."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
import urllib.parse as up

from bs4 import BeautifulSoup

from .search import search
from .utils import domain, get, tokens

SKIP_DOMAINS = ("wikipedia.org", "linkedin.com", "facebook.com", "twitter.com", "x.com",
                "crunchbase.com", "bloomberg.com", "youtube.com", "instagram.com",
                "glassdoor.com", "indeed.com", "reddit.com", "zoominfo.com")


def guess_site(name, hint="", prefer="india"):
    res = search(f"{name} {hint} official website")
    if prefer == "india" and "india" not in hint.lower():
        res = search(f"{name} India official website") + res
    cands = [u for _, u, _ in res if u.startswith("http")
             and not any(d in domain(u) for d in SKIP_DOMAINS)
             and any(t in domain(u).replace("-", "") for t in tokens(name))]
    if prefer == "india":
        cands.sort(key=lambda u: not domain(u).endswith(".in"))  # stable: .in first
    if cands:
        p = up.urlparse(cands[0])
        return f"{p.scheme}://{p.netloc}"
    return None  # refuse to guess: a wrong website is worse than none


def norm_url(u):
    if not u:
        return None
    u = u.strip()
    return u if u.startswith("http") else "https://" + u


def linkedin_info(name, hint="", url=None):
    """Public LinkedIn search-result snippet only (we never scrape LinkedIn itself).
    If the user gave the company's LinkedIn URL, that exact page is used."""
    slug = url.rstrip("/").split("/company/")[-1].split("/")[0] if url and "/company/" in url else None
    q = f"{slug.replace('-', ' ')} site:linkedin.com/company" if slug else f"{name} {hint} site:linkedin.com/company"
    for _, u, sn in search(q):
        s_ = u.split("linkedin.com/company/")[-1].split("/")[0]
        ok = (s_.lower() == slug.lower()) if slug else bool(tokens(name) & tokens(s_.replace("-", " ")))
        if "linkedin.com/company" in u and ok:
            g = lambda pat: (re.search(pat, sn) or [None, None])[1]
            return {"url": url or u, "snippet": sn,
                    "size": g(r"(\d[\d,]*(?:\s*[-–]\s*\d[\d,]*)?\+?)\s+employees"),
                    "hq": g(r"Headquarters:?\s*([^·|]+?)(?:\s{2,}|·|\||Industry|$)"),
                    "industry": g(r"Industry:?\s*([^·|]+?)(?:\s{2,}|·|\||$)")}
    return {"url": url, "snippet": ""} if url else {}


def parse_about(text):
    """Facts from text the user pasted from the LinkedIn About section."""
    end = r"(?=\s*(?:\.\s+(?=[A-Za-z ]{3,20}:)|·|\||\n|$))"
    g = lambda pat: ((re.search(pat, text, re.I) or [None, None])[1] or "").strip(" .") or None
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    desc = " ".join(x for x in sents[:2] if ":" not in x)
    return {"size": g(r"(\d[\d,]*(?:\s*[-–]\s*\d[\d,]*)?\+?)\s+employees") or g(r"company size:?\s*([\d,\-–+]+)"),
            "hq": g(r"headquarters:?\s*(.+?)" + end), "industry": g(r"industry:?\s*(.+?)" + end),
            "founded": g(r"founded:?\s*(\d{4})"), "desc": desc}


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


# ---------- Company website scrape ----------
PATHS = ["", "/contact", "/contact-us", "/about", "/about-us", "/team", "/leadership", "/our-team",
         "/company", "/about/leadership", "/company/leadership", "/management", "/management-team",
         "/leadership-team", "/board", "/board-of-directors", "/founders", "/people", "/who-we-are",
         "/about-us/team", "/about/team", "/our-story", "/company/about-us"]
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
            if str(t) == "Person" and isinstance(d.get("name"), str) and isinstance(d.get("jobTitle"), str):
                P.setdefault("persons", []).append((d["name"], d["jobTitle"]))
                continue
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
    with ThreadPoolExecutor(8) as ex:
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
            hs = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])]
            prof["headings"] = ([h for h in hs if 3 < len(h) < 100][:8], url)
            links = " ".join((a.get_text(" ", strip=True) + " " + a["href"]).lower()
                             for a in soup.find_all("a", href=True))
            sig = [k for k in ("careers", "jobs", "pricing", "blog", "press", "investors", "partners",
                               "customers", "case-stud", "docs", "shop", "cart") if k in links]
            prof["signals"] = (sig, url)
            prof["text"] = (soup.get_text(" ", strip=True)[:3000], url)
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
        if any(k in p for k in ("team", "leader", "about", "company", "manage", "board", "founder", "people", "who-we", "story")):
            people += parse_people(soup, url)
    for k, kind in (("email", emails), ("phone", phones)):
        if k in prof:
            kind.append(prof[k])
    uniq = lambda xs: list({x[0].lower(): x for x in xs}.values())
    return uniq(emails)[:4], uniq(phones)[:3], uniq(socials)[:2], uniq(people)[:8], prof
