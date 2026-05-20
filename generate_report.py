import pandas as pd
import sys
from datetime import datetime

CSV_RAW      = "report_no_filter.csv"
CSV_FILTERED = "report_filtered.csv"
OUT          = "backtest_report.html"


def load(path):
    df = pd.read_csv(path, parse_dates=["time"])
    return df


def stats(df):
    total  = len(df)
    wins   = len(df[df["t1"] == "win"])
    losses = len(df[df["t1"] == "loss"])
    wr     = wins / total * 100 if total else 0
    total_rr = df["rr"].sum()
    avg_rr   = df["rr"].mean() if total else 0
    full_wins = len(df[df["t2"] == "win"])
    be_wins   = len(df[df["t2"] == "be"])
    return dict(total=total, wins=wins, losses=losses, wr=wr,
                total_rr=total_rr, avg_rr=avg_rr,
                full_wins=full_wins, be_wins=be_wins)


def equity_points(df):
    rr = 0
    points = [0]
    for r in df["rr"]:
        rr += r
        points.append(round(rr, 2))
    return points


def sparkline_svg(points, width=320, height=80):
    if len(points) < 2:
        return ""
    mn, mx = min(points), max(points)
    rng = mx - mn if mx != mn else 1
    pad = 10
    w, h = width - pad * 2, height - pad * 2

    def px(i, v):
        x = pad + i / (len(points) - 1) * w
        y = pad + (1 - (v - mn) / rng) * h
        return f"{x:.1f},{y:.1f}"

    coords = " ".join(px(i, v) for i, v in enumerate(points))
    zero_y = pad + (1 - (0 - mn) / rng) * h
    color  = "#22c55e" if points[-1] >= 0 else "#ef4444"
    return f"""
    <svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
      <line x1="{pad}" y1="{zero_y:.1f}" x2="{width-pad}" y2="{zero_y:.1f}"
            stroke="#e5e7eb" stroke-width="1" stroke-dasharray="4"/>
      <polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"
                stroke-linejoin="round" stroke-linecap="round"/>
    </svg>"""


def pair_rows(df):
    rows = ""
    by_pair = df.groupby("pair").agg(
        trades=("rr", "count"),
        wins=("t1", lambda x: (x == "win").sum()),
        rr=("rr", "sum")
    ).sort_values("rr", ascending=False)
    for pair, row in by_pair.iterrows():
        wr = row["wins"] / row["trades"] * 100
        rr_color = "#22c55e" if row["rr"] >= 0 else "#ef4444"
        rr_sign  = "+" if row["rr"] > 0 else ""
        rows += f"""
        <tr>
          <td><strong>{pair}</strong></td>
          <td>{int(row['trades'])}</td>
          <td>{wr:.0f}%</td>
          <td style="color:{rr_color};font-weight:600">{rr_sign}{row['rr']:.1f}R</td>
        </tr>"""
    return rows


def trade_rows(df):
    rows = ""
    for _, t in df.sort_values("time").iterrows():
        t1_color = "#22c55e" if t["t1"] == "win" else "#ef4444"
        rr_color = "#22c55e" if t["rr"] > 0 else "#ef4444"
        rr_sign  = "+" if t["rr"] > 0 else ""
        dir_icon = "▲" if t["direction"] == "up" else "▼"
        dir_color = "#22c55e" if t["direction"] == "up" else "#ef4444"
        rows += f"""
        <tr>
          <td>{str(t['time'])[:16]}</td>
          <td><strong>{t['pair']}</strong></td>
          <td style="color:{dir_color}">{dir_icon} {t['direction'].upper()}</td>
          <td style="color:{t1_color};font-weight:600">{t['t1'].upper()}</td>
          <td>{t['t2'].upper()}</td>
          <td style="color:{rr_color};font-weight:600">{rr_sign}{t['rr']:.1f}R</td>
        </tr>"""
    return rows


def comparison_section(s_raw, s_filt):
    def cell(val, good_if_high=True):
        if isinstance(val, float):
            color = "#22c55e" if (val >= 0 if not good_if_high else val >= 38) else "#ef4444"
            sign  = "+" if val > 0 else ""
            return f'<td style="color:{color};font-weight:700">{sign}{val:.1f}</td>'
        return f"<td>{val}</td>"

    rows = [
        ("Total Trades",  s_raw["total"],    s_filt["total"],    False),
        ("Win Rate (%)",  round(s_raw["wr"],1),  round(s_filt["wr"],1),  True),
        ("Total RR",      round(s_raw["total_rr"],1), round(s_filt["total_rr"],1), False),
        ("Avg RR/Trade",  round(s_raw["avg_rr"],2),   round(s_filt["avg_rr"],2),   False),
        ("Full Wins",     s_raw["full_wins"], s_filt["full_wins"], False),
        ("BE Wins",       s_raw["be_wins"],   s_filt["be_wins"],   False),
        ("Losses",        s_raw["losses"],    s_filt["losses"],    False),
    ]
    html = ""
    for label, v_raw, v_filt, pct in rows:
        def fmt(v, good_if_high=False):
            if isinstance(v, float):
                color = "#22c55e" if v >= (38 if pct else 0) else "#ef4444"
                sign  = "+" if v > 0 else ""
                return f'<td style="color:{color};font-weight:700">{sign}{v}</td>'
            return f"<td><strong>{v}</strong></td>"
        html += f"<tr><td>{label}</td>{fmt(v_raw)}{fmt(v_filt, pct)}</tr>"
    return html


