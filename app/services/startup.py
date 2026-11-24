"""Extra research for small / early-stage startups (still free, no API keys).

Big companies have Wikipedia pages and plenty of news. Startups usually have neither, so this module:
  1. finds the official website by trying likely domains (acme.com, acme.io, getacme.com ...)
  2. searches startup directories, startup media and company registries
  3. reads funding stage, amount raised, investors, founding year and HQ out of the snippets
"""
import re
import urllib.parse as up
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

from .search import search
from .utils import UA, domain, first_sentences, tokens
from .wiki import INDIA

# ---------- 1. find the official website ----------
PARKED = re.compile(r"domain (?:is )?for sale|buy this domain|this domain may be for sale|"
                    r"parked (?:free|domain)|hugedomains|sedo\.com|dan\.com/buy|afternic", re.I)


def site_candidates(name, hint="", prefer="india"):
    """Likely home pages, best first. India-focused searches try .in before .io/.ai."""
    toks = re.findall(r"[a-z0-9]+", name.lower())
    if not toks:
        return []
    joined, dashed = "".join(toks), "-".join(toks)
    india = prefer == "india" or bool(INDIA.search(hint))
    tlds = [".in", ".com", ".io", ".ai", ".co", ".app"] if india else [".com", ".io", ".ai", ".co", ".in", ".app"]
    hosts = [joined + t for t in tlds]
    if len(toks) > 1:
        hosts += [dashed + ".com", dashed + ".in"]
    hosts += [p + joined + ".com" for p in ("get", "try", "use")]
    seen, out = set(), []
    for h in hosts:
        if h not in seen:
            seen.add(h)
            out.append("https://" + h)
    return out[:14]


def _fetch_home(url):
    try:
        r = requests.get(url, headers=UA, timeout=(3, 5), allow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            return r
    except Exception:
        pass
    return None


def _verified(r, name):
    """True if the page really is about this company (not a parked page or a namesake)."""
    soup = BeautifulSoup(r.text, "html.parser")
    bits = [soup.title.get_text(" ", strip=True) if soup.title else ""]
    for m in soup.find_all("meta", attrs={"property": ["og:site_name", "og:title", "og:description"]}):
        bits.append(m.get("content", ""))
    m = soup.find("meta", attrs={"name": "description"})
    bits.append(m.get("content", "") if m else "")
    bits += [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])[:4]]
    text = " ".join(bits) + " " + soup.get_text(" ", strip=True)[:1500]
    if PARKED.search(text[:3000]):
        return False
    need = tokens(name)
    return bool(need) and need <= tokens(text)


def find_site(name, hint="", prefer="india"):
    """Try likely domains in parallel; return the first one whose page mentions the company name."""
    cands = site_candidates(name, hint, prefer)
    if not cands:
        return None
    with ThreadPoolExecutor(8) as ex:
        resps = list(ex.map(_fetch_home, cands))  # map keeps the order, so best candidate wins
    for r in resps:
        if r is not None and _verified(r, name):
            p = up.urlparse(r.url)
            return f"{p.scheme}://{p.netloc}"
    return None


# ---------- 2. startup directories, media and registries ----------
FUNDING_SITES = ("crunchbase.com", "tracxn.com", "pitchbook.com", "wellfound.com", "dealroom.co")
MEDIA_SITES = ("inc42.com", "entrackr.com", "yourstory.com", "techcrunch.com", "economictimes.indiatimes.com")
LAUNCH_SITES = ("producthunt.com", "ycombinator.com", "f6s.com", "github.com", "startupindia.gov.in")
REGISTRY_IN = ("tofler.in", "zaubacorp.com", "instafinancials.com")
REGISTRY_GLOBAL = ("opencorporates.com", "find-and-update.company-information.service.gov.uk")
SKIP = ("linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com")  # handled elsewhere


def _group(name, hint, sites, extra=""):
    return f'"{name}" {hint} {extra} ({" OR ".join("site:" + s for s in sites)})'.replace("  ", " ")


def _hits(name, hint, site, queries):
    """Search results that really mention the company, scored so the right company ranks first."""
    need = tokens(name)
    ctx = tokens(hint) - need
    sd = domain(site) if site else None
    seen, out = set(), []
    for q in queries:
        for t, u, sn in search(q, 8):
            if not u.startswith("http") or u in seen or any(s in domain(u) for s in SKIP):
                continue
            blob = (t + " " + u + " " + sn).lower()
            if not need <= tokens(blob):
                continue
            seen.add(u)
            score = (2 if sd and sd in blob else 0) + (1 if ctx & tokens(blob) else 0) \
                + (1 if re.search(r"startup|founded|funding|seed|series|raised", blob) else 0)
            out.append((score, t, u, sn))
    out.sort(key=lambda x: -x[0])
    # Several same-named companies exist. If some results match our website/location, those are the
    # confident ones; the rest are returned as "loose" so the user can still look at them.
    if (sd or ctx) and any(s >= 2 for s, *_ in out):
        return [x for x in out if x[0] >= 2], [x for x in out if x[0] < 2]
    return out, []


# ---------- 3. read facts out of the snippets ----------
CUR = r"(?:Rs\.?|INR|₹|US\$|USD|\$|€|£)"
AMOUNT = (rf"{CUR}\s?(?:\d[\d.,]*\s?(?:million|billion|crore|cr|lakhs?|mn|bn|[MBK])\b|\d{{1,3}}(?:,\d{{3}})+)")
VERB = r"(?:raised|raises|raising|secured|secures|bags|bagged|closes|closed|garners|garnered|receives|received)"
FUND = re.compile(rf"\b{VERB}\b[^.$₹€£]{{0,40}}?({AMOUNT})", re.I)
STAGE = re.compile(r"\b(pre-?seed|seed|angel|bridge)[- ](?:round|funding|stage|investment)\b|"
                   r"\b(pre-?series [A-C]|series [A-F])\b", re.I)
