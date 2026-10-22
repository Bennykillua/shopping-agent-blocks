# probe.py
import asyncio, csv, json, pathlib, re
import httpx
from bs4 import BeautifulSoup
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

OUT = pathlib.Path("runs"); OUT.mkdir(exist_ok=True)

def check_exit_ip():
    ip = httpx.get("https://ipinfo.io/json", timeout=10).json()
    print(f"Exit IP: {ip.get('ip')} ({ip.get('country')}, {ip.get('org')})")
    if ip.get("country") != "US":
        raise SystemExit("Run this from a US IP. See Prerequisites.")
    return {"exit_country": ip.get("country"), "exit_org": ip.get("org")}

FIXED_PRICE = re.compile(r'FixedPrice.{0,80}?amount\\?"\s*:\s*\\?"(\d{1,6}(?:\.\d{2})?)')
PRICE_IN_JSON = re.compile(
    r'\\?"(?:price|salePrice|currentPrice|finalPrice)\\?"\s*:\s*\\?"?\$?(\d{1,6}(?:\.\d{2})?)'
)

def find_price(html):
    soup = BeautifulSoup(html, "html.parser")
    # 1. Structured product data (JSON-LD)
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            offers = item.get("offers") if isinstance(item, dict) else None
            offers = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offers, dict) and offers.get("price"):
                return str(offers["price"])
    # 2. Price meta tags
    meta = (soup.find("meta", attrs={"itemprop": "price"})
            or soup.find("meta", attrs={"property": "product:price:amount"}))
    if meta and meta.get("content"):
        return meta["content"]
    # 3. Embedded app data: a fixed price object (Wayfair), then common price keys
    for pattern in (FIXED_PRICE, PRICE_IN_JSON):
        m = pattern.search(html)
        if m:
            return m.group(1)
    return None

def log(retailer, url, route, status, body, **extra):
    path = OUT / f"{retailer}_{route}_{abs(hash(url)) % 10**6}.html"
    path.write_text(body, encoding="utf-8")
    row = dict(retailer=retailer, route=route, status=status, body_len=len(body),
               price=find_price(body), file=str(path), **extra)
    print(row)
    with open(OUT / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")

async def main():
    origin = check_exit_ip()
    urls = list(csv.DictReader(open("urls.csv")))  # columns: retailer,url

    # Route 1: plain HTTP request, default httpx settings
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        for u in urls:
            r = await client.get(u["url"])
            log(u["retailer"], u["url"], "plain", r.status_code, r.text,
                retry_after=r.headers.get("retry-after"), **origin)
            await asyncio.sleep(10)

    # Route 2: the MCP fetch tool an agent would call
    server = StdioServerParameters(command="uvx", args=["mcp-server-fetch"])
    async with stdio_client(server) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        for u in urls:
            res = await s.call_tool("fetch", {"url": u["url"], "raw": True, "max_length": 999_999})
            is_error = getattr(res, "is_error", getattr(res, "isError", False))
            text = res.content[0].text if res.content else ""
            m = re.search(r"status code (\d{3})", text)
            status = int(m.group(1)) if m else (None if is_error else 200)
            log(u["retailer"], u["url"], "mcp", status, text,
                tool_error=is_error, **origin)
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())