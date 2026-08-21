"""
fetch_money.py — refresh data/money.json from the USAspending.gov API (free, no key).

The question this answers: where does federal space money actually land?

For each program (NASA, and U.S. Space Force if the API cooperates), it pulls
FY 2025 prime awards — contracts and grants — and asks USAspending for:
  1. total obligations for the year,
  2. the top recipient companies/institutions,
  3. the top congressional districts by place of performance
     (i.e. where the work is done, not where headquarters sit).

Everything lands in data/money.json; the website just displays it.

Note: USAspending uses POST requests with JSON bodies (unlike the other two
APIs). Each program is fetched independently — if one fails (e.g. the Space
Force subtier name isn't recognized), we log it and keep the rest.

Run locally:  python3 scripts/fetch_money.py   (no key needed)
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------- Settings ----------------

API_BASE = "https://api.usaspending.gov/api/v2"

# One complete federal fiscal year: Oct 1, 2024 – Sep 30, 2025.
FISCAL_YEAR_LABEL = "FY 2025"
TIME_PERIOD = [{"start_date": "2024-10-01", "end_date": "2025-09-30"}]

# Prime award types: A–D are contracts, 02–05 are grants.
AWARD_TYPES = ["A", "B", "C", "D", "02", "03", "04", "05"]

# Programs to map. Each is tried independently; failures are logged and skipped.
PROGRAMS = [
    {
        "key": "nasa",
        "label": "NASA",
        "agencies": [{
            "type": "funding", "tier": "toptier",
            "name": "National Aeronautics and Space Administration",
        }],
    },
    {
        "key": "ussf",
        "label": "Space Force",
        "agencies": [{
            "type": "funding", "tier": "subtier",
            "name": "United States Space Force",
            "toptier_name": "Department of Defense",
        }],
    },
]

TOP_RECIPIENTS = 25
TOP_DISTRICTS = 25


# ---------------- Helpers ----------------

def api_post(path, body):
    """One POST to USAspending, with retries on throttling/outages."""
    for attempt in range(5):
        try:
            response = requests.post(f"{API_BASE}{path}", json=body, timeout=90)
            if response.status_code in (429, 500, 502, 503, 504):
                print(f"  API said {response.status_code}: {response.text[:200]}")
                raise requests.exceptions.HTTPError(str(response.status_code))
            if response.status_code == 422:
                # Bad request body — retrying won't help; surface the reason.
                raise ValueError(f"API rejected the query (422): {response.text[:300]}")
            response.raise_for_status()
            return response.json()
        except ValueError:
            raise
        except Exception as error:
            if attempt == 4:
                raise
            wait = 30 * (attempt + 1)
            print(f"  API hiccup ({error}); waiting {wait}s then retrying…")
            time.sleep(wait)


def base_filters(agencies):
    return {
        "time_period": TIME_PERIOD,
        "agencies": agencies,
        "award_type_codes": AWARD_TYPES,
    }


def fetch_total(agencies):
    """Total obligations for the year, via spending grouped by fiscal year."""
    data = api_post("/search/spending_over_time/", {
        "group": "fiscal_year",
        "filters": base_filters(agencies),
    })
    total = 0.0
    for bucket in data.get("results", []):
        total += float(bucket.get("aggregated_amount") or 0)
    return total


def fetch_category(agencies, category, limit):
    """Top entries for one category: 'recipient' or 'district'."""
    data = api_post(f"/search/spending_by_category/{category}/", {
        "category": category,
        "filters": base_filters(agencies),
        "limit": limit,
        "page": 1,
    })
    out = []
    for row in data.get("results", []):
        name = (row.get("name") or "").strip()
        amount = float(row.get("amount") or 0)
        if not name or amount <= 0:
            continue
        # District quirks: "-90" means statewide/multiple districts.
        if category == "district" and name.endswith("-90"):
            name = name[:-3] + " (statewide)"
        out.append({"name": name, "amount": round(amount)})
    out.sort(key=lambda x: -x["amount"])   # biggest first, guaranteed
    return out


# ---------------- Main ----------------

def main():
    programs_out = []
    for program in PROGRAMS:
        label = program["label"]
        print(f"Fetching {FISCAL_YEAR_LABEL} awards funded by {label}…")
        try:
            total = fetch_total(program["agencies"])
            print(f"  total obligations: ${total:,.0f}")
            recipients = fetch_category(program["agencies"], "recipient", TOP_RECIPIENTS)
            print(f"  top recipients: {len(recipients)}")
            time.sleep(0.5)
            districts = fetch_category(program["agencies"], "district", TOP_DISTRICTS)
            print(f"  top districts: {len(districts)}")
            programs_out.append({
                "key": program["key"],
                "label": label,
                "total": round(total),
                "recipients": recipients,
                "districts": districts,
            })
        except Exception as error:
            # Keep going with the other programs — partial data beats none.
            print(f"  SKIPPING {label}: {error}")
        time.sleep(0.5)

    if not programs_out:
        raise SystemExit("No program data could be fetched — see errors above.")

    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "Live data from the USAspending.gov API",
        "fiscal_year": FISCAL_YEAR_LABEL,
        "note": ("Prime awards (contracts and grants). Districts reflect place "
                 "of performance — where the work is done."),
        "programs": programs_out,
    }

    out_path = Path(__file__).resolve().parent.parent / "data" / "money.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {len(programs_out)} program(s) to {out_path}")


if __name__ == "__main__":
    main()
