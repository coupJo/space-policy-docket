"""
build_digest.py — write data/digest.json: "This Week in Space Policy."

Runs AFTER fetch_bills.py and fetch_rules.py (see the workflow). It reads the
two data files those scripts produce and summarizes the trailing 7 days:

  - bills whose latest action happened this week
  - rules and proposed rules published this week
  - comment deadlines coming up in the next 30 days

No API calls, no key — just reading the JSON already on disk.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WINDOW_DAYS = 7          # "this week" = the trailing 7 days
DEADLINE_LOOKAHEAD = 30  # comment deadlines within the next 30 days
MAX_ITEMS = 10           # per section, keeps the card readable


def load(name):
    path = DATA_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main():
    today = datetime.now(timezone.utc).date()
    window_start = today - timedelta(days=WINDOW_DAYS)
    deadline_end = today + timedelta(days=DEADLINE_LOOKAHEAD)

    bills = load("bills.json").get("bills", [])
    rules = load("rules.json").get("rules", [])

    def in_window(date_string):
        if not date_string:
            return False
        d = datetime.strptime(date_string, "%Y-%m-%d").date()
        return window_start < d <= today

    week_bills = [
        {"bill": b["bill"], "title": b["title"],
         "latest_action": b["latest_action"],
         "action_date": b["action_date"], "url": b["url"]}
        for b in bills if in_window(b.get("action_date"))
    ][:MAX_ITEMS]

    week_rules = [
        {"document": r["document"], "title": r["title"], "agency": r["agency"],
         "type": r["type"], "published": r["published"], "url": r["url"]}
        for r in rules if in_window(r.get("published"))
    ][:MAX_ITEMS]

    deadlines = []
    for r in rules:
        close = r.get("comments_close_on")
        if not close:
            continue
        d = datetime.strptime(close, "%Y-%m-%d").date()
        if today <= d <= deadline_end:
            deadlines.append({"document": r["document"], "title": r["title"],
                              "agency": r["agency"], "closes": close,
                              "url": r["url"]})
    deadlines.sort(key=lambda x: x["closes"])
    deadlines = deadlines[:MAX_ITEMS]

    # One-line summary shown as the card's subtitle.
    parts = []
    parts.append(f"{len(week_bills)} bill action{'s' if len(week_bills) != 1 else ''}")
    parts.append(f"{len(week_rules)} rule{'s' if len(week_rules) != 1 else ''} published")
    if deadlines:
        parts.append(f"{len(deadlines)} comment deadline{'s' if len(deadlines) != 1 else ''} ahead")
    summary = " · ".join(parts)

    result = {
        "generated": today.strftime("%Y-%m-%d"),
        "window_start": window_start.strftime("%Y-%m-%d"),
        "window_end": today.strftime("%Y-%m-%d"),
        "summary": summary,
        "bills": week_bills,
        "rules": week_rules,
        "deadlines": deadlines,
    }

    out_path = DATA_DIR / "digest.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Digest: {summary}  →  {out_path}")


if __name__ == "__main__":
    main()
