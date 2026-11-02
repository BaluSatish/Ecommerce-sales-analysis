"""
Generate a SYNTHETIC e-commerce transactions dataset (50,000+ rows).

The data is simulated, not from a real retailer. It deliberately contains
missing values, duplicates, outliers and bad entries so the notebook's cleaning
step is meaningful. Nothing here is tuned to hit a particular headline number;
all results in the README come from running the notebook on this file.

Usage: python src/generate_data.py   ->  data/transactions_raw.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
OUT = Path(__file__).resolve().parent.parent / "data" / "transactions_raw.csv"

N_CUSTOMERS = 24_000
N_SKUS = 400
START, END = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")

# --- product catalogue: heavy-tailed popularity & price --------------------------
categories = ["Electronics", "Home & Kitchen", "Fashion", "Beauty", "Sports", "Books", "Toys"]
cat_price = {"Electronics": 90, "Home & Kitchen": 35, "Fashion": 28, "Beauty": 18,
             "Sports": 40, "Books": 12, "Toys": 20}
skus = pd.DataFrame({
    "sku": [f"SKU{i:04d}" for i in range(1, N_SKUS + 1)],
    "category": rng.choice(categories, N_SKUS, p=[.14, .20, .22, .14, .12, .10, .08]),
})
skus["unit_price"] = [round(cat_price[c] * rng.lognormal(0, .5), 2) for c in skus.category]
popularity = rng.pareto(1.3, N_SKUS) + 1          # a few SKUs sell far more than others
skus["p"] = popularity / popularity.sum()

# --- customers: signup date, repeat propensity ------------------------------------
cust = pd.DataFrame({"customer_id": [f"C{i:06d}" for i in range(1, N_CUSTOMERS + 1)]})
days = (END - START).days
cust["first_order"] = START + pd.to_timedelta(
    np.minimum(rng.exponential(220, N_CUSTOMERS), days - 1).astype(int), unit="D")
cust["repeat_p"] = rng.beta(1.2, 3.0, N_CUSTOMERS)  # chance of ordering again each month
cust["country"] = rng.choice(["India", "USA", "UK", "Germany", "UAE"], N_CUSTOMERS,
                             p=[.46, .22, .13, .10, .09])
cust["channel"] = rng.choice(["Organic", "Paid Search", "Social", "Email", "Referral"],
                             N_CUSTOMERS, p=[.30, .26, .22, .12, .10])

# --- orders ---------------------------------------------------------------------
orders = []
oid = 100_000
for c in cust.itertuples():
    d = c.first_order
    while d <= END:
        oid += 1
        orders.append((f"O{oid}", c.customer_id, d, c.country, c.channel))
        # next order: geometric-ish gap; many customers never return
        if rng.random() > c.repeat_p * 0.9:
            break
        d = d + pd.Timedelta(days=int(rng.exponential(55)) + 7)
orders = pd.DataFrame(orders, columns=["order_id", "customer_id", "order_date", "country", "channel"])

# --- order lines -------------------------------------------------------------------
n_lines = rng.choice([1, 1, 1, 2, 2, 3], len(orders))
lines = orders.loc[orders.index.repeat(n_lines)].reset_index(drop=True)
pick = rng.choice(skus.index, len(lines), p=skus.p.values)
lines["sku"] = skus.sku.values[pick]
lines["category"] = skus.category.values[pick]
lines["unit_price"] = skus.unit_price.values[pick]
lines["quantity"] = rng.choice([1, 2, 3, 4], len(lines), p=[.72, .18, .07, .03])
lines["discount_pct"] = rng.choice([0, 0, 0, 5, 10, 15, 20], len(lines))
lines["revenue"] = (lines.unit_price * lines.quantity * (1 - lines.discount_pct / 100)).round(2)
lines["payment_method"] = rng.choice(["Card", "UPI", "COD", "Wallet"], len(lines), p=[.42, .30, .16, .12])
lines["order_status"] = rng.choice(["Delivered", "Returned", "Cancelled"], len(lines), p=[.90, .06, .04])

# --- inject data-quality problems ----------------------------------------------------
n = len(lines)
for col, frac in [("category", .012), ("payment_method", .015), ("discount_pct", .02)]:
    lines.loc[rng.choice(n, int(frac * n), replace=False), col] = np.nan
lines.loc[rng.choice(n, int(.008 * n), replace=False), "quantity"] = -1      # invalid
big = rng.choice(n, int(.002 * n), replace=False)
lines.loc[big, "quantity"] = rng.choice([100, 250, 500], len(big))            # outlier bulk typos
lines.loc[big, "revenue"] = (lines.loc[big, "unit_price"] * lines.loc[big, "quantity"]).round(2)
lines.loc[rng.choice(n, int(.01 * n), replace=False), "country"] = None
lines["order_date"] = lines.order_date.dt.strftime("%Y-%m-%d")
bad = rng.choice(n, int(.006 * n), replace=False)
lines.loc[bad, "order_date"] = pd.to_datetime(lines.loc[bad, "order_date"]).dt.strftime("%d/%m/%Y")  # mixed format
lines = pd.concat([lines, lines.sample(int(.012 * n), random_state=7)], ignore_index=True)  # duplicates
lines = lines.sample(frac=1, random_state=7).reset_index(drop=True)
lines.insert(0, "line_id", range(1, len(lines) + 1))

lines.to_csv(OUT, index=False)
print(f"{len(lines):,} rows | {lines.order_id.nunique():,} orders | "
      f"{lines.customer_id.nunique():,} customers | {lines.sku.nunique()} SKUs -> {OUT}")
