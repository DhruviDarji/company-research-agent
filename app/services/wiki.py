"""Wikipedia + Wikidata lookups (free APIs): overview, size, HQ, leaders."""
import re
import urllib.parse as up

from .utils import get, tokens

WIKI = "https://en.wikipedia.org/w/api.php"


COMPANYISH = re.compile(r"\b(company|corporation|startup|business|firm|manufacturer|retailer|"
                        r"conglomerate|brand|multinational|enterprise|bank|airline|software|"
                        r"electronics|headquartered|founded in|Pvt|Limited|Ltd|Inc|LLC|"
                        r"e-commerce|consumer goods|subsidiary)\b", re.I)


def wiki_find(name, hint=""):
    """Pick the Wikipedia page that is a *company* (so 'boAt' is not the vessel 'Boat').
    Returns (match or None, alternative candidates)."""
    cands, seen = [], set()
    for q in (f"{name} {hint} company", f"{name} {hint} brand", f"{name} {hint}"):
        r = get(WIKI, params={"action": "query", "list": "search", "format": "json",
                              "srsearch": q.strip(), "srlimit": 5})
        for h in (r.json()["query"]["search"] if r else []):
            if h["title"] not in seen and tokens(name) <= tokens(h["title"]):
                seen.add(h["title"])
                cands.append(h["title"])
    match, alts = None, []
    for title in cands[:6]:
        r2 = get(WIKI, params={"action": "query", "prop": "extracts|pageprops", "exintro": 1,
                               "explaintext": 1, "titles": title, "redirects": 1, "format": "json"})
        if not r2:
            continue
        page = next(iter(r2.json()["query"]["pages"].values()))
        ext = page.get("extract", "")
        url = "https://en.wikipedia.org/wiki/" + up.quote(title.replace(" ", "_"))
        is_co = re.search(r"\((company|brand|business|corporation)", title, re.I) or COMPANYISH.search(ext[:300])
        if is_co and not match:
            match = {"title": title, "extract": ext, "url": url,
                     "qid": page.get("pageprops", {}).get("wikibase_item")}
        elif title != (match or {}).get("title"):
            alts.append((title, url))
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