def build_html(df_raw, df_filt, s_raw, s_filt, eq_raw, eq_filt):
    date_from = str(df_raw["time"].min())[:10]
    date_to   = str(df_raw["time"].max())[:10]
    generated = datetime.now().strftime("%d %B %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Price Trap — Backtest Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f8fafc; color: #1e293b; }}
  .page {{ max-width: 960px; margin: 0 auto; padding: 40px 32px; }}

  .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
             color: white; border-radius: 16px; padding: 40px; margin-bottom: 32px; }}
  .header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 6px; }}
  .header p  {{ font-size: 14px; opacity: 0.8; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
  .section {{ background: white; border-radius: 12px; padding: 24px;
              box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 24px; }}
  .section h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 20px;
                 color: #1e293b; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; }}
  .section.bad  {{ border-top: 4px solid #ef4444; }}
  .section.good {{ border-top: 4px solid #22c55e; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; padding: 10px 12px; background: #f8fafc;
        color: #64748b; font-weight: 600; font-size: 12px;
        text-transform: uppercase; letter-spacing: .04em; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #fafafa; }}

  .verdict {{ border-radius: 12px; padding: 20px 24px; margin-bottom: 24px;
              background: #f0fdf4; border: 1px solid #bbf7d0; }}
  .verdict h3 {{ color: #15803d; font-size: 15px; margin-bottom: 8px; }}
  .verdict p  {{ color: #166534; font-size: 13px; line-height: 1.6; }}

  .footer {{ text-align: center; font-size: 12px; color: #94a3b8; margin-top: 40px; }}
  @media print {{ body {{ background: white; }} .page {{ padding: 20px; }} }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <h1>Price Trap Strategy — Backtest Report</h1>
    <p>Period: {date_from} to {date_to} &nbsp;|&nbsp; 21 Pairs &nbsp;|&nbsp; Generated: {generated}</p>
    <p style="margin-top:8px;font-size:13px;opacity:.7">
      H1 range breakout · M15 engulfing confirmation · Fibonacci 61.8% entry · SL at -78.6% extension
    </p>
  </div>

  <div class="verdict">
    <h3>Key Finding</h3>
    <p>
      The pure mechanical strategy (no filter) yields a <strong>26.7% win rate and negative RR</strong>
      — meaning the rules alone are not enough. Adding a D1 EMA50 trend filter (only trade in the
      direction of the daily trend) improves results to a <strong>42.9% win rate and positive RR</strong>.
      This single condition is what bridges manual discretion to an automated EA.
    </p>
  </div>

  <div class="two-col">
    <div class="section bad">
      <h2>❌ Without D1 Trend Filter</h2>
      {sparkline_svg(eq_raw, width=380, height=90)}
    </div>
    <div class="section good">
      <h2>✅ With D1 Trend Filter</h2>
      {sparkline_svg(eq_filt, width=380, height=90)}
    </div>
  </div>

  <div class="section">
    <h2>Results Comparison</h2>
    <table>
      <thead>
        <tr><th>Metric</th><th>Without Filter</th><th>With D1 Filter</th></tr>
      </thead>
      <tbody>{comparison_section(s_raw, s_filt)}</tbody>
    </table>
  </div>

  <div class="two-col">
    <div class="section bad">
      <h2>Pair Performance — No Filter</h2>
      <table>
        <thead><tr><th>Pair</th><th>Trades</th><th>WR</th><th>RR</th></tr></thead>
        <tbody>{pair_rows(df_raw)}</tbody>
      </table>
    </div>
    <div class="section good">
      <h2>Pair Performance — With Filter</h2>
      <table>
        <thead><tr><th>Pair</th><th>Trades</th><th>WR</th><th>RR</th></tr></thead>
        <tbody>{pair_rows(df_filt)}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Full Trade Log — With D1 Filter</h2>
    <table>
      <thead>
        <tr><th>Time</th><th>Pair</th><th>Direction</th>
            <th>Trade 1</th><th>Trade 2</th><th>RR</th></tr>
      </thead>
      <tbody>{trade_rows(df_filt)}</tbody>
    </table>
  </div>

  <div class="footer">
    Price Trap Backtest · For discussion purposes only
  </div>

</div>
</body>
</html>"""


def main():
    df_raw  = load(CSV_RAW)
    df_filt = load(CSV_FILTERED)
    s_raw   = stats(df_raw)
    s_filt  = stats(df_filt)
    eq_raw  = equity_points(df_raw)
    eq_filt = equity_points(df_filt)
    html    = build_html(df_raw, df_filt, s_raw, s_filt, eq_raw, eq_filt)
    with open(OUT, "w") as f:
        f.write(html)
    print(f"Report saved: {OUT}")
    print("Open in browser → Cmd+P → Save as PDF")


if __name__ == "__main__":
    main()
