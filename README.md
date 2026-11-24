# Company Research Agent

<<<<<<< HEAD
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
=======
A lightweight Python agent that gathers a comprehensive brief about a company from multiple public sources (Wikipedia, Wikidata, company website, LinkedIn, news, etc.). It aggregates facts, key people, contact information, recent news, and talking points into a structured JSON payload.

---

## ✨ Features
- **Multi‑source data aggregation** – Wikipedia/Wikidata, company website scraping, LinkedIn snippets, OpenStreetMap, and news feeds.
- **Robust error handling** – Each source runs in isolation; failures are logged but do not abort the whole build.
- **Talk‑point generation** – Summarizes findings into ready‑to‑use discussion points.
- **Configurable hints** – Provide a hint (city, product, etc.) to disambiguate similar company names.
- **Deployable on Render** – Includes a `render.yaml` for one‑click deployments.

---

## 📦 Installation
```bash
# Clone the repository (already done) and cd into it
cd "c:/Users/Dhruvi/Downloads/company-research-agent (3)/company-research-agent"

# Create a virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\activate  # on Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

The project requires Python 3.9+.

---

## 🚀 Quick Start
```bash
# Run the built‑in CLI (see `cli.py` for arguments)
python cli.py "<company name>" [--hint "optional hint"]
```

Example:
```bash
python cli.py "Acme Corp" --hint "New York"
```
The command prints a JSON object containing the assembled brief.

---

## 🛠️ API Usage
You can also import the service directly in your own Python code:
```python
from app.services.brief import build

brief = build("Acme Corp", hint="New York")
print(brief)
```
The returned dictionary has the following top‑level keys:
- `query` – the original search query.
- `matched` – the Wikipedia title that matched (if any).
- `overview` – a short description and source URL.
- `facts` – list of `(label, value, url)` tuples.
- `people` – list of `(name, role, url)`.
- `contacts` – list of `(type, value, source_url)`.
- `news` – recent news items.
- `talking` – ready‑to‑use talking points.
- `notes` – any warnings or extra information.

---

## ⚙️ Configuration
The app reads the following environment variables (defaults are shown):
| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Interface to bind the Flask app (used by Render). |
| `PORT` | `8000` | Port for the Flask server. |
| `DEBUG` | `False` | Enable Flask debug mode. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. |

You can set them in a `.env` file or directly in the Render dashboard under **Environment Variables**.

---

## 🌐 Deploy to Render
A `render.yaml` file is already included. To deploy:
1. Sign in to <https://render.com>.
2. Click **New → Web Service**.
3. Connect the GitHub repo `DhruviDarji/company-research-agent`.
4. The form will be mostly auto‑filled from `render.yaml` (see the screenshot you uploaded). Choose a name, region, and keep the **Free** plan if you just want to test.
5. Click **Create Web Service** – Render will run `pip install -r requirements.txt` and start the app with `python run.py`.

The service will be reachable at `https://<your‑service‑name>.onrender.com`.

---

## 🧪 Running Tests
If you add tests later, you can run them with:
```bash
pytest
```
(There are currently no test files shipped with the project.)

---

## 🤝 Contributing
Contributions are welcome! Feel free to open an issue or a pull request.
1. Fork the repo.
2. Create a new branch (`git checkout -b my‑feature`).
3. Make your changes, add tests, and ensure they pass.
4. Submit a pull request.

---

## 📄 License
This project is licensed under the MIT License – see the `LICENSE` file for details.

---

## 🙋‍♀️ Author
Created by **Dhruvi Darji**. Feel free to reach out via the GitHub repository's Discussions or Issues.
>>>>>>> cca472d4b1c5a06c875bb010895590d5edf2269a
