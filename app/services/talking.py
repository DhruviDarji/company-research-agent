"""Three first-meeting talking points (rule-based, no AI model, no cost)."""


def talking_points(B):
    """Rule-based (no LLM): turns the facts above into three conversation openers."""
    n, tp = B["matched"] or B["query"], []
    if B["news"]:
        t, u = B["news"][0][0], B["news"][0][1]
        tp.append((f"Open with the recent news (\"{t}\"). Ask how it changes priorities "
                   f"for the next 6-12 months.", u))
    facts = {f[0]: f for f in B["facts"]}
    keys = [k for k in ("Employees", "Headquarters", "Address") if k in facts][:2]
    if keys:
        desc = ", ".join((facts[k][1] + " employees") if k == "Employees" else "based at " + facts[k][1].replace(" (OpenStreetMap, verify)", "") for k in keys)
        tp.append((f"{n} has {desc}. Ask what is hardest to coordinate "
                   f"or grow right now, and where you could help.", facts[keys[0]][2]))
    if B["people"]:
        p = B["people"][0]
        tp.append((f"Ask {p[0]} ({p[1]}) what success looks like this year and which "
                   f"goals are blocked today.", p[2]))
    if B["overview"] and len(tp) < 3:
        tp.append((f"Confirm what {n} sells and to whom, then ask which customer "
                   f"segment is growing fastest.", B["overview"][1]))
    generic = ["Ask how they currently evaluate and onboard new vendors or partners.",
               "Ask what their top priority is for the next quarter and what could get in its way.",
               "Ask who else should be in the conversation and what the decision process looks like."]
    for g in generic:
        if len(tp) < 3:
            tp.append((g + " (general, not sourced)", None))
    return tp[:3]

