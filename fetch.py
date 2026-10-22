# fetch.py
import csv, os, pathlib, time
import httpx
from dotenv import load_dotenv
from probe import find_price
from classify import classify

load_dotenv()
KEY = os.environ["ZENROWS_API_KEY"]
FAILED = {"belk", "bloomingdales", "wayfair", "sephora"}  # failed both routes in the test
OUT = pathlib.Path("runs"); OUT.mkdir(exist_ok=True)

# Auto mode first; escalate once if the page comes back without a price
SETUPS = [
    {"mode": "auto", "proxy_country": "us"},
    {"js_render": "true", "premium_proxy": "true", "proxy_country": "us", "wait": "5000"},
]
BILLED = {200, 404, 410}  # Zenrows bills these, even when the page has no price

def credits_used():
    r = httpx.get("https://api.zenrows.com/v1/subscriptions/self/details",
                  headers={"X-API-Key": KEY}, timeout=30)
    return r.json().get("usage_credits")

start = credits_used()
results, billed_usd = [], 0.0
for u in csv.DictReader(open("urls.csv")):
    if u["retailer"] not in FAILED:
        continue
    spent = 0.0
    for params in SETUPS:
        r = httpx.get("https://api.zenrows.com/v1/", timeout=180,
                      params={"apikey": KEY, "url": u["url"], **params})
        if r.status_code in BILLED:
            spent += float(r.headers.get("X-Request-Cost") or 0)
        price = find_price(r.text)
        label, note = classify(r.status_code, r.text, price, 50_000)
        if label == "success":
            break
    (OUT / f'fetch_{u["retailer"]}.html').write_text(r.text, encoding="utf-8")
    billed_usd += spent
    results.append((u["retailer"], r.status_code, label, price, spent))

time.sleep(15)  # the usage counter lags; wait before the final reading
total_credits = credits_used() - start
per_credit = billed_usd / total_credits if total_credits else None

for retailer, status, label, price, spent in results:
    credits = round(spent / per_credit) if per_credit else "?"
    print(f"{retailer:<14}{status:<6}{label:<12}price={price!s:<10}credits={credits}")
print(f"Total: {total_credits} credits")