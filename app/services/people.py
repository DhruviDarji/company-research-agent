"""Decision-maker extraction from search results and headlines."""
import re

from .search import search
from .utils import tokens

LEAD = (r"(?:CEO|Chief Executive(?: Officer)?|[Cc]o-?[Ff]ounder|[Ff]ounder|[Mm]anaging [Dd]irector|MD|"
        r"[Cc]hairman|[Cc]hairperson|Chair|[Pp]resident|Owner|Proprietor|[Dd]irector|CTO|CFO|COO|CMO|"
        r"Chief [A-Z][a-z]+ Officer|Head of [A-Z]\w+|Vice President|VP)")
STOP = {"chief", "executive", "officer", "founder", "cofounder", "co-founder", "ceo", "cto", "cfo", "coo",
        "director", "managing", "chairman", "president", "owner", "limited", "private", "pvt", "ltd", "inc",
        "group", "linkedin", "company", "india", "says", "said", "the", "and", "of", "at", "new", "board",
        "team", "profile", "view", "follow", "read", "more", "about", "news", "business", "services"}
PNAME = r"[A-Z][\w'’.-]+(?: [A-Z][\w'’.-]+){1,3}"


def ok_name(n):
    parts = n.split()
    if not 2 <= len(parts) <= 4:
        return False
    return not ({p.lower().strip(".,") for p in parts} & STOP) and all(re.match(r"^[A-Z][\w'’.-]*$", p) for p in parts)


def norm_role(r):
    r = re.sub(r"\s+", " ", r).strip(" ,.-")
    r = r[:1].upper() + r[1:]
    return {"MD": "Managing Director"}.get(r, r)


def people_from_text(title, snippet, url, name):
    """Pull (person, role, url) out of one search result or headline. Only if it names the company."""
    text = f"{title}. {snippet}"
    if not tokens(name) <= tokens(text):
        return []
    found, nm = [], re.escape(name)
    if "linkedin.com/in/" in url:  # "Priya Sharma - Founder & CEO - Acme | LinkedIn"
        parts = [x.strip() for x in re.split(r"\s+[-–|]\s+", title)]
        if len(parts) >= 2 and ok_name(parts[0]):
            m = re.search(LEAD, parts[1] + " " + snippet[:120])
            if m:
                role = parts[1] if re.search(LEAD, parts[1]) and len(parts[1]) < 60 else m.group(0)
                found.append((parts[0], norm_role(role), url))
    for m in re.finditer(rf"({PNAME}),? (?:is |was |the |as )*(?:the )?({LEAD})(?: and ({LEAD}))? (?:of|at) (?:the )?(?i:{nm})", text):
        found.append((m.group(1), norm_role(m.group(2)), url))
    for m in re.finditer(rf"(?i:{nm})(?:'s|’s)? ({LEAD}) ({PNAME})", text):
        found.append((m.group(2), norm_role(m.group(1)), url))
    for m in re.finditer(r"[Dd]irectors?\b[^.:]{0,80}?(?: are| include|:)\s+(" + PNAME + r"(?:(?:,| and|,? &) " + PNAME + r"){0,4})", text):
        for p in re.split(r",| and | & ", m.group(1)):
            found.append((p.strip(), "Director (registry listing)", url))
    for m in re.finditer(r"(?:[Ff]ounded|[Cc]o-?founded|[Ss]tarted|[Ee]stablished) by (" + PNAME + r"(?:(?:,| and|,? &) " + PNAME + r"){0,3})", text):
        for p_ in re.split(r",| and | & ", m.group(1)):
            found.append((p_.strip(), "Founder", url))
    found = [(n.strip(" .,"), r, u) for n, r, u in found]
    return [f for f in found if ok_name(f[0])]


def rank_role(role):
    r = role.lower()
    if re.search(r"ceo|chief executive|founder|managing director|owner|proprietor|chair|president", r):
        return 0
    if re.search(r"chief|cto|cfo|coo|cmo|partner|principal", r):
        return 1
    return 2


def find_people(name, hint, extra=(), search_web=True, deep=False):
    """Decision-makers from separate web searches (used when Wikipedia/Wikidata list too few).
    deep=True adds extra queries (board, founders, company registries) for when nothing was listed.
    Headlines/snippets already collected (extra) are always read; they cost no extra searches."""
    out = []
    if search_web:
        queries = [f'"{name}" CEO OR founder OR "managing director" {hint}',
                   f"{name} {hint} leadership team management",
                   f"site:linkedin.com/in {name} {hint} founder OR CEO OR director"]
        if deep:
            queries += [f"who is the CEO of {name} {hint}",
                        f'"{name}" "board of directors" OR "key people" {hint}',
                        f"{name} {hint} founded by",
                        f"{name} {hint} directors zaubacorp OR tofler OR opencorporates"]
        for q in queries:
            for t, u, sn in search(q, 8):
                out += people_from_text(t, sn, u, name)
    for t, sn, u in extra:
        out += people_from_text(t, sn, u, name)
    return out
