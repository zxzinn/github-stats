#!/usr/bin/env python3
"""Render two SVG cards from result_clean.json: overview + languages."""
import json
import sys
from pathlib import Path

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Vue": "#41b883", "Rust": "#dea584", "Go": "#00ADD8", "Java": "#b07219",
    "C#": "#178600", "C++": "#f34b7d", "C": "#555555", "Zig": "#ec915c",
    "Dart": "#00B4AB", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c",
    "Markdown": "#083fa1", "MDX": "#fcb32c", "Shell": "#89e051",
    "YAML": "#cb171e", "TOML": "#9c4221", "JSON": "#292929",
    "SQL": "#e38c00", "GraphQL": "#e10098", "Dockerfile": "#384d54",
    "Jupyter Notebook": "#DA5B0B", "Ruby": "#701516", "PHP": "#4F5D95",
    "Lua": "#000080", "Scala": "#c22d40", "Terraform": "#844FBA",
    "Protobuf": "#3D85C6", "Elixir": "#6e4a7e", "Svelte": "#ff3e00",
}
DEFAULT_COLOR = "#888888"

CSS = """
<style>
.card { font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
.bg { fill: #ffffff; stroke: #d0d7de; stroke-width: 1; rx: 6; ry: 6; }
.title { font-size: 16px; font-weight: 600; fill: #1f2328; }
.subtitle { font-size: 11px; fill: #59636e; }
.label { font-size: 13px; fill: #1f2328; }
.value { font-size: 13px; fill: #1f2328; font-weight: 600; text-anchor: end; }
.bar-bg { fill: #eaeef2; }
@media (prefers-color-scheme: dark) {
  .bg { fill: #0d1117; stroke: #30363d; }
  .title, .label, .value { fill: #e6edf3; }
  .subtitle { fill: #9198a1; }
  .bar-bg { fill: #21262d; }
}
</style>
"""

EXCLUDE_FROM_BREAKDOWN = {"JSON", "YAML", "TOML", "Markdown", "MDX"}


def fmt(n: int) -> str:
    return f"{n:,}"


def render_overview(data: dict) -> str:
    t = data["totals"]
    rows = [
        ("Lines added", fmt(t["added"])),
        ("Lines deleted", fmt(t["deleted"])),
        ("Net lines", fmt(t["net"])),
        ("Commits", fmt(t["commits"])),
        ("Repos contributed to", fmt(t["repos_contributed"])),
    ]
    h = 60 + len(rows) * 30 + 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="450" height="{h}" class="card">',
        CSS,
        f'<rect class="bg" x="1" y="1" width="448" height="{h-2}"/>',
        f'<text class="title" x="20" y="32">GitHub stats — {data["user"]}</text>',
        '<text class="subtitle" x="20" y="50">Lines authored across owned + contributed repos (incl. private)</text>',
    ]
    y = 85
    for label, value in rows:
        parts.append(f'<text class="label" x="20" y="{y}">{label}</text>')
        parts.append(f'<text class="value" x="430" y="{y}">{value}</text>')
        y += 30
    excluded = ", ".join(data.get("excluded_languages", []))
    if excluded:
        parts.append(f'<text class="subtitle" x="20" y="{y+5}">Excludes: {excluded}, lockfiles, vendored paths</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_languages(data: dict) -> str:
    langs = {k: v for k, v in data["languages"].items() if k not in EXCLUDE_FROM_BREAKDOWN}
    items = [(name, v["add"] + v["del"]) for name, v in langs.items()]
    items.sort(key=lambda x: -x[1])
    items = items[:8]
    total = sum(v for _, v in items) or 1
    h = 70 + len(items) * 28 + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="450" height="{h}" class="card">',
        CSS,
        f'<rect class="bg" x="1" y="1" width="448" height="{h-2}"/>',
        '<text class="title" x="20" y="32">Most used languages</text>',
        '<text class="subtitle" x="20" y="50">By lines authored (excludes config / docs / lockfiles)</text>',
    ]
    y = 75
    for name, lines in items:
        pct = lines / total * 100
        color = LANG_COLORS.get(name, DEFAULT_COLOR)
        parts.append(f'<text class="label" x="20" y="{y+12}">{name}</text>')
        parts.append(f'<text class="value" x="430" y="{y+12}">{pct:.1f}%</text>')
        parts.append(f'<rect class="bar-bg" x="20" y="{y+16}" width="410" height="6" rx="3" ry="3"/>')
        parts.append(f'<rect x="20" y="{y+16}" width="{max(2, pct*4.1):.1f}" height="6" rx="3" ry="3" fill="{color}"/>')
        y += 28
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overview.svg").write_text(render_overview(data))
    (out_dir / "languages.svg").write_text(render_languages(data))
    print(f"Wrote {out_dir}/overview.svg and {out_dir}/languages.svg")


if __name__ == "__main__":
    main()
