"""
report.py — Stage 2 (SQL aggregation) + Stage 3 (HTML -> PDF rendering).

getReportData() turns 200 rows into 4 numbers/lists.
render_report_html() turns those numbers into an HTML page.
render_pdf() asks a headless browser to "print" that page to a PDF file.
"""
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from db import get_conn

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def get_report_data() -> dict:
    """
    Runs the four aggregation queries and returns one dict:
      - total_orders   : COUNT(*)
      - total_revenue  : SUM(amount)
      - top_products   : top 5 products by revenue (GROUP BY product)
      - daily_orders   : orders per day for the last 7 days
      - all_orders     : every order row (for the long table in the PDF)
    """
    conn = get_conn()

    total_orders = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]

    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM orders"
    ).fetchone()["total"]

    # top 5 by revenue, not by order count — a product with fewer, pricier orders can outrank one with more, cheaper orders
    top_products = [
        dict(row)
        for row in conn.execute(
            """
            SELECT product, SUM(amount) AS revenue, COUNT(*) AS order_count
            FROM orders
            GROUP BY product
            ORDER BY revenue DESC
            LIMIT 5
            """
        ).fetchall()
    ]

    seven_days_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    daily_orders = [
        dict(row)
        for row in conn.execute(
            """
            SELECT created_at AS day, COUNT(*) AS order_count
            FROM orders
            WHERE created_at >= ?
            GROUP BY created_at
            ORDER BY created_at ASC
            """,
            (seven_days_ago,),
        ).fetchall()
    ]

    all_orders = [
        dict(row)
        for row in conn.execute(
            "SELECT id, customer, product, amount, created_at FROM orders ORDER BY created_at DESC, id DESC"
        ).fetchall()
    ]

    conn.close()

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "top_products": top_products,
        "daily_orders": daily_orders,
        "all_orders": all_orders,
    }


def render_report_html(data: dict) -> str:
    """Builds the HTML page for the report from the aggregated data."""
    today = datetime.now().strftime("%B %d, %Y")

    top_rows = "".join(
        f"<tr><td>{p['product']}</td><td>{p['order_count']}</td>"
        f"<td>${p['revenue']:.2f}</td></tr>"
        for p in data["top_products"]
    )

    daily_rows = "".join(
        f"<tr><td>{d['day']}</td><td>{d['order_count']}</td></tr>"
        for d in data["daily_orders"]
    )

    all_rows = "".join(
        f"<tr><td>{o['id']}</td><td>{o['customer']}</td><td>{o['product']}</td>"
        f"<td>${o['amount']:.2f}</td><td>{o['created_at']}</td></tr>"
        for o in data["all_orders"]
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{ margin: 24px 32px; }}
    body {{
        font-family: -apple-system, Helvetica, Arial, sans-serif;
        color: #1a1a1a;
        font-size: 12px;
    }}
    h1 {{ font-size: 22px; margin-bottom: 2px; }}
    .subtitle {{ color: #666; margin-top: 0; margin-bottom: 20px; }}
    .totals {{ display: flex; gap: 32px; margin-bottom: 24px; }}
    .total-card {{
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 12px 18px;
    }}
    .total-card .label {{ font-size: 11px; color: #777; text-transform: uppercase; }}
    .total-card .value {{ font-size: 20px; font-weight: 700; }}
    h2 {{ font-size: 15px; margin-top: 28px; margin-bottom: 8px; border-bottom: 2px solid #222; padding-bottom: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
    thead {{ display: table-header-group; }}
    th {{
        text-align: left;
        background: #f2f2f2;
        padding: 6px 8px;
        font-size: 11px;
        text-transform: uppercase;
        color: #555;
    }}
    td {{ padding: 5px 8px; border-bottom: 1px solid #eee; font-size: 11.5px; }}
    tr {{ break-inside: avoid; }}
    .all-orders-table {{ margin-top: 6px; }}
</style>
</head>
<body>
    <h1>Sales Report</h1>
    <p class="subtitle">Generated on {today}</p>

    <div class="totals">
        <div class="total-card">
            <div class="label">Total Orders</div>
            <div class="value">{data['total_orders']}</div>
        </div>
        <div class="total-card">
            <div class="label">Total Revenue</div>
            <div class="value">${data['total_revenue']:.2f}</div>
        </div>
    </div>

    <h2>Top 5 Products by Revenue</h2>
    <table>
        <thead><tr><th>Product</th><th>Orders</th><th>Revenue</th></tr></thead>
        <tbody>{top_rows}</tbody>
    </table>

    <h2>Orders per Day (last 7 days)</h2>
    <table>
        <thead><tr><th>Day</th><th>Orders</th></tr></thead>
        <tbody>{daily_rows}</tbody>
    </table>

    <h2>All Orders ({len(data['all_orders'])})</h2>
    <table class="all-orders-table">
        <thead><tr><th>ID</th><th>Customer</th><th>Product</th><th>Amount</th><th>Date</th></tr></thead>
        <tbody>{all_rows}</tbody>
    </table>
</body>
</html>"""


def render_pdf(html: str, output_path: Path) -> None:
    """Launches headless Chromium, loads the HTML, and prints it to a PDF file."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        page.pdf(path=str(output_path), format="A4", print_background=True)
        browser.close()


if __name__ == "__main__":
    # Manual test for Stage 2 + Stage 3
    data = get_report_data()
    import json

    print(json.dumps(
        {k: v for k, v in data.items() if k != "all_orders"} | {"all_orders_count": len(data["all_orders"])},
        indent=2,
    ))

    html = render_report_html(data)
    test_path = REPORTS_DIR / "test.pdf"
    render_pdf(html, test_path)
    print(f"Wrote {test_path}")
