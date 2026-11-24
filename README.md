# Company Research Agent

Enter any company name and get a one-page, fully sourced brief:

1. **What the company does**, its size, locations and recent news
2. **Publicly listed decision-makers** and contact details
3. **Three suggested talking points** for a first meeting
4. **A source link for every fact**
5. **Bonus:** export the brief as a **PDF** or **Excel sheet**

Uses only free public sources and needs **no API keys**: Wikipedia and Wikidata, web search
(DuckDuckGo, Bing, Mojeek), the company's own website (schema.org data, contact and team pages),
LinkedIn search snippets (LinkedIn itself is never scraped), OpenStreetMap and Google News RSS.
Analysis and talking points are rule-based, so there is no model cost.

## Project structure

```
company-research-agent/
├── app/
│   ├── __init__.py              create_app() factory
│   ├── config.py                settings from environment variables
│   ├── routes/
│   │   ├── pages.py             GET /  -> renders templates/index.html
│   │   └── api.py               /api/health, /api/brief, /api/pdf, /api/xlsx
│   ├── services/                the research engine
│   │   ├── brief.py             assembles the brief from all sources
│   │   ├── wiki.py              Wikipedia + Wikidata
│   │   ├── search.py            web search, news RSS, extra sources
│   │   ├── website.py           site scraping, LinkedIn snippet, OpenStreetMap
│   │   ├── people.py            decision-maker extraction
│   │   ├── analysis.py          analysis + three talking points
│   │   ├── export.py            text / PDF / Excel export
│   │   ├── service.py           15-minute cache
│   │   └── utils.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/styles.css
│       └── js/app.js
├── run.py                       entry point
├── cli.py                       command-line version
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000** in your browser, type a company name and click Research.
A lookup takes about 10 to 40 seconds.

## Command line

```bash
python cli.py "Stripe" --pdf --xlsx
python cli.py "Joe's Plumbing" --hint "Leeds UK"
```

`--xlsx` appends each brief to `company_briefs.xlsx`, so the file works as a running research sheet.

## API

| Endpoint | Description |
|---|---|
| `GET /api/health` | health check |
| `GET /api/brief?q=Stripe` | brief as JSON |
| `GET /api/pdf?q=Stripe` | PDF download |
| `GET /api/xlsx?q=Stripe` | Excel download |

Optional query parameters: `hint` (city or country), `prefer` (`india`, `global`, `any`),
`website`, `linkedin`, `about` (text pasted from LinkedIn's About section).

## Deploying

Any Python host works (Render, Railway, Fly.io). From the project root:

```bash
gunicorn run:app --bind 0.0.0.0:$PORT --timeout 120
```

The page and the API are served from the same address, so no extra configuration is needed.

## Notes and limits

- Several companies can share a name. Indian and larger companies are ranked first by default;
  use the website, LinkedIn or location fields to pin the right one.
- Facts from search snippets and headlines can be out of date. Check them on the linked source.
- Search engines may rate-limit or block some networks. The brief then shows a note instead of failing.
- Only publicly listed information is collected. Respect each site's terms and local privacy law
  when you contact people.
