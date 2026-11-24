"""Web search (DuckDuckGo -> Bing -> Mojeek, no API key), Google News RSS, extra sources."""
import time
import urllib.parse as up
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from .utils import domain, first_sentences, get, tokens


def news(name, n=4):
    r = get("https://news.google.com/rss/search",
            params={"q": f'"{name}"', "hl": "en-US", "gl": "US", "ceid": "US:en"})
    if not r:
        return []
    try:
        items = list(ET.fromstring(r.content).iter("item"))[:n]
    except ET.ParseError:
        return []
    out = []
    for it in items:
        title = (it.findtext("title") or "").rsplit(" - ", 1)[0]
        out.append((title, it.findtext("link") or "", (it.findtext("pubDate") or "")[:16],
                    it.findtext("source") or ""))
    return out



_ok = [0]

_last = [0.0]


def search(query, n=6):
    """Web search without an API key: DuckDuckGo HTML, falling back to Bing HTML."""
    wait = 0.6 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)  # short pause between searches so search engines do not block us
    _last[0] = time.time()
    out = []
    r = get("https://html.duckduckgo.com/html/", params={"q": query})
    if r:
        for res in BeautifulSoup(r.text, "html.parser").select("div.result")[:n]:
            a = res.select_one("a.result__a")
            if not a:
                continue
            sn = res.select_one(".result__snippet")
            href = a.get("href", "")
            url = up.parse_qs(up.urlparse(href).query).get("uddg", [href])[0]
            out.append((a.get_text(strip=True), url, sn.get_text(" ", strip=True) if sn else ""))
    if not out:
        r = get("https://www.bing.com/search", params={"q": query})
        if r:
            for li in BeautifulSoup(r.text, "html.parser").select("li.b_algo")[:n]:
                a, p = li.select_one("h2 a"), li.select_one(".b_caption p")
                if a:
                    out.append((a.get_text(strip=True), a.get("href", ""), p.get_text(" ", strip=True) if p else ""))
    if not out:
        r = get("https://www.mojeek.com/search", params={"q": query})
        if r:
            for li in BeautifulSoup(r.text, "html.parser").select("ul.results-standard li")[:n]:
                a, p = li.select_one("a.title"), li.select_one("p.s")
                if a:
                    out.append((a.get_text(strip=True), a.get("href", ""), p.get_text(" ", strip=True) if p else ""))
    _ok[0] += len(out)
    return out


def more_sources(name, hint, have):
    """Extra public pages about the company: registries (India: Zauba/Tofler), profiles, articles."""
    out, seen = [], {domain(u) for u in have}
    qs = (f"{name} {hint} company profile directors zaubacorp OR tofler OR opencorporates OR crunchbase",
          f"{name} {hint} company about")
    for q in qs:
        for t, u, sn in search(q, 8):
            blob = tokens(t + " " + u + " " + sn)
            if u.startswith("http") and domain(u) not in seen and tokens(name) <= blob:
                seen.add(domain(u))
                out.append((t[:90], u, first_sentences(sn, 2)))
    return out[:6]

