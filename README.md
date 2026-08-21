# Space Policy Docket

A free, independent tracker of U.S. space policy — bills in Congress, agency rulemaking, and who regulates what in orbit. Built with plain HTML/CSS/JavaScript, hosted on GitHub Pages, designed to update itself daily.

**Status:** Phase 1 — site shell + Docket tab with sample data. Live Congress.gov data arrives in Phase 2.

## What's in each file

```
space-policy-docket/
├── index.html        The whole site: masthead, 4 tabs, and all written content
├── css/
│   └── style.css     All styling (colors, fonts, table, cards)
├── js/
│   └── app.js        All behavior: tab switching, loading data, search/sort/filter
├── data/
│   └── bills.json    The bill data the Docket table displays (sample for now)
└── README.md         This file
```

The key idea: `data/bills.json` is the only thing that changes day to day. The site just displays whatever is in that file. In Phase 2, a Python script will rewrite it daily from the Congress.gov API — no changes to the site needed.

## Viewing the site on your computer

Browsers block `fetch()` when you double-click an HTML file, so the table won't load that way. Instead, run a tiny local server from inside this folder:

```
python3 -m http.server 8000
```

Then open http://localhost:8000 in your browser. (On the live GitHub Pages site this isn't an issue.)

## Editing content

- **Who Regulates Space? tab** — the agency cards are plain text in `index.html` (search for `agency-card`). Edit them directly.
- **Sample bills** — edit `data/bills.json`. Each bill needs: `bill`, `congress`, `title`, `sponsor`, `latest_action`, `action_date` (YYYY-MM-DD), `topics` (a list), `url`.
- **Your name** — add it to the footer in `index.html` when you're ready to put this on your resume.

## Roadmap

- **Phase 1 (now):** shell + Docket table (sample data) + Who Regulates v1
- **Phase 2:** `scripts/fetch_bills.py` pulls real bills from the Congress.gov API; GitHub Actions runs it daily; Federal Register rules + weekly digest
- **Phase 3:** Money Map — space contracts by company and congressional district (USAspending.gov)
- **Phase 4:** National Space Law Comparator (UNOOSA sources)

## Before Phase 2

Get a free Congress.gov API key at https://api.congress.gov/sign-up/ — takes two minutes, arrives by email.
