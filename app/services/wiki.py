"""Wikipedia + Wikidata lookups (free APIs): overview, size, HQ, leaders."""
import datetime as dt
import re
import urllib.parse as up
from concurrent.futures import ThreadPoolExecutor

from .utils import get, tokens

WIKI = "https://en.wikipedia.org/w/api.php"


COMPANYISH = re.compile(r"\b(company|corporation|startup|business|firm|manufacturer|retailer|"
                        r"conglomerate|brand|multinational|enterprise|bank|airline|software|"
                        r"electronics|headquartered|founded in|Pvt|Limited|Ltd|Inc|LLC|"
                        r"e-commerce|consumer goods|subsidiary)\b", re.I)


INDIA = re.compile(r"\b(India|Indian|Mumbai|Delhi|Bengaluru|Bangalore|Gurugram|Gurgaon|Noida|Chennai|"
                   r"Hyderabad|Pune|Kolkata|Ahmedabad|Maharashtra|Gujarat|Karnataka|Tamil Nadu)\b")


def pageviews(title):
    """Wikipedia views over ~2 months (free Wikimedia API): a rough 'how big is it' signal."""
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)
    start = (end.replace(day=1) - dt.timedelta(days=40)).replace(day=1)
    r = get("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/"
            f"user/{up.quote(title.replace(' ', '_'), safe='')}/monthly/{start:%Y%m%d}/{end:%Y%m%d}")
    try:
        return sum(i["views"] for i in r.json()["items"])
    except Exception:
        return 0


def wiki_find(name, hint="", prefer="india"):
    """Among same-named companies, rank: Indian (if prefer=india) and/or large (page views).
    Returns (match or None, alternatives)."""
    import math
    qs = [f"{name} {hint} company", f"{name} {hint} brand"]
    if prefer == "india" and "india" not in hint.lower():
        qs.append(f"{name} India company")
    cands, seen = [], set()
    for q in qs:
        r = get(WIKI, params={"action": "query", "list": "search", "format": "json",
                              "srsearch": q.strip(), "srlimit": 5})
        for h in (r.json()["query"]["search"] if r else []):
            if h["title"] not in seen and tokens(name) <= tokens(h["title"]):
                seen.add(h["title"])
                cands.append(h["title"])

    def load(title):
        r2 = get(WIKI, params={"action": "query", "prop": "extracts|pageprops", "exintro": 1,
                               "explaintext": 1, "titles": title, "redirects": 1, "format": "json"})
        if not r2:
            return None
        page = next(iter(r2.json()["query"]["pages"].values()))
        ext = page.get("extract", "")
        co = re.search(r"\((company|brand|business|corporation)", title, re.I) or COMPANYISH.search(ext[:300])
        return {"title": title, "extract": ext, "company": bool(co), "indian": bool(INDIA.search(ext[:700])),
                "qid": page.get("pageprops", {}).get("wikibase_item"),
                "url": "https://en.wikipedia.org/wiki/" + up.quote(title.replace(" ", "_")),
                "views": pageviews(title) if co else 0}

    with ThreadPoolExecutor(4) as ex:
        pages = [p for p in ex.map(load, cands[:6]) if p]
    for p in pages:
        p["score"] = math.log10(1 + p["views"]) + (1.0 if prefer == "india" and p["indian"] else 0)
    cos = sorted([p for p in pages if p["company"]], key=lambda p: -p["score"])
    others = [p for p in pages if not p["company"]]
    match = cos[0] if cos else None
    if match:
        match["why"] = ("Indian company" if match["indian"] else "") + \
                       (", " if match["indian"] else "") + f"{match['views']:,} Wikipedia views (~2 months)"
    alts = [(f"{p['title']} ({'Indian, ' if p['indian'] else ''}{p['views']:,} views)", p["url"]) for p in cos[1:3]]
    alts += [(p["title"] + " (not a company)", p["url"]) for p in others[:1]]
    return match, alts[:3]


def wikidata(qid):
    r = get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")
    if not r:
        return {}
    claims = r.json()["entities"][qid]["claims"]

    def vals(p):
        return [c["mainsnak"]["datavalue"]["value"] for c in claims.get(p, [])
                if c.get("mainsnak", {}).get("datavalue")]

    ids = {v["id"] for p in ("P159", "P17", "P452", "P169", "P488", "P112")
           for v in vals(p) if isinstance(v, dict) and "id" in v}
    labels = {}
    if ids:
        lr = get("https://www.wikidata.org/w/api.php", params={
            "action": "wbgetentities", "ids": "|".join(ids), "props": "labels",
            "languages": "en", "format": "json"})
        if lr:
            labels = {k: v["labels"]["en"]["value"] for k, v in lr.json()["entities"].items()
                      if "en" in v.get("labels", {})}
    names = lambda p: [labels[v["id"]] for v in vals(p) if isinstance(v, dict) and v.get("id") in labels]
    emp = vals("P1128")
    inc = vals("P571")
    web = vals("P856")
    return {"employees": f"{int(float(emp[-1]['amount'])):,}" if emp else None,
            "hq": ", ".join(names("P159")), "country": ", ".join(names("P17")),
            "industry": ", ".join(names("P452")[:3]),
            "founded": inc[0]["time"][1:5] if inc else None,
            "website": web[0] if web else None,
            "ceo": names("P169"), "chair": names("P488"), "founders": names("P112")}
