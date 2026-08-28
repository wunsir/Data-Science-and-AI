"""Small dependency-free SVG renderers for the public analysis pages."""

from __future__ import annotations

import html
from typing import Any


COLORS = ("#1e40af", "#0f766e", "#7c3aed", "#b45309", "#be123c", "#475569")
FONT = "Microsoft YaHei, PingFang SC, sans-serif"


def _value(value: float, kind: str) -> str:
    if kind == "salary":
        return f"¥{value / 1000:,.1f}k"
    if kind == "percent":
        return f"{value:+.1f}%"
    if kind == "rate":
        return f"{value:.1f}%"
    return f"{value:,.0f}"


def _base(title: str, subtitle: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="42" y="48" font-family="{FONT}" font-size="24" font-weight="700" fill="#0f172a">{html.escape(title)}</text>',
        f'<text x="42" y="78" font-family="{FONT}" font-size="14" fill="#64748b">{html.escape(subtitle)}</text>',
    ]


def empty_svg(title: str, subtitle: str, width: int = 960, height: int = 390) -> str:
    parts = _base(title, subtitle, width, height)
    parts += [
        f'<text x="42" y="160" font-family="{FONT}" font-size="16" fill="#64748b">当前分组没有达到展示所需的样本量</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def bar_svg(
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    *,
    kind: str = "count",
    color: str = "#1e40af",
) -> str:
    if not rows:
        return empty_svg(title, subtitle)
    width, left, right, top, row_height = 960, 235, 118, 112, 38
    height = max(390, 145 + row_height * len(rows))
    values = [float(row["value"]) for row in rows]
    minimum, maximum = min(0.0, min(values)), max(0.0, max(values))
    span = maximum - minimum or 1.0
    chart_width = width - left - right
    zero = left + (0.0 - minimum) / span * chart_width
    parts = _base(title, subtitle, width, height)
    parts.append(f'<line x1="{zero:.2f}" y1="{top - 8}" x2="{zero:.2f}" y2="{height - 34}" stroke="#cbd5e1"/>')
    for index, row in enumerate(rows):
        value = float(row["value"])
        y = top + index * row_height
        point = left + (value - minimum) / span * chart_width
        x, bar_width = min(zero, point), max(1.5, abs(point - zero))
        anchor, label_x = ("start", point + 8) if value >= 0 else ("end", point - 8)
        note = f"  n={int(row['n']):,}" if row.get("n") is not None else ""
        parts += [
            f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" font-family="{FONT}" font-size="13" fill="#334155">{html.escape(str(row["label"])[:28])}</text>',
            f'<rect x="{x:.2f}" y="{y + 5}" width="{bar_width:.2f}" height="22" rx="3" fill="{color}" opacity=".9"/>',
            f'<text x="{label_x:.2f}" y="{y + 21}" text-anchor="{anchor}" font-family="{FONT}" font-size="11" fill="#334155">{html.escape(_value(value, kind) + note)}</text>',
        ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _shade(value: float, minimum: float, maximum: float) -> tuple[str, str]:
    ratio = 0.5 if maximum <= minimum else max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    start, end = (239, 246, 255), (30, 64, 175)
    rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True))
    return "#" + "".join(f"{channel:02x}" for channel in rgb), "#ffffff" if ratio > 0.55 else "#1e293b"


