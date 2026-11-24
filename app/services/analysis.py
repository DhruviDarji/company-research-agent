"""Rule-based analysis and talking points (no AI model, no cost)."""
import datetime as dt
import re

from .utils import domain

SECTORS = {
    "software / SaaS": r"\b(saas|software|platform|cloud|api|app|ai)\b",
    "e-commerce / D2C": r"\b(e-?commerce|d2c|online store|shop|retail|brand)\b",
    "fintech": r"\b(fintech|payments?|lending|insurance|banking|upi|neobank|loans?)\b",
    "healthcare": r"\b(health|clinic|pharma|medical|hospital|wellness|diagnostics)\b",
    "education": r"\b(edtech|education|learning|courses|school|university)\b",
    "consumer electronics": r"\b(electronics|audio|earphones|headphones|wearables|smartwatch)\b",
    "manufacturing": r"\b(manufactur\w*|industrial|machinery|factory|steel|chemicals?|automotive)\b",
    "logistics / mobility": r"\b(logistics|supply chain|delivery|shipping|mobility|fleet)\b",
    "media / marketing": r"\b(media|advertising|marketing|agency|publishing)\b",
    "food and beverage": r"\b(food|restaurant|beverage|snacks?|cafe|dairy)\b",
    "IT services / consulting": r"\b(consulting|it services|outsourcing|digital transformation|solutions)\b",
    "home / field services": r"\b(plumb\w*|electrician|repairs?|hvac|cleaning|maintenance|installation)\b",
    "real estate / construction": r"\b(real estate|construction|housing|developers?|infrastructure)\b"}
THEMES = {
    "funding": r"\b(raises?|raised|funding|series [a-e]|seed round|valuation|ipo|investment)\b",
    "product launch": r"\b(launch\w*|unveil\w*|introduc\w*|new product|rolls? out)\b",
    "expansion": r"\b(expan\w*|opens?|new (plant|office|store|facility)|enters?)\b",
    "partnership / M&A": r"\b(partner\w*|acquir\w*|acquisition|merger|tie-?up|collaborat\w*)\b",
    "leadership change": r"\b(appoint\w*|names? new|steps? down|resigns?|joins as)\b",
    "recognition": r"\b(award\w*|wins?|ranked|recogni\w*)\b",
    "challenges": r"\b(layoffs?|lawsuit|probe|fraud|penalty|loss(es)?|decline|recall|shuts?|fined?|raid)\b"}


def analyze(B):
    """Rule-based analysis of the collected public data (no AI model, no cost)."""
    facts = {f[0]: f for f in B["facts"]}
    site = B.get("_site", {})
    g = lambda k: site[k][0] if k in site else None
    blob = " ".join([(B["overview"] or ("",))[0], g("meta") or "", " ".join(g("headings") or []),
                     (g("text") or "")[:1500], (B.get("_li") or {}).get("snippet", ""),
                     facts.get("Industry", ("", ""))[1]]).lower()
    out = {"profile": [], "signals": [], "summary": ""}
    # size class
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", facts["Employees"][1])] if "Employees" in facts else []
    n = max(nums) if nums else None
    size = ("unknown size" if n is None else "micro business (1-10)" if n <= 10 else "small company / startup (11-50)"
            if n <= 50 else "SME (51-250)" if n <= 250 else "mid-size company (251-1,000)" if n <= 1000
            else "large company (1,000+)")
    out["profile"].append(("Size class", size, facts["Employees"][2] if "Employees" in facts else None))
    # sector
    score = {k: len(re.findall(p, blob)) for k, p in SECTORS.items()}
    top = [k for k, v in sorted(score.items(), key=lambda kv: -kv[1]) if v >= 2][:2]
    src0 = (B["overview"] or (0, None))[1]
    out["profile"].append(("Sector (inferred)", ", ".join(top) or "unclear from public text", src0))
    # age
    yr = int(facts["Founded"][1][:4]) if "Founded" in facts and facts["Founded"][1][:4].isdigit() else None
    if yr:
        age = dt.date.today().year - yr
        out["profile"].append(("Age", f"{age} years (founded {yr})" + (" - early stage" if age <= 3 else " - established" if age >= 10 else ""), facts["Founded"][2]))
    # news themes
    themes = {}
    for t, u, d, s_ in B["news"]:
        for k, p in THEMES.items():
            if re.search(p, t, re.I):
                themes.setdefault(k, []).append((t, u))
    pos = sum(len(v) for k, v in themes.items() if k != "challenges")
    neg = len(themes.get("challenges", []))
    mood = "no recent coverage found" if not B["news"] else "mostly positive" if pos > neg else "mixed or cautious" if neg else "neutral"
    out["profile"].append(("News tone", mood, B["news"][0][1] if B["news"] else None))
    sg = out["signals"]
    for k, v in themes.items():
        kind = "Watch-out" if k == "challenges" else "Strength" if k in ("funding", "recognition", "expansion") else "Opportunity"
        sg.append((kind, f"News mentions {k}: \"{v[0][0][:80]}\"", v[0][1]))
    # website signals
    sig, sig_u = site.get("signals", ([], None))
    if any(k in sig for k in ("careers", "jobs")):
        sg.append(("Opportunity", "Has a careers/jobs page, so the team is likely hiring and growing.", sig_u))
    if "pricing" in sig:
        sg.append(("Strength", "Public pricing page: a defined product with a self-serve or sales-led model.", sig_u))
    if "investors" in sig:
        sg.append(("Strength", "Has an investors section: likely funded or listed.", sig_u))
    if any(k in sig for k in ("partners", "customers", "case-stud")):
        sg.append(("Strength", "Publishes customers/partners/case studies: shows traction.", sig_u))
    if n and n > 1000:
        sg.append(("Strength", f"Large organisation (~{n:,} staff): established, but decisions may involve several teams.", out["profile"][0][2]))
    if yr and dt.date.today().year - yr >= 10:
        sg.append(("Strength", f"Operating for {dt.date.today().year - yr}+ years.", facts["Founded"][2]))
    # watch-outs
    if not B["people"]:
        sg.append(("Watch-out", "No leaders are publicly listed: you will need to find the right contact.", None))
    if not B["news"]:
        sg.append(("Watch-out", "No recent news found: little visible momentum, or very low media profile.", None))
    if yr and dt.date.today().year - yr <= 2:
        sg.append(("Watch-out", "Very young company: priorities and budget may change quickly.", facts["Founded"][2]))
    # confidence
    doms = {domain(u) for u in [f[2] for f in B["facts"]] + [n_[1] for n_ in B["news"]] + [m[1] for m in B["more"]] if u}
    keys = sum(bool(x) for x in (B["overview"], "Employees" in facts, ("Headquarters" in facts or "Address" in facts), B["people"], B["contacts"]))
    pts = min(len(doms), 6) + keys
    out["profile"].append(("Data confidence", ("High" if pts >= 9 else "Medium" if pts >= 5 else "Low") +
                           f" ({len(doms)} source sites, {keys}/5 key fields)", None))
    loc = (facts.get("Headquarters") or facts.get("Address") or (0, ""))[1].replace(" (OpenStreetMap, verify)", "")
    nm = B["matched"] or B["query"]
    mom = ("Recent coverage is about " + ", ".join(list(themes)[:3]) + ".") if themes else ""
    out["summary"] = (f"{nm} appears to be a {size}" + (f" in {' / '.join(top)}" if top else "") +
                      (f", based in {loc[:60]}" if loc else "") + ". " + mom +
                      " This is an automatic reading of public data: confirm key points before relying on them.")
    out["themes"], out["size"], out["sector"] = themes, size, top
    return out


