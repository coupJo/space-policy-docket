"""
fetch_bills.py — refresh data/bills.json with real bills from the Congress.gov API.

How it works, in plain terms:
  1. Walk through EVERY bill of the current Congress, newest updates first
     (the API has no keyword search, so we scan and filter ourselves).
  2. Keep only bills whose title looks space-related (keyword lists below).
  3. Look up each keeper's sponsor — reusing sponsors remembered from the
     previous run so we only ask the API about genuinely new bills.
  4. Tag each bill with topics using simple keyword rules.
  5. Write everything to data/bills.json — the website just displays that file.

Run it locally:
  export CONGRESS_API_KEY=yourkey
  python3 scripts/fetch_bills.py

In production, GitHub Actions runs this daily (see .github/workflows/update-data.yml)
with the key stored as a repository secret — never written into the code.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------- Settings ----------------

API_BASE = "https://api.congress.gov/v3"
CONGRESS = 119                # current Congress (update every two years)
PAGE_SIZE = 250               # max the API allows per request
SAFETY_MAX_PAGES = 80         # backstop so a bug can never loop forever
DETAIL_CALL_CAP = 400         # safety cap on per-bill sponsor lookups

# A bill's title must contain one of these to count as "space policy."
# WORDS are matched as whole words ("mars" won't match "marshal");
# PHRASES are matched anywhere in the title.
WORDS = [
    "space", "aerospace", "satellite", "satellites", "orbit", "orbital",
    "orbits", "astronaut", "astronauts", "nasa", "lunar", "spaceport",
    "spaceports", "rocket", "rockets",
]
PHRASES = [
    "commercial launch", "launch vehicle", "space launch",
    "remote sensing", "outer space",
]

# "Space" also means office space, parking space, green space… skip those.
EXCLUDE_PHRASES = [
    "office space", "space and facilities", "facilities management",
    "parking space", "open space", "green space", "crawl space",
]

# Topic tags shown as pills on the site. First keyword hit wins a tag;
# a bill can earn several tags. Tune these lists freely.
TOPIC_RULES = {
    "Orbital Debris":        ["debris", "sustainability of space", "orbits act"],
    "Commercial Launch":     ["commercial launch", "launch vehicle", "spaceport",
                              "reentry", "commercial space"],
    "NASA & Exploration":    ["nasa", "artemis", "lunar", "moon", "mars",
                              "exploration", "international space station"],
    "Spectrum & Comms":      ["spectrum", "communications", "broadband"],
    "Remote Sensing":        ["remote sensing", "earth observation", "imagery"],
    "National Security":     ["security", "defense", "space force", "missile",
                              "deterrence"],
    "Science & Weather":     ["weather", "science", "research", "heliophysics"],
    "Regulatory & Licensing": ["licens", "authorization", "regulatory",
                               "oversight", "modernization"],
}

# "HR" -> "H.R. 123" for display, and the congress.gov URL slug for links.
TYPE_LABELS = {
    "HR": "H.R.", "S": "S.", "HRES": "H.Res.", "SRES": "S.Res.",
    "HJRES": "H.J.Res.", "SJRES": "S.J.Res.",
    "HCONRES": "H.Con.Res.", "SCONRES": "S.Con.Res.",
}
TYPE_SLUGS = {
    "HR": "house-bill", "S": "senate-bill",
    "HRES": "house-resolution", "SRES": "senate-resolution",
    "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution",
    "HCONRES": "house-concurrent-resolution",
    "SCONRES": "senate-concurrent-resolution",
}

WORD_REGEX = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.IGNORECASE)


# ---------------- Helpers ----------------

def api_get(path, **params):
    """One GET request to the Congress.gov API, with the key attached.

    Retries up to 4 times with growing pauses — the API sometimes answers
    429 ("slow down") or has a brief outage, and we'd rather wait than crash.
    """
    params["api_key"] = os.environ["CONGRESS_API_KEY"]
    params["format"] = "json"
    for attempt in range(5):
        try:
            response = requests.get(f"{API_BASE}{path}", params=params, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504):
                print(f"  API said {response.status_code}: {response.text[:200]}")
                raise requests.exceptions.HTTPError(str(response.status_code))
            response.raise_for_status()
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                api_get.rate_remaining = remaining   # shown in progress lines
            return response.json()
        except Exception as error:
            if attempt == 4:
                raise                      # give up: the Action shows red
            wait = 30 * (attempt + 1)
            print(f"  API hiccup ({error}); waiting {wait}s then retrying…")
            time.sleep(wait)

api_get.rate_remaining = "?"


def is_space_related(title):
    lower = title.lower()
    if any(p in lower for p in EXCLUDE_PHRASES):
        return False
    return bool(WORD_REGEX.search(title)) or any(p in lower for p in PHRASES)


def tag_topics(title):
    lower = title.lower()
    tags = [topic for topic, keywords in TOPIC_RULES.items()
            if any(k in lower for k in keywords)]
    return tags or ["General Space"]


def ordinal(n):
    return f"{n}th"  # good enough for 119th, 120th, 121st is 2029's problem


def fetch_sponsor(bill_type, number):
    """One extra API call per bill: the list endpoint doesn't include sponsors."""
    try:
        data = api_get(f"/bill/{CONGRESS}/{bill_type.lower()}/{number}")
        sponsors = data.get("bill", {}).get("sponsors", [])
        if not sponsors:
            return "—"
        s = sponsors[0]
        prefix = "Sen." if bill_type.upper().startswith("S") else "Rep."
        name = f"{s.get('firstName', '').title()} {s.get('lastName', '').title()}".strip()
        party_state = f"({s.get('party', '?')}-{s.get('state', '?')})"
        return f"{prefix} {name} {party_state}"
    except Exception as error:
        print(f"  warning: no sponsor for {bill_type} {number}: {error}")
        return "—"


