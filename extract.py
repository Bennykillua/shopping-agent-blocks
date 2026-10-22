# extract.py
import json, pathlib, re
from bs4 import BeautifulSoup
from probe import find_price

PLACEHOLDERS = {0.0, 0.01, 1.0, 999.0, 9999.0, 99999.0}
SALE = re.compile(r'\\?"style\\?"\s*:\s*\\?"SALE')

def extract_offer(html):
    soup = BeautifulSoup(html, "html.parser")
    prices, currency, availability = [], None, None
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if not isinstance(item, dict) or "offers" not in item:
                continue
            offers = item["offers"] if isinstance(item["offers"], list) else [item["offers"]]
            for o in offers:
                if not isinstance(o, dict):
                    continue
                for key in ("price", "lowPrice", "highPrice"):
                    if o.get(key) not in (None, ""):
                        prices.append(float(o[key]))
                currency = currency or o.get("priceCurrency")
                availability = availability or o.get("availability")
    source = "structured data"
    if not prices and (p := find_price(html)):
        prices, source = [float(p)], "embedded app data"
    return {"price": prices[0] if prices else None, "candidates": sorted(set(prices)),
            "currency": currency, "availability": (availability or "").split("/")[-1] or None,
            "sale": bool(SALE.search(html)), "source": source}

def validate(offer, last_price=None, expected_currency="USD"):
    issues = []
    p = offer["price"]
    if p is None:
        return ["no price found"]
    if p in PLACEHOLDERS or p <= 0:
        issues.append(f"placeholder price {p}")
    if offer["currency"] and offer["currency"] != expected_currency:
        issues.append(f"regional price in {offer['currency']}")
    if len(offer["candidates"]) > 1:
        issues.append(f"several prices on page {offer['candidates']}: check the variant")
    if offer["sale"]:
        issues.append("marked as a sale price, not the regular price")
    if last_price and abs(p - last_price) / last_price > 0.3:
        issues.append(f"moved from {last_price} to {p} since last run")
    if offer["availability"] and offer["availability"] != "InStock":
        issues.append(f"item is {offer['availability']}")
    return issues

if __name__ == "__main__":
    history_file = pathlib.Path("runs/price_history.json")
    history = json.loads(history_file.read_text()) if history_file.exists() else {}
    files = sorted(pathlib.Path("runs").glob("fetch_*.html")) + sorted(pathlib.Path("runs").glob("shopbop_plain_*.html"))[:1]
    for f in files:
        retailer = f.stem.replace("fetch_", "").split("_")[0]
        offer = extract_offer(f.read_text(encoding="utf-8"))
        
        issues = validate(offer, history.get(retailer))
        print(f"{retailer:<14}{offer['price']!s:<10}{offer['currency']!s:<5}"
              f"{offer['availability']!s:<12}{offer['source']:<18}{'; '.join(issues) or 'ok'}")
        if offer["price"]:
            history[retailer] = offer["price"]
    history_file.write_text(json.dumps(history, indent=2))