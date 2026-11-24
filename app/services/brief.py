"""Assembles the brief from every source (Wikipedia, Wikidata, site, LinkedIn snippet, news...)."""
import datetime as dt
import logging
import urllib.parse as up

from . import search as search_mod
from . import utils
from .people import find_people, rank_role
from .search import more_sources, news, search
from .talking import talking_points
from .utils import domain, first_sentences
from .website import guess_site, linkedin_info, osm_info, scrape_site
from .wiki import wiki_find, wikidata


def build(name, hint=""):
    B = {"query": name, "matched": None, "overview": None, "facts": [], "news": [],
         "people": [], "contacts": [], "talking": [], "notes": [],
         "generated": dt.date.today().isoformat()}
    LOC = ("Headquarters", "Address")

    def safe(fn, default, label):
        """Run one data source; if it breaks, keep going and note what is missing."""
        try:
            return fn()
        except Exception as e:
            logging.getLogger(__name__).exception("%s lookup failed", label)
            B["notes"].append((f"{label} lookup failed ({type(e).__name__}), so that part is missing.", None))
            return default

    def fact(label, value, url):
        have = {f[0] for f in B["facts"]}
        if value and label not in have and not (label in LOC and have & set(LOC)):
            B["facts"].append((label, str(value).strip(), url))

    def person(n, role, url):
        if n.lower() not in {p[0].lower() for p in B["people"]}:
            B["people"].append((n, role, url))

    site = None
    search_mod._ok[0] = 0
    utils.FAILS.clear()
    wp, alts = safe(lambda: wiki_find(name, hint), (None, []), "Wikipedia")
    B["more"] = []
    if wp:
        B["matched"] = wp["title"]
        B["overview"] = (first_sentences(wp["extract"]), wp["url"])
        if wp["qid"]:
            wd, src = safe(lambda: wikidata(wp["qid"]), {}, "Wikidata"), f"https://www.wikidata.org/wiki/{wp['qid']}"
            for label, key in [("Industry", "industry"), ("Employees", "employees"),
                               ("Headquarters", "hq"), ("Country", "country"), ("Founded", "founded")]:
                fact(label, wd.get(key), src)
            for key, role in [("ceo", "CEO"), ("chair", "Chair"), ("founders", "Founder")]:
                for p in wd.get(key, [])[:2]:
                    person(p, role, src)
            site = wd.get("website")
    wiki_people = len(B["people"])  # leaders found on Wikipedia/Wikidata
    site = site or safe(lambda: guess_site(name, hint), None, "Website search")
    prof = {}
    if site:
        fact("Website", site, site)
        emails, phones, socials, people, prof = safe(lambda: scrape_site(site), ([], [], [], [], {}), "Company website")
        B["contacts"] += [("Email", e, u) for e, u in emails] + [("Phone", p, u) for p, u in phones]
        B["contacts"] += [("Social", s_, u) for s_, u in socials]
        for n, role, u in people:
            person(n, role, u)
        for n in prof.get("founders", ([], None))[0]:
            person(n, "Founder", prof["founders"][1])
        for label, k in (("Address", "address"), ("Employees", "employees"), ("Founded", "founded")):
            if k in prof:
                fact(label, *prof[k])
        if not B["overview"]:
            d = prof.get("description") or prof.get("meta")
            if d:
                B["overview"] = (first_sentences(d[0]), d[1])
    li = safe(lambda: linkedin_info(name, hint), {}, "LinkedIn") or {}
    if li:
        fact("Employees", li.get("size"), li["url"])
        fact("Headquarters", li.get("hq"), li["url"])
        fact("Industry", li.get("industry"), li["url"])
        B["contacts"].append(("Social", li["url"], li["url"]))
        if not B["overview"] and li["snippet"]:
            B["overview"] = (first_sentences(li["snippet"], 2), li["url"])
    if not wp and not {f[0] for f in B["facts"]} & set(LOC):  # no guessed address for a matched company
        o = safe(lambda: osm_info(name, hint), {}, "OpenStreetMap")
        if o:
            fact("Address", o["address"] + " (OpenStreetMap, verify)", o["url"])
            if o.get("phone"):
                B["contacts"].append(("Phone", o["phone"], o["url"]))
    if not B["overview"]:
        for t, u, sn in search(f"{name} {hint} about company"):
            if sn and not any(d in domain(u) for d in ("facebook.com", "instagram.com")):
                B["overview"] = (first_sentences(sn, 2) + " (search snippet)", u)
                break
    q = f"{name} {hint}".strip()
    B["news"] = safe(lambda: news(q if hint else name), [], "News")
    have = [f[2] for f in B["facts"]] + [n_[1] for n_ in B["news"]] + [c_[2] for c_ in B["contacts"]]
    B["more"] = safe(lambda: more_sources(name, hint, have), [], "Extra sources")
    # Wikipedia/Wikidata lists few leaders for most companies, so search the web separately
    # when it gave fewer than 3 (with extra queries when it gave none).
    extra = [(t_, "", u_) for t_, u_, _, _ in B["news"]] + [(t_, sn_, u_) for t_, u_, sn_ in B["more"]]
    web_search = wiki_people < 3
    before = len(B["people"])
    for n_, role_, u_ in safe(lambda: find_people(name, hint, extra, search_web=web_search, deep=wiki_people == 0),
                              [], "Decision-maker search"):
        person(n_, role_, u_)
    B["people"] = sorted(B["people"], key=lambda p_: rank_role(p_[1]))[:8]
    if len(B["people"]) > before:
        B["notes"].append((("Wikipedia/Wikidata listed too few decision-makers, so more were searched separately on the web. "
                            if web_search else "Some decision-makers came from headlines and search results. ") +
                           "These can be out of date: verify names and titles on their linked profiles.", None))
    wiki_fails = sorted({f"{h}: {r}" for h, r in utils.FAILS})
    if wiki_fails:
        B["notes"].append(("Wikipedia/Wikidata could not be reached (" + "; ".join(wiki_fails[:3]) +
                           "), so size, HQ and leaders may be missing. Wait a minute and search again.", None))
    if wp is None or alts:
        for t, u in alts:
            B["notes"].append((f"Other Wikipedia pages with a similar name (not used): {t}", u))
    B["notes"].append(("Check this is the right company. If not, re-run with a hint such as "
                       "\"India audio brand\" or the city.", None))
    if search_mod._ok[0] == 0:
        B["notes"].append(("Web search returned nothing: DuckDuckGo, Bing and Mojeek may be blocking "
                           "this network. Wait a few minutes or try another connection.", None))
    if not B["news"]:
        B["notes"].append(("No recent news retrieved (Google News RSS empty or blocked).", None))
    if not B["people"]:
        B["notes"].append(("No leaders are publicly listed on the sources searched. Look them up here:",
                           "https://www.linkedin.com/search/results/people/?keywords=" + up.quote(q)))
    if not B["facts"] and not B["overview"]:
        B["notes"].append(("Little public information found. Try the legal name, or add a city or country in the hint box.", None))
    B["talking"] = talking_points(B)
    return B

