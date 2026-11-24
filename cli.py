#!/usr/bin/env python3
"""Command-line use:  python cli.py "Stripe" --pdf --xlsx"""
import argparse
import os
import re
import sys

from app.services import build, to_pdf, to_text, to_xlsx


def main():
    ap = argparse.ArgumentParser(description="One-page company research brief")
    ap.add_argument("company", nargs="?")
    ap.add_argument("--hint", default="", help="city/country to disambiguate, e.g. 'Leeds UK'")
    ap.add_argument("--prefer", choices=["india", "global", "any"], default="india",
                    help="which same-named company to favour (default india)")
    ap.add_argument("--website", help="official website, if you know it (skips guessing)")
    ap.add_argument("--linkedin", help="company LinkedIn URL, e.g. linkedin.com/company/boat-lifestyle")
    ap.add_argument("--about", default="", help="text pasted from the LinkedIn About section")
    ap.add_argument("--pdf", action="store_true", help="export PDF")
    ap.add_argument("--xlsx", action="store_true", help="append to company_briefs.xlsx")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    name = a.company or input("Company name: ").strip()
    if not name:
        sys.exit("No company given.")
    B = build(name, a.hint, a.prefer, a.website, a.linkedin, a.about)
    print(to_text(B))
    os.makedirs(a.out, exist_ok=True)
    slug = re.sub(r"\W+", "_", name.lower()).strip("_")
    if a.pdf:
        to_pdf(B, p := os.path.join(a.out, f"{slug}_brief.pdf"))
        print("\nSaved", p)
    if a.xlsx:
        to_xlsx(B, p := os.path.join(a.out, "company_briefs.xlsx"))
        print("Saved", p)


if __name__ == "__main__":
    main()
