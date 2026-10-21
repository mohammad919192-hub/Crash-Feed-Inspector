"""Generate a self-contained, local HTML snapshot from verified CSV rows."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Iterable

from .analytics import describe
from .dataset import quality_report, verified_multipliers

BINS = [
    ("1.00–1.19x", 1.0, 1.2),
    ("1.20–1.49x", 1.2, 1.5),
    ("1.50–1.99x", 1.5, 2.0),
    ("2.00–2.99x", 2.0, 3.0),
    ("3.00–4.99x", 3.0, 5.0),
    ("5.00–9.99x", 5.0, 10.0),
    ("10.00x+", 10.0, float("inf")),
]


def _histogram_svg(values: list[float]) -> str:
    counts = [
        sum(value >= lower and value < upper for value in values)
        for _, lower, upper in BINS
    ]
    maximum = max(counts) or 1
    width, label_width, bar_max, row_height = 720, 112, 500, 42
    height = len(BINS) * row_height + 12
    parts = [
        f'<svg role="img" aria-label="Histogram of verified multipliers" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg">'
    ]
    for index, ((label, _, _), count) in enumerate(zip(BINS, counts)):
        y = 8 + index * row_height
        bar_width = int(bar_max * count / maximum)
        parts.append(f'<text x="0" y="{y + 20}" class="svg-label">{html.escape(label)}</text>')
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{bar_max}" height="25" rx="4" class="bar-bg"/>'
        )
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{bar_width}" height="25" rx="4" class="bar"/>'
        )
        parts.append(
            f'<text x="{label_width + bar_max + 12}" y="{y + 18}" class="svg-value">{count:,}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def generate_dashboard(
    rows: Iterable[dict[str, Any]],
    output_path: str | Path,
    threshold: float = 2.0,
) -> Path:
    """Write a standalone HTML report. Only explicitly verified rows feed statistics."""
    data_rows = list(rows)
    values = verified_multipliers(data_rows)
    if not values:
        raise ValueError("No rows are explicitly verified=true; refusing to chart unverified candidates.")
    stats = describe(values, thresholds=(1.5, 2.0, 3.0, 5.0, 10.0))
    quality = quality_report(data_rows)
    threshold_rate = sum(value >= threshold for value in values) / len(values)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    metric_cards = [
        ("Verified rounds", f"{len(values):,}"),
        ("Mean multiplier", f'{stats["mean"]:.3f}x'),
        ("Median multiplier", f'{stats["median"]:.3f}x'),
        ("P90 (nearest rank)", f'{stats["p90_nearest_rank"]:.3f}x'),
        (f"Hit rate ≥ {threshold:g}x", f"{threshold_rate:.1%}"),
    ]
    cards_html = "".join(
        f'<article class="metric"><div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div></article>'
        for label, value in metric_cards
    )
    thresholds = (1.5, 2.0, 3.0, 5.0, 10.0)
    threshold_rows = "".join(
        "<tr>"
        f"<td>≥ {t:.2f}x</td>"
        f"<td>{sum(value >= t for value in values):,}</td>"
        f"<td>{sum(value >= t for value in values) / len(values):.1%}</td>"
        "</tr>"
        for t in thresholds
    )
    quality_rows = "".join(
        f"<tr><th scope='row'>{html.escape(str(label))}</th><td>{html.escape(str(value))}</td></tr>"
        for label, value in [
            ("CSV rows", quality["row_count"]),
            ("Verified rows used for statistics", quality["verified_rows"]),
            ("Unverified rows excluded", quality["unverified_rows"]),
            ("Rows missing timestamps", quality["missing_timestamps"]),
            ("Out-of-order timestamp transitions", quality["chronology_violations"]),
            ("Timestamp coverage", f'{quality["timestamp_coverage"]:.1%}'),
        ]
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>Crash Feed Inspector — Historical Snapshot</title>
<style>
:root {{ color-scheme: dark; --bg:#0b1020; --panel:#121a2d; --line:#29354d; --text:#edf2ff; --muted:#aab6ce; --accent:#79a8ff; --bar:#79a8ff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif; }}
main {{ max-width:1120px; margin:auto; padding:32px 20px 56px; }}
header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:24px; }}
h1 {{ font-size:clamp(1.7rem,4vw,2.4rem); line-height:1.2; margin:0 0 10px; }}
h2 {{ font-size:1.15rem; margin:0 0 16px; }}
p {{ color:var(--muted); margin:8px 0; }}
.eyebrow {{ color:var(--accent); font-size:.8rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:24px 0; }}
.metric,.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px; min-width:0; }}
.metric-label {{ color:var(--muted); font-size:.88rem; }}
.metric-value {{ font-size:1.7rem; font-weight:750; letter-spacing:-.025em; overflow-wrap:anywhere; }}
.two-col {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr)); gap:16px; margin:16px 0; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-weight:600; font-size:.9rem; }}
tbody tr:last-child th,tbody tr:last-child td {{ border-bottom:0; }}
svg {{ display:block; width:100%; height:auto; overflow:visible; }}
.svg-label,.svg-value {{ fill:var(--text); font-size:13px; }}
.bar-bg {{ fill:var(--line); }} .bar {{ fill:var(--bar); }}
.notice {{ border-left:3px solid var(--accent); padding:12px 14px; background:rgba(121,168,255,.08); border-radius:0 8px 8px 0; }}
footer {{ color:var(--muted); font-size:.85rem; border-top:1px solid var(--line); padding-top:16px; margin-top:24px; }}
@media (max-width:520px) {{ main {{ padding:22px 14px 40px; }} .panel {{ padding:14px; }} .metric {{ padding:14px; }} .metric-value {{ font-size:1.4rem; }} }}
</style>
</head>
<body>
<main>
<header>
<div class="eyebrow">Offline research report</div>
<h1>Crash Feed Inspector</h1>
<p>Historical distribution and data-quality snapshot. This file does not stream live data.</p>
</header>
<section aria-label="Summary metrics" class="grid">{cards_html}</section>
<div class="two-col">
<section class="panel">
<h2>Verified multiplier distribution</h2>
<p>Counts by fixed multiplier range; only rows explicitly marked verified=true are included.</p>
{_histogram_svg(values)}
</section>
<section class="panel">
<h2>Empirical threshold frequencies</h2>
<p>Observed share of verified historical outcomes at or above each threshold.</p>
<table>
<thead><tr><th>Threshold</th><th>Count</th><th>Share</th></tr></thead>
<tbody>{threshold_rows}</tbody>
</table>
</section>
</div>
<section class="panel">
<h2>Dataset quality</h2>
<table><tbody>{quality_rows}</tbody></table>
</section>
<section class="panel" style="margin-top:16px">
<h2>Interpretation limits</h2>
<p class="notice">Historical frequencies describe this dataset; they are not reliable forecasts of the next round. No predictive edge is established by this report. Verify the source, schema, chronology, and sample size before using the data for research.</p>
</section>
<footer>Generated locally by Crash Feed Inspector. No raw message payloads or round identifiers are embedded in this report.</footer>
</main>
</body>
</html>
"""
    output.write_text(document, encoding="utf-8")
    return output