# ---------------- Main ----------------

def main():
    if not os.environ.get("CONGRESS_API_KEY"):
        sys.exit("Error: set the CONGRESS_API_KEY environment variable first.")

    # Sponsors never change, so remember the ones we already looked up in the
    # previous run's bills.json — cuts API calls by ~80% on a normal day.
    out_path = Path(__file__).resolve().parent.parent / "data" / "bills.json"
    known_sponsors = {}
    if out_path.exists():
        for old in json.loads(out_path.read_text()).get("bills", []):
            if old.get("sponsor") and old["sponsor"] != "—":
                known_sponsors[old["bill"]] = old["sponsor"]
    print(f"Sponsors remembered from last run: {len(known_sponsors)}")

    print(f"Scanning the entire {CONGRESS}th Congress for space-related bills…")
    seen = {}      # (type, number) -> raw bill, dedupes across pages
    scanned = 0

    # Walk through EVERY bill of this Congress, 250 at a time,
    # until the API returns an empty page.
    for page in range(SAFETY_MAX_PAGES):
        batch = api_get(
            f"/bill/{CONGRESS}",
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE,
            sort="updateDate desc",   # the API reads this as "updateDate+desc"
        )
        bills = batch.get("bills", [])
        if not bills:
            break
        scanned += len(bills)
        for raw in bills:
            key = (raw.get("type", ""), str(raw.get("number", "")))
            if key not in seen and is_space_related(raw.get("title", "")):
                seen[key] = raw
        time.sleep(0.2)   # small pause between pages, avoids burst throttling
        if (page + 1) % 10 == 0:
            print(f"  …{scanned} bills scanned, {len(seen)} space-related so far "
                  f"(API quota left: {api_get.rate_remaining})")

    print(f"Scanned {scanned} bills total; {len(seen)} look space-related.")

    matches = list(seen.values())[:DETAIL_CALL_CAP]
    new_lookups = 0

    output = []
    for raw in matches:
        bill_type = raw.get("type", "").upper()
        number = str(raw.get("number", ""))
        latest = raw.get("latestAction", {}) or {}
        slug = TYPE_SLUGS.get(bill_type, "bill")
        label = f"{TYPE_LABELS.get(bill_type, bill_type)} {number}"

        # Use the remembered sponsor if we have it; only ask the API for new bills.
        sponsor = known_sponsors.get(label)
        if not sponsor:
            sponsor = fetch_sponsor(bill_type, number)
            new_lookups += 1
            time.sleep(0.2)   # be polite to the API

        output.append({
            "bill": label,
            "congress": ordinal(raw.get("congress", CONGRESS)),
            "title": raw.get("title", "").strip(),
            "sponsor": sponsor,
            "latest_action": latest.get("text", "—"),
            "action_date": latest.get("actionDate", raw.get("introducedDate", "")),
            "topics": tag_topics(raw.get("title", "")),
            "url": f"https://www.congress.gov/bill/"
                   f"{ordinal(raw.get('congress', CONGRESS))}-congress/{slug}/{number}",
        })

    print(f"Sponsors: {len(matches) - new_lookups} remembered, {new_lookups} fetched fresh.")

    # Newest action first.
    output.sort(key=lambda b: b["action_date"], reverse=True)

    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "Live data from the Congress.gov API",
        "bills": output,
    }

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {len(output)} bills to {out_path}")


if __name__ == "__main__":
    main()
