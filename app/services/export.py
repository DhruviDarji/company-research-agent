"""Exports: plain text, PDF (reportlab) and Excel sheet (openpyxl)."""
import os
from xml.sax.saxutils import escape as esc

from .utils import domain


def to_text(B):
    L = [f"=== {B['query'].upper()} BRIEF ({B['generated']}) ==="]
    if not B["matched"]:
        L.append("(No Wikipedia page: built from the company website, web search and other free sources.)")
    else:
        L.append(f"Matched entity: {B['matched']} ({B['why']})  <- verify this is the right company")
    if B["overview"]:
        L += ["", "WHAT THEY DO", f"{B['overview'][0]}\n  src: {B['overview'][1]}"]
    L += ["", "KEY FACTS"] + [f"- {a}: {b}\n  src: {c}" for a, b, c in B["facts"]]
    L += ["", "RECENT NEWS"] + [f"- {t} ({d}, {s})\n  src: {u}" for t, u, d, s in B["news"]]
    L += ["", "DECISION-MAKERS"] + [f"- {a}, {b}\n  src: {c}" for a, b, c in B["people"]]
    L += ["", "CONTACTS"] + [f"- {a}: {b}\n  src: {c}" for a, b, c in B["contacts"]]
    A = B["analysis"]
    L += ["", "ANALYSIS", A["summary"]] + [f"- {a}: {b}" + (f"\n  src: {c}" if c else "") for a, b, c in A["profile"]]
    L += [f"- {k}: {t}" + (f"\n  src: {u}" if u else "") for k, t, u in A["signals"]]
    L += ["", "MORE SOURCES"] + [f"- {t}: {sn}\n  src: {u}" for t, u, sn in B["more"]]
    L += [f"NOTE: {t}" + (f"\n  link: {u}" if u else "") for t, u in B["notes"]]
    L += ["", "TALKING POINTS"] + [f"{i}. {t}\n  src: {u or 'n/a'}"
                                   for i, (t, u) in enumerate(B["talking"], 1)]
    return "\n".join(L)


def to_pdf(B, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=8, leading=10)
    h = ParagraphStyle("h", parent=ss["Heading2"], fontSize=10, spaceBefore=6,
                       spaceAfter=2, textColor=colors.HexColor("#1F3A5F"))
    src = lambda u: (f' <link href="{esc(u)}" color="#1a56db">[{esc(domain(u))}]</link>'
                     if u else " [general / your input]")
    P = lambda t: Paragraph(t, body)
    S = [Paragraph(f"{esc(B['matched'] or B['query'])}: Company Brief",
                   ParagraphStyle("t", parent=ss["Title"], fontSize=15, spaceAfter=2)),
         P(f"Generated {B['generated']} from public web sources. Verify before relying on it.")]
    if B["overview"]:
        S += [Paragraph("What they do", h), P(esc(B["overview"][0]) + src(B["overview"][1]))]
    S.append(Paragraph("Size, locations and facts", h))
    S += [P(f"<b>{esc(a)}:</b> {esc(b)}{src(c)}") for a, b, c in B["facts"]]
    S.append(Paragraph("Recent news", h))
    S += [P(f"{esc(t)} ({esc(d)}){src(u)}") for t, u, d, s in B["news"]]
    S.append(Paragraph("Decision-makers and contacts", h))
    S += [P(f"<b>{esc(a)}</b>, {esc(b)}{src(c)}") for a, b, c in B["people"][:6]]
    S += [P(f"<b>{esc(a)}:</b> {esc(b)}{src(c)}") for a, b, c in B["contacts"]]
    if B["more"]:
        S.append(Paragraph("More sources", h))
        S += [P(f"{esc(t[:70])}{src(u)}") for t, u, sn in B["more"][:5]]
    S += [P(f"<i>{esc(t)}</i>" + (src(u) if u else "")) for t, u in B["notes"]]
    A = B["analysis"]
    S += [Paragraph("Analysis", h), P(esc(A["summary"]))]
    S += [P(f"<b>{esc(a)}:</b> {esc(b)}{src(c) if c else ''}") for a, b, c in A["profile"]]
    S += [P(f"<b>{esc(k)}:</b> {esc(t)}{src(u) if u else ''}") for k, t, u in A["signals"][:6]]
    S.append(Paragraph("Talking points for a first meeting", h))
    S += [P(f"{i}. {esc(t)}{src(u)}") for i, (t, u) in enumerate(B["talking"], 1)]
    SimpleDocTemplate(path, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                      topMargin=1.2 * cm, bottomMargin=1.2 * cm).build(S)


def to_xlsx(B, path):
    from openpyxl import Workbook, load_workbook
    if isinstance(path, str) and os.path.exists(path):
        wb = load_workbook(path)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Briefs"
        ws.append(["Date", "Company", "Section", "Item", "Value", "Source"])
        for c, w in zip("ABCDEF", (12, 22, 16, 22, 70, 50)):
            ws.column_dimensions[c].width = w
    d, c = B["generated"], B["matched"] or B["query"]
    rows = []
    if B["overview"]:
        rows.append(("Overview", "Summary", *B["overview"]))
    rows += [("Fact", a, b, u) for a, b, u in B["facts"]]
    rows += [("News", f"{dd} {s}", t, u) for t, u, dd, s in B["news"]]
    rows += [("Person", b, a, u) for a, b, u in B["people"]]
    rows += [("Contact", a, b, u) for a, b, u in B["contacts"]]
    rows += [("More source", domain(u), t, u) for t, u, sn in B["more"]]
    rows += [("Analysis", a, b, u or "") for a, b, u in B["analysis"]["profile"]]
    rows += [("Analysis", k, t, u or "") for k, t, u in B["analysis"]["signals"]]
    rows += [("Note", "", t, u or "") for t, u in B["notes"]]
    rows += [("Talking point", str(i), t, u or "") for i, (t, u) in enumerate(B["talking"], 1)]
    for r in rows:
        ws.append([d, c, *r])
    wb.save(path)