def heatmap_svg(
    title: str,
    subtitle: str,
    row_names: list[str],
    column_names: list[str],
    cells: list[dict[str, Any]],
    *,
    kind: str,
) -> str:
    if not row_names or not column_names or not cells:
        return empty_svg(title, subtitle, 1080, 480)
    width, left, right, top, cell_height = 1080, 190, 55, 155, 50
    cell_width = (width - left - right) / len(column_names)
    height = max(470, top + cell_height * len(row_names) + 70)
    lookup = {(str(cell["row"]), str(cell["column"])): cell for cell in cells}
    values = [float(cell["value"]) for cell in cells]
    minimum, maximum = min(values), max(values)
    parts = _base(title, subtitle, width, height)
    for index, column in enumerate(column_names):
        x = left + (index + 0.5) * cell_width
        parts.append(
            f'<text x="{x:.2f}" y="{top - 18}" transform="rotate(-28 {x:.2f} {top - 18})" font-family="{FONT}" font-size="12" fill="#475569">{html.escape(column)}</text>'
        )
    for row_index, row_name in enumerate(row_names):
        y = top + row_index * cell_height
        parts.append(
            f'<text x="{left - 12}" y="{y + 30}" text-anchor="end" font-family="{FONT}" font-size="13" fill="#334155">{html.escape(row_name)}</text>'
        )
        for column_index, column_name in enumerate(column_names):
            x = left + column_index * cell_width
            cell = lookup.get((row_name, column_name))
            if cell:
                fill, text_color = _shade(float(cell["value"]), minimum, maximum)
                label = _value(float(cell["value"]), kind)
            else:
                fill, text_color, label = "#f1f5f9", "#94a3b8", "—"
            parts += [
                f'<rect x="{x + 1:.2f}" y="{y + 1:.2f}" width="{cell_width - 2:.2f}" height="{cell_height - 2:.2f}" rx="3" fill="{fill}"/>',
                f'<text x="{x + cell_width / 2:.2f}" y="{y + 30}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{text_color}">{html.escape(label)}</text>',
            ]
    parts += [
        f'<text x="{left}" y="{height - 28}" font-family="{FONT}" font-size="12" fill="#64748b">浅色表示较低，深色表示较高；“—”为样本量不足。</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def stacked_svg(
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    series: list[str],
) -> str:
    if not rows or not series:
        return empty_svg(title, subtitle)
    width, left, right, top, row_height = 1020, 180, 70, 145, 46
    height = max(450, top + row_height * len(rows) + 75)
    chart_width = width - left - right
    parts = _base(title, subtitle, width, height)
    for index, name in enumerate(series):
        x, y = left + (index % 4) * 180, 103 + (index // 4) * 27
        parts += [
            f'<rect x="{x}" y="{y - 12}" width="12" height="12" rx="2" fill="{COLORS[index % len(COLORS)]}"/>',
            f'<text x="{x + 18}" y="{y - 2}" font-family="{FONT}" font-size="12" fill="#475569">{html.escape(name)}</text>',
        ]
    for row_index, row in enumerate(rows):
        y, values = top + row_index * row_height, row["values"]
        total = sum(float(values.get(name, 0)) for name in series) or 1.0
        parts.append(f'<text x="{left - 12}" y="{y + 23}" text-anchor="end" font-family="{FONT}" font-size="13" fill="#334155">{html.escape(str(row["label"]))}</text>')
        cursor = left
        for index, name in enumerate(series):
            share = float(values.get(name, 0)) / total
            segment = chart_width * share
            if segment:
                parts.append(f'<rect x="{cursor:.2f}" y="{y + 5}" width="{segment:.2f}" height="25" fill="{COLORS[index % len(COLORS)]}"/>')
                if segment > 42:
                    parts.append(f'<text x="{cursor + segment / 2:.2f}" y="{y + 22}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="#ffffff">{share * 100:.0f}%</text>')
            cursor += segment
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def boxplot_svg(title: str, subtitle: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return empty_svg(title, subtitle)
    width, left, right, top, row_height = 980, 220, 105, 120, 42
    height = max(430, top + len(rows) * row_height + 75)
    maximum = max(float(row["high"]) for row in rows) or 1.0
    chart_width = width - left - right
    x = lambda value: left + min(float(value), maximum) / maximum * chart_width
    parts = _base(title, subtitle, width, height)
    for tick in range(6):
        value, point = maximum * tick / 5, x(maximum * tick / 5)
        parts += [
            f'<line x1="{point:.2f}" y1="{top - 12}" x2="{point:.2f}" y2="{height - 48}" stroke="#e2e8f0"/>',
            f'<text x="{point:.2f}" y="{height - 25}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="#64748b">¥{value / 1000:.0f}k</text>',
        ]
    for index, row in enumerate(rows):
        y = top + index * row_height
        low, q1, median, q3, high = (x(row[key]) for key in ("low", "q1", "median", "q3", "high"))
        parts += [
            f'<text x="{left - 12}" y="{y + 21}" text-anchor="end" font-family="{FONT}" font-size="13" fill="#334155">{html.escape(str(row["label"])[:24])}</text>',
            f'<line x1="{low:.2f}" y1="{y + 17}" x2="{high:.2f}" y2="{y + 17}" stroke="#64748b" stroke-width="2"/>',
            f'<rect x="{q1:.2f}" y="{y + 5}" width="{max(2, q3 - q1):.2f}" height="24" rx="3" fill="#dbeafe" stroke="#1e40af" stroke-width="1.5"/>',
            f'<line x1="{median:.2f}" y1="{y + 5}" x2="{median:.2f}" y2="{y + 29}" stroke="#be123c" stroke-width="2.5"/>',
            f'<text x="{high + 7:.2f}" y="{y + 21}" font-family="{FONT}" font-size="11" fill="#64748b">n={int(row["n"]):,}</text>',
        ]
    parts += [f'<text x="{left}" y="{height - 5}" font-family="{FONT}" font-size="11" fill="#64748b">箱体为25%—75%分位数，须线为5%—95%分位数，红线为中位数。</text>', "</svg>"]
    return "\n".join(parts) + "\n"


def multi_bar_svg(
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    series: list[dict[str, str]],
    *,
    kind: str,
) -> str:
    if not rows or not series:
        return empty_svg(title, subtitle)
    width, left, right, top = 1020, 230, 115, 130
    group_height = 28 + 18 * len(series)
    height = max(440, top + group_height * len(rows) + 65)
    values = [float(row["values"].get(spec["key"], 0)) for row in rows for spec in series]
    minimum, maximum = min(0.0, min(values)), max(0.0, max(values))
    span, chart_width = maximum - minimum or 1.0, width - left - right
    zero = left + (0.0 - minimum) / span * chart_width
    parts = _base(title, subtitle, width, height)
    for index, spec in enumerate(series):
        x = left + index * 190
        parts += [
            f'<rect x="{x}" y="96" width="12" height="12" rx="2" fill="{spec["color"]}"/>',
            f'<text x="{x + 18}" y="107" font-family="{FONT}" font-size="12" fill="#475569">{html.escape(spec["name"])}</text>',
        ]
    parts.append(f'<line x1="{zero:.2f}" y1="{top - 8}" x2="{zero:.2f}" y2="{height - 42}" stroke="#94a3b8"/>')
    for row_index, row in enumerate(rows):
        y = top + row_index * group_height
        parts.append(f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" font-family="{FONT}" font-size="13" fill="#334155">{html.escape(str(row["label"])[:26])}</text>')
        for series_index, spec in enumerate(series):
            value = float(row["values"].get(spec["key"], 0))
            bar_y = y + series_index * 18
            point = left + (value - minimum) / span * chart_width
            x, bar_width = min(zero, point), max(1.5, abs(point - zero))
            anchor, label_x = ("start", point + 6) if value >= 0 else ("end", point - 6)
            parts += [
                f'<rect x="{x:.2f}" y="{bar_y + 4}" width="{bar_width:.2f}" height="12" rx="2" fill="{spec["color"]}" opacity=".88"/>',
                f'<text x="{label_x:.2f}" y="{bar_y + 15}" text-anchor="{anchor}" font-family="{FONT}" font-size="10" fill="#475569">{html.escape(_value(value, kind))}</text>',
            ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def lorenz_svg(title: str, subtitle: str, payload: dict[str, Any]) -> str:
    series = payload.get("series", [])
    if not series:
        return empty_svg(title, subtitle, 960, 560)
    width, height, left, right, top, bottom = 960, 590, 100, 70, 120, 82
    chart_width, chart_height = width - left - right, height - top - bottom
    parts = _base(title, subtitle, width, height)
    for tick in range(6):
        ratio = tick / 5
        x, y = left + ratio * chart_width, top + chart_height - ratio * chart_height
        parts += [
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + chart_height}" stroke="#e2e8f0"/>',
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + chart_width}" y2="{y:.2f}" stroke="#e2e8f0"/>',
            f'<text x="{x:.2f}" y="{height - 48}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="#64748b">{ratio * 100:.0f}%</text>',
        ]
    parts.append(f'<line x1="{left}" y1="{top + chart_height}" x2="{left + chart_width}" y2="{top}" stroke="#94a3b8" stroke-dasharray="6 5"/>')
    for index, item in enumerate(series):
        points = " ".join(f"{left + float(point[0]) * chart_width:.2f},{top + chart_height - float(point[1]) * chart_height:.2f}" for point in item["points"])
        color, legend_y = COLORS[index % len(COLORS)], 101 + index * 20
        parts += [
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>',
            f'<line x1="{left + 420}" y1="{legend_y - 4}" x2="{left + 447}" y2="{legend_y - 4}" stroke="{color}" stroke-width="3"/>',
            f'<text x="{left + 455}" y="{legend_y}" font-family="{FONT}" font-size="12" fill="#475569">{html.escape(item["label"])}  Gini={item["gini"]:.3f}</text>',
        ]
    parts += [f'<text x="{left + chart_width / 2}" y="{height - 14}" text-anchor="middle" font-family="{FONT}" font-size="12" fill="#475569">累计职位占比</text>', "</svg>"]
    return "\n".join(parts) + "\n"


def forest_svg(title: str, subtitle: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return empty_svg(title, subtitle, 1080, 500)
    width, left, right, top, row_height = 1080, 280, 105, 122, 31
    height = max(470, top + row_height * len(rows) + 65)
    minimum, maximum = min(0.0, min(float(row["low"]) for row in rows)), max(0.0, max(float(row["high"]) for row in rows))
    span, chart_width = maximum - minimum or 1.0, width - left - right
    x = lambda value: left + (float(value) - minimum) / span * chart_width
    parts = _base(title, subtitle, width, height)
    parts.append(f'<line x1="{x(0):.2f}" y1="{top - 12}" x2="{x(0):.2f}" y2="{height - 42}" stroke="#64748b" stroke-width="1.5"/>')
    for index, row in enumerate(rows):
        y, color = top + index * row_height, row.get("color", COLORS[index % len(COLORS)])
        parts += [
            f'<text x="{left - 12}" y="{y + 9}" text-anchor="end" font-family="{FONT}" font-size="12" fill="#334155">{html.escape(str(row["label"])[:34])}</text>',
            f'<line x1="{x(row["low"]):.2f}" y1="{y + 5}" x2="{x(row["high"]):.2f}" y2="{y + 5}" stroke="{color}" stroke-width="2"/>',
            f'<circle cx="{x(row["value"]):.2f}" cy="{y + 5}" r="4.5" fill="{color}"/>',
        ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"

