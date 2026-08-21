"""
fetch_rules.py — refresh data/rules.json from the Federal Register API (free, no key).

What it does, in plain terms:
  1. Ask the Federal Register for final rules and proposed rules published by
     the four space-relevant agencies (FAA, FCC, NOAA, NASA) since Jan 2025,
     running one search per keyword because the API takes one term at a time.
  2. Deduplicate (the same rule matches several keywords), then keep only
     titles that pass the same space filter the bill script uses.
  3. Tag topics, note open comment deadlines, write data/rules.json.

Routine meeting/paperwork NOTICEs are excluded on purpose — this table is for
rulemaking. To include notices, add "NOTICE" to DOC_TYPES below.

Run locally:  python3 scripts/fetch_rules.py   (no API key needed)
In production, GitHub Actions runs this daily alongside fetch_bills.py.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------- Settings ----------------

API_URL = "https://www.federalregister.gov/api/v1/documents.json"
SINCE = "2025-01-01"          # start of the 119th Congress, matches the bills tab
PER_PAGE = 100
SAFETY_MAX_PAGES = 20         # backstop per search term

# Agency slugs from the Federal Register. Add more slugs here to widen coverage
# (e.g. "commerce-department" for export-control rules).
AGENCIES = [
    "federal-aviation-administration",
    "federal-communications-commission",
    "national-oceanic-and-atmospheric-administration",
    "national-aeronautics-and-space-administration",
]

# RULE = final rule, PRORULE = proposed rule. Add "NOTICE" to include notices.
DOC_TYPES = ["RULE", "PRORULE"]
TYPE_LABELS = {"Rule": "Final Rule", "Proposed Rule": "Proposed Rule",
               "Notice": "Notice", "Presidential Document": "Presidential Doc"}

# One API search per term; results are merged and deduplicated.
SEARCH_TERMS = [
    "space", "satellite", "orbital debris", "launch vehicle",
    "remote sensing", "spaceport", "reentry",
]

# Same idea as the bill script: a title must look space-related to stay.
WORDS = [
    "space", "aerospace", "satellite", "satellites", "orbit", "orbital",
    "orbits", "astronaut", "astronauts", "nasa", "lunar", "spaceport",
    "spaceports", "rocket", "rockets", "reentry",
]
PHRASES = [
    "commercial launch", "launch vehicle", "space launch",
    "remote sensing", "outer space", "earth observation",
]
EXCLUDE_PHRASES = [
    "office space", "space and facilities", "facilities management",
    "parking space", "open space", "green space", "crawl space",
]

TOPIC_RULES = {
    "Orbital Debris":         ["debris", "deorbit", "post-mission disposal"],
    "Commercial Launch":      ["launch", "reentry", "spaceport", "part 450"],
    "Spectrum & Comms":       ["spectrum", "frequency", "earth station",
                               "satellite communication", "orbit act"],
    "Remote Sensing":         ["remote sensing", "earth observation", "imagery"],
    "NASA & Exploration":     ["nasa", "artemis", "lunar", "exploration"],
    "Science & Weather":      ["weather", "environmental data", "heliophysics"],
    "Regulatory & Licensing": ["licens", "authorization", "regulatory",
                               "modernization", "streamlining"],
}

WORD_REGEX = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.IGNORECASE)

FIELDS = ["document_number", "title", "type", "abstract", "publication_date",
          "comments_close_on", "html_url", "agencies"]


# ---------------- Helpers ----------------

def is_space_related(text):
    lower = text.lower()
    if any(p in lower for p in EXCLUDE_PHRASES):
        return False
    return bool(WORD_REGEX.search(text)) or any(p in lower for p in PHRASES)


def tag_topics(text):
    lower = text.lower()
    tags = [topic for topic, keywords in TOPIC_RULES.items()
            if any(k in lower for k in keywords)]
    return tags or ["General Space"]


def agency_names(doc):
    """The API returns a list of agency objects; pull readable names."""
    names = []
    for a in doc.get("agencies") or []:
        name = a.get("name") or a.get("raw_name") or ""
        # Shorten the long official names for the table.
        name = (name.replace("Federal Aviation Administration", "FAA")
                    .replace("Federal Communications Commission", "FCC")
                    .replace("National Oceanic and Atmospheric Administration", "NOAA")
                    .replace("National Aeronautics and Space Administration", "NASA")
                    .replace("Department of Transportation", "DOT")
                    .replace("Department of Commerce", "Commerce"))
        if name and name not in names:
            names.append(name)
    return ", ".join(names) or "—"


def api_get(params):
    """One GET to the Federal Register, with retries on throttling/outages."""
    for attempt in range(5):
        try:
            response = requests.get(API_URL, params=params, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504):
                print(f"  API said {response.status_code}: {response.text[:200]}")
                raise requests.exceptions.HTTPError(str(response.status_code))
            response.raise_for_status()
            return response.json()
        except Exception as error:
            if attempt == 4:
                raise                      # give up: the Action shows red
            wait = 30 * (attempt + 1)
            print(f"  API hiccup ({error}); waiting {wait}s then retrying…")
            time.sleep(wait)


def search_term(term):
    """All pages of one keyword search. Returns raw document dicts."""
    docs, page = [], 1
    while page <= SAFETY_MAX_PAGES:
        params = {
            "conditions[term]": term,
            "conditions[agencies][]": AGENCIES,
            "conditions[type][]": DOC_TYPES,
            "conditions[publication_date][gte]": SINCE,
            "fields[]": FIELDS,
            "per_page": PER_PAGE,
            "order": "newest",
            "page": page,
        }
        results = api_get(params).get("results", [])
        if not results:
            break
        docs.extend(results)
        if len(results) < PER_PAGE:
            break
        page += 1
        time.sleep(0.2)   # be polite
    print(f"  '{term}': {len(docs)} documents")
    return docs


# ---------------- Main ----------------

def main():
    print("Searching the Federal Register…")
    seen = {}
    for term in SEARCH_TERMS:
        for doc in search_term(term):
            number = doc.get("document_number")
            if number and number not in seen:
                seen[number] = doc

    print(f"{len(seen)} unique documents; filtering for space relevance…")
    output = []
    for doc in seen.values():
        title = (doc.get("title") or "").strip()
        abstract = (doc.get("abstract") or "").strip()
        if not is_space_related(title + " " + abstract):
            continue
        output.append({
            "document": doc.get("document_number", "—"),
            "title": title,
            "agency": agency_names(doc),
            "type": TYPE_LABELS.get(doc.get("type", ""), doc.get("type", "—")),
            "published": doc.get("publication_date", ""),
            "comments_close_on": doc.get("comments_close_on"),  # often null
            "topics": tag_topics(title + " " + abstract),
            "url": doc.get("html_url", "https://www.federalregister.gov/"),
        })

    output.sort(key=lambda r: r["published"], reverse=True)

    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "Live data from the Federal Register API",
        "rules": output,
    }

    out_path = Path(__file__).resolve().parent.parent / "data" / "rules.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {len(output)} rules to {out_path}")


if __name__ == "__main__":
    main()
