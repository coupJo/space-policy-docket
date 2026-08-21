# Space Policy Docket

A free, independent tracker of U.S. space policy — bills in Congress, agency rulemaking, and who regulates what in orbit. Built with plain HTML/CSS/JavaScript, hosted on GitHub Pages, and it updates itself every morning.

**Live site:** https://coupjo.github.io/space-policy-docket/

**Status:** Docket tab live with real Congress.gov bills and Federal Register rulemaking, a "This Week in Space Policy" digest, and a Money Map of NASA award spending. All refreshed daily.

## What's in each file

```
space-policy-docket/
├── index.html              The whole site: masthead, 4 tabs, and all written content
├── css/
│   └── style.css           All styling (colors, fonts, tables, cards, badges)
├── js/
│   └── app.js              All behavior: tabs, data loading, search/sort/filter, digest
├── data/                   Auto-generated — don't hand-edit these
│   ├── bills.json          Space bills in the current Congress
│   ├── rules.json          Final & proposed rules from FAA, FCC, NOAA, NASA
│   ├── money.json          NASA award totals by recipient & congressional district
│   └── digest.json         The trailing-7-day summary shown at the top
├── scripts/
│   ├── fetch_bills.py      Scans every bill of the Congress via the Congress.gov API
│   ├── fetch_rules.py      Pulls space rulemaking from the Federal Register API
│   ├── fetch_money.py      Pulls FY award data from the USAspending.gov API
│   └── build_digest.py     Summarizes the last 7 days from the bills & rules files
└── .github/workflows/
    └── update-data.yml     Runs all three scripts every morning and commits the result
```

The key idea: the `data/` files are the only things that change day to day. The site just displays whatever is in them, and the Python scripts rewrite them daily — no changes to the site needed.

## How the daily update works

Every morning at 6am Pacific, GitHub Actions (GitHub's free robot) checks out this repo, runs the scripts in order — bills, rules, awards, digest — and commits whatever changed. GitHub Pages then redeploys the site automatically. It also re-runs whenever a script is edited, and can be triggered by hand: **Actions tab → Update bill data → Run workflow**.

The Congress.gov API key lives in a repository secret named `CONGRESS_API_KEY` (Settings → Secrets and variables → Actions) — it never appears in the code. The Federal Register API needs no key.

## Viewing the site on your computer

Browsers block `fetch()` when you double-click an HTML file. Run a tiny local server from inside this folder instead:

```
python3 -m http.server 8000
```

Then open http://localhost:8000. (The live GitHub Pages site has no such issue.)

## Editing content

- **Who Regulates Space? tab** — the agency cards are plain text in `index.html` (search for `agency-card`). Edit them directly.
- **Which bills/rules count as "space"** — tune the `WORDS`, `PHRASES`, `EXCLUDE_PHRASES`, and `TOPIC_RULES` lists at the top of the fetch scripts.
- **Your name** — add it to the footer in `index.html` when you're ready to put this on your resume.

## Roadmap

- **Phase 1 (done):** site shell + live bills table + Who Regulates v1
- **Phase 2 (done):** Federal Register rulemaking + weekly digest
- **Phase 3 (done):** Money Map — NASA awards by company and congressional district (USAspending.gov)
- **Phase 4:** National Space Law Comparator (UNOOSA sources)
