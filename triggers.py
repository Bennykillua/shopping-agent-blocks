# triggers.py
import asyncio, csv, json
import httpx
from curl_cffi import requests as cffi
from playwright.async_api import async_playwright
from probe import find_price, check_exit_ip, OUT
from classify import classify

AGENT_UA = "ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)"

def chrome_headers(ua):
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    }

def http_get(url, headers):
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    return r.status_code, r.text

def tls_get(url):
    r = cffi.get(url, impersonate="chrome", timeout=30)
    return r.status_code, r.text

async def browser_get(pw, url, hide_webdriver):
    args = ["--disable-blink-features=AutomationControlled"] if hide_webdriver else []
    browser = await pw.chromium.launch(headless=True, args=args)
    page = await browser.new_page()
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(5_000)  # give challenge scripts time to run
    body = await page.content()
    await browser.close()
    return (resp.status if resp else None), body

async def main():
    check_exit_ip()
    urls = list(csv.DictReader(open("urls.csv")))
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); major = b.version.split(".")[0]; await b.close()
        chrome_ua = (f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")
        variants = {
            "baseline": lambda u: asyncio.to_thread(http_get, u, {}),
            "browser_headers": lambda u: asyncio.to_thread(http_get, u, chrome_headers(chrome_ua)),
            "agent_ua": lambda u: asyncio.to_thread(http_get, u, chrome_headers(AGENT_UA)),
            "browser_tls": lambda u: asyncio.to_thread(tls_get, u),
            "headless_js": lambda u: browser_get(pw, u, False),
            "headless_js_no_webdriver": lambda u: browser_get(pw, u, True),
        }
        # Variants in the outer loop, so each retailer sees one request every ~50 seconds
        for name, run in variants.items():
            for u in urls:
                try:
                    status, body = await run(u["url"])
                except Exception as e:
                    status, body = None, f"error: {e}"
                price = find_price(body)
                label, note = classify(status, body, price, 50_000)
                print(f'{u["retailer"]:<14}{name:<26}{str(status):<6}{label:<12}{note}')
                with open(OUT / "triggers.jsonl", "a") as f:
                    f.write(json.dumps(dict(retailer=u["retailer"], variant=name, status=status,
                                            body_len=len(body), price=price, label=label)) + "\n")
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())