def talking_points(B):
    """Three company-specific openers built from the analysis (rule-based, no AI model)."""
    A, n, tp = B["analysis"], B["matched"] or B["query"], []
    th = A["themes"]
    if "funding" in th:
        t, u = th["funding"][0]
        tp.append((f"Funding news (\"{t[:80]}\"): ask how they plan to deploy the capital and which "
                   f"capability gaps they must close first.", u))
    elif "product launch" in th:
        t, u = th["product launch"][0]
        tp.append((f"Launch news (\"{t[:80]}\"): ask how adoption is going and what is slowing it down.", u))
    elif "expansion" in th or "partnership / M&A" in th:
        k = "expansion" if "expansion" in th else "partnership / M&A"
        t, u = th[k][0]
        tp.append((f"{k.capitalize()} news (\"{t[:80]}\"): ask what this changes for operations and suppliers.", u))
    elif B["news"]:
        tp.append((f"Open with the recent headline (\"{B['news'][0][0][:80]}\") and ask how it affects "
                   f"their priorities this year.", B["news"][0][1]))
    size = A["size"]
    su = A["profile"][0][2]
    if size.startswith(("micro", "small")):
        tp.append((f"{n} is a {size}: likely founder-led. Ask what one bottleneck, whether sales, hiring "
                   f"or operations, would unlock their next stage if removed.", su))
    elif size.startswith(("SME", "mid")):
        tp.append((f"{n} is a {size}: ask which processes no longer scale as they grow and which tools "
                   f"or partners they have outgrown.", su))
    elif size.startswith("large"):
        tp.append((f"{n} is a {size}: ask which business unit owns this topic, and how a pilot would be "
                   f"approved and measured.", su))
    heads = (B.get("_site") or {}).get("headings")
    if heads and heads[0]:
        tp.append((f"Their site leads with \"{heads[0][0][:70]}\": ask which customer segment responds best "
                   f"to that message and where it falls short.", heads[1]))
    if B["people"] and len(tp) < 3:
        p = B["people"][0]
        tp.append((f"Ask {p[0]} ({p[1]}) what success looks like this year and which goals are blocked today.", p[2]))
    if B["overview"] and len(tp) < 3:
        tp.append((f"Confirm what {n} sells and to whom, then ask which customer segment is growing fastest.", B["overview"][1]))
    generic = ["Ask how they currently evaluate and onboard new vendors or partners.",
               "Ask what their top priority is for the next quarter and what could get in its way.",
               "Ask who else should be in the conversation and what the decision process looks like."]
    for g in generic:
        if len(tp) < 3:
            tp.append((g + " (general, not sourced)", None))
    return tp[:3]
