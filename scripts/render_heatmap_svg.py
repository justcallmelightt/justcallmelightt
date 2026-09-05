#!/usr/bin/env python3
"""Render contribution JSON as a polished, self-contained animated SVG."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DARK_PALETTE = ["#20262e", "#123b2a", "#086b3b", "#14a44d", "#39d353"]
LIGHT_PALETTE = ["#e8ecf0", "#b6efc2", "#69d985", "#2fba61", "#178f45"]
CELL = 10
GAP = 4
STEP = CELL + GAP
LEFT = 48
TOP = 132
WIDTH = 860
HEIGHT = 280


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "contributions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "contrib-heatmap.svg")
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def compact_number(value: int) -> str:
    if value < 1_000:
        return str(value)
    compact = f"{value / 1_000:.1f}".rstrip("0").rstrip(".")
    return f"{compact}k"


def human_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return f"{parsed:%b} {parsed.day}"


def month_labels(first_sunday: date, last_date: date) -> list[tuple[int, str]]:
    labels = []
    cursor = date(first_sunday.year, first_sunday.month, 1)
    if cursor < first_sunday:
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    while cursor <= last_date:
        week = (cursor - first_sunday).days // 7
        if 0 <= week < 53:
            labels.append((LEFT + week * STEP, cursor.strftime("%b").upper()))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return labels


def stat_card(x: int, label: str, value: str, detail: str = "") -> str:
    detail_markup = f'<text class="stat-detail" x="{x + 74}" y="88">{esc(detail)}</text>' if detail else ""
    return (
        f'<g class="stat-card"><rect x="{x}" y="52" width="194" height="48" rx="10"/>'
        f'<text class="stat-label" x="{x + 14}" y="70">{esc(label)}</text>'
        f'<text class="stat-value" x="{x + 14}" y="90">{esc(value)}</text>{detail_markup}</g>'
    )


def render(payload: dict[str, object], static: bool = False) -> str:
    raw_days = payload["days"]
    days = {date.fromisoformat(day["date"]): day for day in raw_days}
    first_date, last_date = min(days), max(days)
    first_sunday = last_date - timedelta(days=(last_date.weekday() + 1) % 7, weeks=52)
    username = esc(payload.get("username", "GitHub"))
    stats = payload["stats"]

    cells = []
    for current, day in sorted(days.items()):
        week = (current - first_sunday).days // 7
        weekday = (current.weekday() + 1) % 7
        if not (0 <= week < 53):
            continue
        x, y = LEFT + week * STEP, TOP + weekday * STEP
        level = max(0, min(4, int(day["level"])))
        delay = min(0.74, week * 0.0105 + weekday * 0.021)
        style = "" if static else f' style="--delay:{delay:.3f}s"'
        cells.append(
            f'<rect class="day level-{level}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5"{style}>'
            f'<title>{esc(current.isoformat())}: {esc(day["count"])} contributions</title></rect>'
        )

    months = "".join(
        f'<text class="month" x="{x}" y="121">{esc(label)}</text>'
        for x, label in month_labels(first_sunday, last_date)
    )
    weekdays = "".join(
        f'<text class="weekday" x="20" y="{TOP + row * STEP + 8}">{label}</text>'
        for row, label in ((1, "M"), (3, "W"), (5, "F"))
    )
    legend = "".join(
        f'<rect class="level-{level}" x="{730 + level * 15}" y="249" width="10" height="10" rx="2.5"/>'
        for level in range(5)
    )
    cards = "".join(
        (
            stat_card(20, "CONTRIBUTIONS", compact_number(int(stats["total"])), "LAST YEAR"),
            stat_card(222, "CURRENT STREAK", f'{stats["current_streak"]}d'),
            stat_card(424, "LONGEST STREAK", f'{stats["longest_streak"]}d'),
            stat_card(626, "BEST DAY", str(stats["best_day"]["count"]), human_date(stats["best_day"]["date"])),
        )
    )
    animation_css = "" if static else "\n".join(
        (
            "    .day { opacity: 0; transform: translateY(7px) scale(.72); filter: blur(2px); animation: settle .52s cubic-bezier(.16,1,.3,1) var(--delay) forwards; }",
            "    @keyframes settle { to { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); } }",
            "    @media (prefers-reduced-motion: reduce) {",
            "      .day { transform: none; filter: none; animation: fade .15s ease-out forwards; }",
            "      @keyframes fade { to { opacity: 1; } }",
            "    }",
        )
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{username}'s GitHub contribution activity</title>
  <desc id="desc">{esc(stats['total'])} contributions from {esc(first_date)} to {esc(last_date)}. Current streak {esc(stats['current_streak'])} days and longest streak {esc(stats['longest_streak'])} days.</desc>
  <defs>
    <linearGradient id="canvas-dark" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#151a21"/><stop offset="1" stop-color="#0d1117"/></linearGradient>
    <linearGradient id="canvas-light" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#f6f8fa"/></linearGradient>
  </defs>
  <style>
    :root {{ color-scheme: light dark; }}
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #8b949e; }}
    .canvas {{ fill: url(#canvas-dark); stroke: #30363d; }}
    .top-light {{ stroke: rgba(255,255,255,.16); }}
    .eyebrow {{ fill: #f0f6fc; font-size: 12px; font-weight: 700; letter-spacing: .12em; }}
    .range, .month, .weekday, .legend-label {{ font-size: 9px; letter-spacing: .04em; }}
    .live-dot {{ fill: #39d353; }}
    .stat-card rect {{ fill: rgba(255,255,255,.035); stroke: rgba(255,255,255,.075); }}
    .stat-label {{ font-size: 8px; font-weight: 700; letter-spacing: .1em; }}
    .stat-value {{ fill: #f0f6fc; font-size: 17px; font-weight: 700; letter-spacing: -.04em; }}
    .stat-detail {{ font-size: 8px; letter-spacing: .05em; }}
    .level-0 {{ fill: {DARK_PALETTE[0]}; }} .level-1 {{ fill: {DARK_PALETTE[1]}; }}
    .level-2 {{ fill: {DARK_PALETTE[2]}; }} .level-3 {{ fill: {DARK_PALETTE[3]}; }}
    .level-4 {{ fill: {DARK_PALETTE[4]}; }}
    .day {{ transform-box: fill-box; transform-origin: center; }}
{animation_css}
    @media (prefers-color-scheme: light) {{
      text {{ fill: #656d76; }} .canvas {{ fill: url(#canvas-light); stroke: #d0d7de; }}
      .top-light {{ stroke: rgba(255,255,255,.9); }} .eyebrow, .stat-value {{ fill: #1f2328; }}
      .stat-card rect {{ fill: rgba(255,255,255,.72); stroke: rgba(31,35,40,.10); }}
      .level-0 {{ fill: {LIGHT_PALETTE[0]}; }} .level-1 {{ fill: {LIGHT_PALETTE[1]}; }}
      .level-2 {{ fill: {LIGHT_PALETTE[2]}; }} .level-3 {{ fill: {LIGHT_PALETTE[3]}; }}
      .level-4 {{ fill: {LIGHT_PALETTE[4]}; }}
    }}
  </style>
  <rect class="canvas" x="1" y="1" width="858" height="278" rx="18"/>
  <path class="top-light" d="M20 1.5h820" opacity=".8"/>
  <circle class="live-dot" cx="24" cy="28" r="4"/>
  <text class="eyebrow" x="38" y="32">CONTRIBUTION ACTIVITY</text>
  <text class="range" x="650" y="31">{esc(first_date)}  /  {esc(last_date)}</text>
  {cards}
  {months}
  {weekdays}
  <g aria-label="Contribution days">{''.join(cells)}</g>
  <text class="legend-label" x="690" y="258">LESS</text>{legend}<text class="legend-label" x="814" y="258">MORE</text>
</svg>'''


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    svg = render(payload, static=os.getenv("STATIC") == "1")
    args.output.write_text(svg + "\n", encoding="utf-8")
    print(f"Rendered {args.output}")


if __name__ == "__main__":
    main()
