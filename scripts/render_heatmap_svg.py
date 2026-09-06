#!/usr/bin/env python3
"""Render contribution JSON as a self-contained animated SVG."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
FONT_URL = (
    "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/"
    "packages/pretendard-std/dist/web/variable/woff2/PretendardStdVariable.woff2"
)
EMBEDDED_FONT_PATTERN = re.compile(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)")
DARK_PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
LIGHT_PALETTE = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
CELL = 10
GAP = 4
STEP = CELL + GAP
LEFT = 42
TOP = 28
WIDTH = 860
HEIGHT = 174


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "contributions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "contrib-heatmap.svg")
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_font_data(output: Path) -> str:
    if output.exists():
        match = EMBEDDED_FONT_PATTERN.search(output.read_text(encoding="utf-8"))
        if match:
            return match.group(1)

    response = requests.get(FONT_URL, timeout=30)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("ascii")


def short_date(value: str) -> str:
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
            labels.append((LEFT + week * STEP, cursor.strftime("%b")))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return labels


def render(payload: dict[str, object], font_data: str, static: bool = False) -> str:
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
        delay = week * 0.034 + weekday * 0.024
        peak = 1.18 + level * 0.18
        style = "" if static else f' style="--delay:{delay:.3f}s;--peak:{peak:.2f}"'
        state = "empty" if level == 0 else "active"
        cells.append(
            f'<rect class="cell {state} level-{level}" x="{x}" y="{y}" width="{CELL}" '
            f'height="{CELL}" rx="1.5"{style}><title>{esc(current.isoformat())}: '
            f'{esc(day["count"])} contributions</title></rect>'
        )

    months = "".join(
        f'<text class="month" x="{x}" y="18">{esc(label)}</text>'
        for x, label in month_labels(first_sunday, last_date)
    )
    weekdays = "".join(
        f'<text class="weekday" x="8" y="{TOP + row * STEP + 9}">{label}</text>'
        for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend = "".join(
        f'<rect class="level-{level}" x="{704 + level * 15}" y="145" width="10" height="10" rx="1.5"/>'
        for level in range(5)
    )
    animation_css = "" if static else "\n".join(
        (
            "    .cell { opacity: 0; }",
            "    .empty { animation: reveal-empty .38s cubic-bezier(.2,.8,.2,1) var(--delay) both; }",
            "    .active { animation: pop .58s cubic-bezier(.16,1,.3,1) var(--delay) both, flash .74s ease-out var(--delay) both; }",
            "    @keyframes reveal-empty { from { opacity: 0; transform: scale(.72); } to { opacity: 1; transform: scale(1); } }",
            "    @keyframes pop { 0% { opacity: 0; transform: scale(.18); } 58% { opacity: 1; transform: scale(1.08); } 100% { opacity: 1; transform: scale(1); } }",
            "    @keyframes flash { 0%, 38% { filter: brightness(var(--peak)); } 100% { filter: brightness(1); } }",
            "    @media (prefers-reduced-motion: reduce) {",
            "      .cell { transform: none; filter: none; animation: fade .15s ease-out forwards; }",
            "      @keyframes fade { to { opacity: 1; } }",
            "    }",
        )
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{username}'s GitHub contribution heatmap</title>
  <desc id="desc">{esc(stats['total'])} contributions, current streak {esc(stats['current_streak'])} days, longest streak {esc(stats['longest_streak'])} days.</desc>
  <style>
    @font-face {{ font-family: "Pretendard Embedded"; src: url("data:font/woff2;base64,{font_data}") format("woff2"); font-weight: 45 920; font-style: normal; }}
    :root {{ color-scheme: light dark; }}
    text {{ font-family: "Pretendard Embedded", Pretendard, -apple-system, BlinkMacSystemFont, sans-serif; fill: #8b949e; }}
    .month, .weekday, .legend-label {{ font-size: 10px; font-weight: 500; letter-spacing: -.01em; }}
    .summary {{ fill: #c9d1d9; font-size: 11px; font-weight: 600; letter-spacing: -.015em; }}
    .level-0 {{ fill: {DARK_PALETTE[0]}; }} .level-1 {{ fill: {DARK_PALETTE[1]}; }}
    .level-2 {{ fill: {DARK_PALETTE[2]}; }} .level-3 {{ fill: {DARK_PALETTE[3]}; }}
    .level-4 {{ fill: {DARK_PALETTE[4]}; }}
    .cell {{ transform-box: fill-box; transform-origin: center; stroke: rgba(255,255,255,.045); stroke-width: .5; }}
{animation_css}
    @media (prefers-color-scheme: light) {{
      text {{ fill: #57606a; }} .summary {{ fill: #424a53; }}
      .level-0 {{ fill: {LIGHT_PALETTE[0]}; }} .level-1 {{ fill: {LIGHT_PALETTE[1]}; }}
      .level-2 {{ fill: {LIGHT_PALETTE[2]}; }} .level-3 {{ fill: {LIGHT_PALETTE[3]}; }}
      .level-4 {{ fill: {LIGHT_PALETTE[4]}; }}
      .cell {{ stroke: rgba(27,31,36,.055); }}
    }}
  </style>
  {months}
  {weekdays}
  <g aria-label="Contribution days">{''.join(cells)}</g>
  <text class="summary" x="8" y="155">{esc(stats['total'])} contributions  ·  {esc(stats['current_streak'])} day streak  ·  longest {esc(stats['longest_streak'])} days  ·  best {esc(stats['best_day']['count'])} on {esc(short_date(stats['best_day']['date']))}</text>
  <text class="legend-label" x="672" y="155">Less</text>{legend}<text class="legend-label" x="784" y="155">More</text>
</svg>'''


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    font_data = load_font_data(args.output)
    svg = render(payload, font_data, static=os.getenv("STATIC") == "1")
    args.output.write_text(svg + "\n", encoding="utf-8")
    print(f"Rendered {args.output}")


if __name__ == "__main__":
    main()
