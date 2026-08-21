"""
fetch_bills.py — refresh data/bills.json with real bills from the Congress.gov API.

How it works, in plain terms:
  1. Download every bill of the current Congress, newest updates first
     (the API has no keyword search, so we cast a wide net first).
  2. Keep only bills whose title looks space-related (keyword lists below).
  3. For each keeper, make one extra API call to get its sponsor.
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
    """One GET request to the Congress.gov API, with the key attached."""
    params["api_key"] = os.environ["CONGRESS_API_KEY"]
    params["format"] = "json"
    response = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
    response.raise_for_status()   # crash loudly on errors so the Action shows red
    return response.json()


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
        if (page + 1) % 10 == 0:
            print(f"  …{scanned} bills scanned, {len(seen)} space-related so far")

    print(f"Scanned {scanned} bills total; {len(seen)} look space-related.")

    matches = list(seen.values())[:DETAIL_CALL_CAP]
    print(f"Fetching sponsors for {len(matches)} bills…")

    output = []
    for raw in matches:
        bill_type = raw.get("type", "").upper()
        number = str(raw.get("number", ""))
        latest = raw.get("latestAction", {}) or {}
        slug = TYPE_SLUGS.get(bill_type, "bill")
        output.append({
            "bill": f"{TYPE_LABELS.get(bill_type, bill_type)} {number}",
            "congress": ordinal(raw.get("congress", CONGRESS)),
            "title": raw.get("title", "").strip(),
            "sponsor": fetch_sponsor(bill_type, number),
            "latest_action": latest.get("text", "—"),
            "action_date": latest.get("actionDate", raw.get("introducedDate", "")),
            "topics": tag_topics(raw.get("title", "")),
            "url": f"https://www.congress.gov/bill/"
                   f"{ordinal(raw.get('congress', CONGRESS))}-congress/{slug}/{number}",
        })
        time.sleep(0.1)   # be polite to the API

    # Newest action first.
    output.sort(key=lambda b: b["action_date"], reverse=True)

    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "Live data from the Congress.gov API",
        "bills": output,
    }

    out_path = Path(__file__).resolve().parent.parent / "data" / "bills.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {len(output)} bills to {out_path}")


if __name__ == "__main__":
    main()
