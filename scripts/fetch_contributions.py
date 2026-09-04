#!/usr/bin/env python3
"""Fetch a public GitHub contribution calendar and save normalized JSON."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DEFAULT_USERNAME = "justcallmelightt"
COUNT_PATTERN = re.compile(r"([\d,]+) contributions? on", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=os.getenv("GITHUB_USERNAME", DEFAULT_USERNAME))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "contributions.json",
    )
    parser.add_argument("--html", type=Path, help="Parse a saved response instead of fetching")
    return parser.parse_args()


def fetch_html(username: str) -> str:
    response = requests.get(
        f"https://github.com/users/{username}/contributions",
        headers={
            "Accept": "text/html",
            "User-Agent": f"{username}-profile-readme/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def contribution_count(cell, soup: BeautifulSoup) -> int:
    if cell.get("data-count") is not None:
        return int(cell["data-count"])

    cell_id = cell.get("id")
    tooltip = soup.find("tool-tip", attrs={"for": cell_id}) if cell_id else None
    text = tooltip.get_text(" ", strip=True) if tooltip else ""
    if text.lower().startswith("no contributions"):
        return 0
    match = COUNT_PATTERN.search(text)
    if not match:
        raise ValueError(f"Could not find contribution count for {cell.get('data-date')}")
    return int(match.group(1).replace(",", ""))


def parse_days(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.select(".ContributionCalendar-day[data-date]")
    if not cells:
        raise ValueError("GitHub contribution cells were not found; the page structure may have changed")

    days = []
    for cell in cells:
        days.append(
            {
                "date": cell["data-date"],
                "count": contribution_count(cell, soup),
                "level": max(0, min(4, int(cell.get("data-level", 0)))),
            }
        )
    return sorted(days, key=lambda day: day["date"])


def streak_ending_on(counts: dict[date, int], end: date) -> int:
    length = 0
    cursor = end
    while counts.get(cursor, 0) > 0:
        length += 1
        cursor -= timedelta(days=1)
    return length


def derive_stats(days: list[dict[str, object]]) -> dict[str, object]:
    parsed = [(date.fromisoformat(str(day["date"])), int(day["count"])) for day in days]
    counts = dict(parsed)
    today = min(date.today(), parsed[-1][0])
    streak_end = today if counts.get(today, 0) > 0 else today - timedelta(days=1)

    longest = running = 0
    previous: date | None = None
    for day, count in parsed:
        if count > 0:
            running = running + 1 if previous == day - timedelta(days=1) else 1
            longest = max(longest, running)
            previous = day
        else:
            running = 0
            previous = None

    monthly: dict[str, int] = defaultdict(int)
    for day, count in parsed:
        monthly[day.strftime("%Y-%m")] += count

    best_date, best_count = max(parsed, key=lambda item: (item[1], item[0]))
    return {
        "total": sum(count for _, count in parsed),
        "current_streak": streak_ending_on(counts, streak_end),
        "longest_streak": longest,
        "best_day": {"date": best_date.isoformat(), "count": best_count},
        "monthly_totals": dict(sorted(monthly.items())),
    }


def main() -> None:
    args = parse_args()
    html = args.html.read_text(encoding="utf-8") if args.html else fetch_html(args.username)
    days = parse_days(html)
    payload = {
        "username": args.username,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "range": {"from": days[0]["date"], "to": days[-1]["date"]},
        "days": days,
        "stats": derive_stats(days),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(days)} days for {args.username} to {args.output}")


if __name__ == "__main__":
    main()