STAGE_ORDER = ["pre seed", "angel", "seed", "bridge", "pre series a", "series a", "pre series b", "series b",
               "pre series c", "series c", "series d", "series e", "series f"]  # least to most advanced
PNAME = r"[A-Z][\w'’&-]+(?: [A-Z][\w'’&-]+){0,3}"
INVEST = re.compile(r"(?:led by|backed by|investors? (?:include|including)|participation from|funded by)\s+(" +
                    PNAME + r"(?:(?:,| and|,? &) " + PNAME + r"){0,4})")
FOUNDED = re.compile(r"\b(?:founded|launched|started|incorporated|established)\s+in\s+((?:19|20)\d{2})\b", re.I)
HQ = re.compile(r"\b(?:headquartered|based|located)\s+in\s+([A-Z][\w.-]+(?:,? [A-Z][\w.-]+){0,2})")
BASED = re.compile(r"\b([A-Z][a-z]{3,}(?: [A-Z][a-z]+)?)-based\b")
NOT_PLACES = {"Cloud", "Web", "Mobile", "Software", "Hardware", "Remote", "Home", "Office", "Data", "Tech",
              "Startup", "Subscription", "Open", "Internet", "Browser", "Desktop", "Venture", "Evidence",
              "Community", "Agent", "Product", "Service", "Platform", "Market", "Marketplace", "Fintech"}
TAIL_STOP = {"The", "It", "Its", "He", "She", "This", "In", "And", "With", "To", "For", "As", "At", "On"}


def _clean_investors(raw, company=""):
    out, own = [], tokens(company)
    for part in re.split(r",| and | & ", raw):
        words = part.strip(" .").split()
        while words and words[-1] in TAIL_STOP:
            words.pop()
        n = " ".join(words)
        if n and not re.match(r"(?i)series|seed|round|the |a |an ", n) and len(n) > 2 and n not in out \
                and not (own and own <= tokens(n)):
            out.append(n)
    return out[:5]


def read_facts(rows, company=""):
    """rows: [(title, url, snippet)] that all mention the company. Returns [(label, value, url)]."""
    amount = stage = invest = None
    founded, hq = Counter(), Counter()
    first = {}
    for t, u, sn in rows:
        text = f"{t}. {sn}"
        m = FUND.search(text)
        if m and not amount:
            amount = (m.group(1).strip(), u)
        for m in STAGE.finditer(text):
            k = re.sub(r"[-\s]+", " ", (m.group(1) or m.group(2)).lower())
            k = "pre seed" if k == "preseed" else k
            rank = STAGE_ORDER.index(k) if k in STAGE_ORDER else -1
            if rank >= 0 and (not stage or rank > stage[2]):
                stage = (k, u, rank)  # keep the most advanced stage mentioned
        m = INVEST.search(text)
        if m and not invest:
            names = _clean_investors(m.group(1), company)
            if names:
                invest = (", ".join(names), u)
        for m in FOUNDED.finditer(text):
            founded[m.group(1)] += 1
            first.setdefault(("f", m.group(1)), u)
        for m in HQ.finditer(text):
            v = m.group(1).strip(" ,.")
            if v.lower() not in ("india", "the", "a") or hq:
                hq[v] += 1
                first.setdefault(("h", v), u)
        for m in BASED.finditer(text):
            if m.group(1) not in NOT_PLACES:
                hq[m.group(1)] += 1
                first.setdefault(("h", m.group(1)), u)
    note = " (from search results, verify)"
    facts = []
    if stage:
        facts.append(("Funding stage", stage[0].title().replace("Pre ", "Pre-") + note, stage[1]))
    if amount:
        facts.append(("Funding raised", amount[0] + note, amount[1]))
    if invest:
        facts.append(("Investors", invest[0] + note, invest[1]))
    if founded:
        y = founded.most_common(1)[0][0]
        facts.append(("Founded", y + note, first[("f", y)]))
    if hq:
        v = hq.most_common(1)[0][0]
        facts.append(("Headquarters", v + note, first[("h", v)]))
    return facts


# ---------- entry point ----------
def startup_profile(name, hint="", prefer="india", site=None):
    """Targeted startup searches. Returns {'more': [(title, url, snippet)], 'extra': [(title, snippet, url)],
    'facts': [(label, value, url)]} for brief.py to merge in."""
    india = prefer == "india" or bool(INDIA.search(hint))
    queries = [
        _group(name, hint, FUNDING_SITES, "startup funding"),
        _group(name, hint, MEDIA_SITES, "startup"),
        _group(name, hint, LAUNCH_SITES),
        _group(name, hint, REGISTRY_IN if india else REGISTRY_GLOBAL),
        f'"{name}" {hint} startup founders'.replace("  ", " "),
        f'"{name}" {hint} startup raised funding seed'.replace("  ", " "),
    ]
    sure, loose = _hits(name, hint, site, queries)
    rows = [(t, u, sn) for _, t, u, sn in sure]
    more = [(t[:90], u, first_sentences(sn, 2)) for t, u, sn in rows[:8]]
    if len(more) < 3:  # too little that is certain: show name-only matches, clearly flagged
        more += [(t[:70] + " (name match only, check it is the right company)", u, first_sentences(sn, 2))
                 for _, t, u, sn in loose[:3 - len(more)]]
    return {"more": more, "extra": [(t, sn, u) for t, u, sn in rows], "facts": read_facts(rows, name)}
