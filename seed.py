"""
seed.py — Stage 1: fill report.db with ~200 fake but realistic orders.

Safe to run twice: it deletes all rows before inserting, so the row
count never doubles no matter how many times you run it.

Usage:
    python3 seed.py
"""
import random
from datetime import datetime, timedelta

from db import get_conn, init_db

PRODUCTS = ["Widget", "Gadget", "Doohickey", "Thingamajig", "Gizmo", "Contraption"]
CUSTOMERS = [
    "Alice Nguyen", "Bilal Khan", "Carmen Diaz", "David Osei", "Elena Popescu",
    "Farhan Ali", "Grace Kim", "Hassan Malik", "Ines Costa", "Jamal Carter",
    "Keiko Sato", "Liam O'Brien", "Mei Chen", "Noor Ahmed", "Omar Haddad",
    "Priya Sharma", "Quentin Roy", "Rania Saleh", "Sofia Rossi", "Tariq Jabbar",
]

N_ORDERS = 200


def seed():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # Delete first — running this script twice must leave exactly one clean copy.
    cur.execute("DELETE FROM orders")

    now = datetime.now()
    rows = []
    for _ in range(N_ORDERS):
        customer = random.choice(CUSTOMERS)
        product = random.choice(PRODUCTS)
        amount = round(random.uniform(5, 200), 2)
        days_ago = random.randint(0, 29)
        created_at = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        rows.append((customer, product, amount, created_at))

    cur.executemany(
        "INSERT INTO orders (customer, product, amount, created_at) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()

    count = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    print(f"Seeded {count} orders into report.db")


if __name__ == "__main__":
    seed()
