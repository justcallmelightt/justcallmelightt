#!/usr/bin/env python3
"""Render contribution JSON as a self-contained animated SVG."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
LIGHT_PALETTE = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
CELL = 11
GAP = 4
STEP = CELL + GAP
LEFT = 40
TOP = 42
WIDTH = 860
HEIGHT = 184


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "contributions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "contrib-heatmap.svg")
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def month_labels(first_sunday: date, last_date: date) -> list[tuple[int, str]]:
    labels = []
    cursor = date(first_sunday.year, first_sunday.month, 1)
    if cursor < first_sunday:
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    while cursor <= last_date:
        week = (cursor - first_sunday).days // 7
        if 0 <= week < 53:
            labels.append((LEFT + week * STEP, cursor.strftime("%b")))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return labels


def render(payload: dict[str, object], static: bool = False) -> str:
    raw_days = payload["days"]
    days = {date.fromisoformat(day["date"]): day for day in raw_days}
    last_date = max(days)
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
        delay = min(0.72, week * 0.011 + weekday * 0.018)
        style = "" if static else f' style="--delay:{delay:.3f}s"'
        cells.append(
            f'<rect class="day level-{level}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3"{style}>'
            f'<title>{esc(current.isoformat())}: {esc(day["count"])} contributions</title></rect>'
        )

    months = "".join(
        f'<text class="month" x="{x}" y="27">{esc(label)}</text>'
        for x, label in month_labels(first_sunday, last_date)
    )
    weekdays = "".join(
        f'<text class="weekday" x="0" y="{TOP + row * STEP + 9}">{label}</text>'
        for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend = "".join(
        f'<rect class="level-{level}" x="{727 + level * 15}" y="151" width="11" height="11" rx="3"/>'
        for level in range(5)
    )
    animation_css = "" if static else "\n".join(
        (
            "      .day { opacity: 0; transform: translateY(-9px); animation: reveal .42s cubic-bezier(.22,1,.36,1) var(--delay) forwards; }",
            "      @keyframes reveal { to { opacity: 1; transform: translateY(0); } }",
            "      @media (prefers-reduced-motion: reduce) {",
            "        .day { transform: none; animation: fade .15s ease-out var(--delay) forwards; }",
            "        @keyframes fade { to { opacity: 1; } }",
            "      }",
        )
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{username}'s GitHub contribution heatmap</title>
  <desc id="desc">{esc(stats['total'])} contributions, current streak {esc(stats['current_streak'])} days, longest streak {esc(stats['longest_streak'])} days.</desc>
  <style>
    :root {{ color-scheme: light dark; }}
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #8b949e; }}
    .month, .weekday, .legend-label {{ font-size: 11px; }}
    .summary {{ font-size: 12px; font-weight: 600; letter-spacing: -.01em; }}
    .level-0 {{ fill: {PALETTE[0]}; }} .level-1 {{ fill: {PALETTE[1]}; }}
    .level-2 {{ fill: {PALETTE[2]}; }} .level-3 {{ fill: {PALETTE[3]}; }}
    .level-4 {{ fill: {PALETTE[4]}; }}
    .day {{ transform-box: fill-box; transform-origin: center; }}
    {animation_css}
    @media (prefers-color-scheme: light) {{
      text {{ fill: #57606a; }}
      .level-0 {{ fill: {LIGHT_PALETTE[0]}; }} .level-1 {{ fill: {LIGHT_PALETTE[1]}; }}
      .level-2 {{ fill: {LIGHT_PALETTE[2]}; }} .level-3 {{ fill: {LIGHT_PALETTE[3]}; }}
      .level-4 {{ fill: {LIGHT_PALETTE[4]}; }}
    }}
  </style>
  {months}
  {weekdays}
  <g aria-label="Contribution days">{''.join(cells)}</g>
  <text class="summary" x="0" y="160">{esc(stats['total'])} contributions · {esc(stats['current_streak'])} day streak · best {esc(stats['best_day']['count'])} on {esc(stats['best_day']['date'])}</text>
  <text class="legend-label" x="700" y="160">Less</text>{legend}<text class="legend-label" x="807" y="160">More</text>
</svg>'''


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    svg = render(payload, static=os.getenv("STATIC") == "1")
    args.output.write_text(svg + "\n", encoding="utf-8")
    print(f"Rendered {args.output}")


if __name__ == "__main__":
    main()
