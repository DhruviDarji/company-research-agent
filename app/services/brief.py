"""Assembles the full brief by combining every source."""
import datetime as dt
import logging
import re
import urllib.parse as up

from . import search as search_mod
from .analysis import analyze, talking_points
from .people import LEAD, find_people, ok_name, rank_role
from .search import more_sources, news, search
from .startup import find_site, startup_profile
from . import utils
from .utils import domain, first_sentences, tokens
from .website import (guess_site, linkedin_info, norm_url, osm_info, parse_about, scrape_site)
from .wiki import wiki_find, wikidata


def build(name, hint="", prefer="india", website=None, linkedin=None, about="", startup=False):
    B = {"query": name, "matched": None, "overview": None, "facts": [], "news": [],
         "people": [], "contacts": [], "talking": [], "notes": [], "why": "",
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
    given = bool(website or linkedin)  # you pointed at a specific company: skip Wikipedia namesakes
    wp, alts = (None, []) if given else safe(lambda: wiki_find(name, hint, prefer), (None, []), "Wikipedia")
    if not hint and prefer == "india" and not given and (wp is None or wp["indian"]):
        hint = "India"  # bias later searches toward the Indian company
    B["more"] = []
    if wp:
        B["matched"], B["why"] = wp["title"], wp["why"]
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
    site = norm_url(website) or site or safe(lambda: guess_site(name, hint, prefer), None, "Website search")
    # Startup mode: on when ticked, or automatically when Wikipedia has no page for this company.
    use_startup = bool(startup) or wp is None
    guessed = False
    if not site and use_startup:
        site = safe(lambda: find_site(name, hint, prefer), None, "Startup website guess")
        guessed = bool(site)
    prof = {}
    if site:
        fact("Website", site + (" (provided by you)" if website else " (guessed from the name, verify)" if guessed else ""), site)
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
    B["_site"] = prof
    li = safe(lambda: linkedin_info(name, hint, norm_url(linkedin)), {}, "LinkedIn") or {}
    B["_li"] = li
    if about:
        ab = parse_about(about)
        lu = li.get("url")
        for label, k in (("Employees", "size"), ("Headquarters", "hq"), ("Industry", "industry"), ("Founded", "founded")):
            fact(label, ab[k], lu)
        if not B["overview"] and ab["desc"]:
            B["overview"] = (ab["desc"], lu)
    if li:
        fact("Employees", li.get("size"), li["url"])
        if linkedin:
            fact("LinkedIn", li["url"] + " (provided by you)", li["url"])
        fact("Headquarters", li.get("hq"), li["url"])
        fact("Industry", li.get("industry"), li["url"])
        B["contacts"].append(("Social", li["url"], li["url"]))
        if not B["overview"] and li.get("snippet"):
            B["overview"] = (first_sentences(li["snippet"], 2), li["url"])
    if not wp and not {f[0] for f in B["facts"]} & set(LOC):
        o = safe(lambda: osm_info(name, hint), {}, "OpenStreetMap")
        if o:
            fact("Address", o["address"] + " (OpenStreetMap, verify)", o["url"])
            if o.get("phone"):
                B["contacts"].append(("Phone", o["phone"], o["url"]))
    if not B["overview"]:
        # Only accept a snippet that actually names the company and comes from a normal site:
        # for small companies the first search hit is often an unrelated forum answer.
        NOISE = ("facebook.com", "instagram.com", "zhihu.com", "quora.com", "reddit.com", "baidu.com",
                 "tieba", "stackexchange.com", "stackoverflow.com", "youtube.com", "pinterest.com")
        for t, u, sn in search(f"{name} {hint} about company"):
            if sn and not any(d in domain(u) for d in NOISE) and tokens(name) <= tokens(t + " " + sn):
                B["overview"] = (first_sentences(sn, 2) + " (search snippet)", u)
                break
    q = f"{name} {hint}".strip()
    B["news"] = safe(lambda: news(q if hint else name), [], "News")
    have = [x for x in [f[2] for f in B["facts"]] + [n_[1] for n_ in B["news"]] + [c_[2] for c_ in B["contacts"]] if x]
    B["more"] = safe(lambda: more_sources(name, hint, have), [], "Extra sources")
    S = {}
    if use_startup:
        S = safe(lambda: startup_profile(name, hint, prefer, site), {}, "Startup sources")
        have_u = {m[1] for m in B["more"]}
        B["more"] = (B["more"] + [m for m in S.get("more", []) if m[1] not in have_u])[:10]
        for label, value, u in S.get("facts", []):
            fact(label, value, u)  # fills gaps only: website/LinkedIn facts were added first
        B["notes"].append(("Startup mode: little public data is normal for small companies, so startup "
                           "directories, startup media and company registries were searched as well. "
                           "Funding, stage and investors come from search-result text: verify them on the links.", None))
    for n_, role_ in prof.get("persons", ([],))[0]:
        if re.search(LEAD, role_) and ok_name(n_):
            person(n_, role_, site)
    before = len(B["people"])
    extra = [(t_, "", u_) for t_, u_, _, _ in B["news"]] + [(t_, sn_, u_) for t_, u_, sn_ in B["more"]] + S.get("extra", [])
    # Wikipedia/Wikidata lists few leaders for most companies, so search the web separately
    # when it gave fewer than 3 (with extra queries when it gave none).
    web_search = wiki_people < 3
    found_people = safe(lambda: find_people(name, hint, extra, search_web=web_search, deep=wiki_people == 0),
                        [], "Decision-maker search")
    for n_, role_, u_ in found_people:
        person(n_, role_, u_)
    B["people"] = sorted(B["people"], key=lambda p: rank_role(p[1]))[:8]
    if len(B["people"]) > before:
        B["notes"].append((("Wikipedia/Wikidata listed too few decision-makers, so more were searched separately on the web. " if web_search else "Some decision-makers came from headlines and search results. ") +
                           "These can be out of date: verify names and titles on their linked profiles.", None))
    wiki_fails = sorted({f"{h}: {r}" for h, r in utils.FAILS})
    if wiki_fails:
        B["notes"].append(("Wikipedia/Wikidata could not be reached (" + "; ".join(wiki_fails[:3]) +
                           "), so size, HQ and leaders may be missing. Wait a minute and search again.", None))
    elif not given and wp is None:
        B["notes"].append(("No matching Wikipedia page was found for this name.", None))
    elif wp and not any(f[0] in ("Employees", "Headquarters") for f in B["facts"]):
        B["notes"].append(("The matched Wikipedia/Wikidata entry has no size or headquarters data.", None))
    if wp is None or alts:
        for t, u in alts:
            B["notes"].append((f"Other pages with a similar name (not used): {t}", u))
    if not given:
        B["notes"].append(("Several companies can share a name: Indian and larger ones are ranked first. "
                           "If this is not the one, give --website / --linkedin, or use --hint / --prefer global.", None))
    if search_mod._ok[0] == 0:
        B["notes"].append(("Web search returned nothing: DuckDuckGo, Bing and Mojeek may be blocking "
                           "this network. Wait a few minutes or try another connection.", None))
    if not B["news"]:
        B["notes"].append(("No recent news retrieved (Google News RSS empty or blocked).", None))
    if not B["people"]:
        B["notes"].append(("No leaders are publicly listed on the sources searched. Look them up here:",
                           (li["url"].rstrip("/") + "/people/") if li.get("url") else "https://www.linkedin.com/search/results/people/?keywords=" + up.quote(q)))
    if not B["facts"] and not B["overview"]:
        B["notes"].append(("Little public information found. Try the legal name, or add --hint with the city or country.", None))
    B["analysis"] = analyze(B)
    B["talking"] = talking_points(B)
    return B
