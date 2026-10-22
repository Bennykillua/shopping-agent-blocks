# agent_tool.py
import os, time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx
from curl_cffi import requests as cffi
from dotenv import load_dotenv
from classify import classify
from extract import extract_offer, validate
from probe import find_price

load_dotenv()
MAX_DIRECT, MAX_WAIT = 2, 60
FETCH_SETUPS = [
    {"mode": "auto", "proxy_country": "us"},
    {"js_render": "true", "premium_proxy": "true", "proxy_country": "us", "wait": "5000"},
]
STOP = {
    "policy_block": "Don't retry or route around it. Tell the user and suggest a partner feed.",
    "not_found": "The product page no longer exists. Ask the user for a current link.",
}

def robots_allows(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    try:
        r = cffi.get(base + "/robots.txt", impersonate="chrome", timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None  # an unreadable robots.txt is not a rule
    rp = RobotFileParser(); rp.parse(r.text.splitlines())
    return rp.can_fetch("*", url)

def done(url, label, reason, next_step, attempts, cost_usd, html=None):
    offer = None
    if html is not None:
        offer = extract_offer(html); offer["issues"] = validate(offer)
        if offer["issues"]:
            next_step = "Check the flagged issues before acting on this price."
    return {"ok": label == "success" and not (offer and offer["issues"]), "url": url,
            "label": label, "reason": reason, "next_step": next_step, "offer": offer,
            "attempts": attempts, "cost_usd": round(cost_usd, 5)}

def read_product(url: str) -> dict:
    """Read a public product page. Returns price and availability, or why it couldn't."""
    attempts, cost = [], 0.0
    if robots_allows(url) is False:
        return done(url, "policy_block", "robots.txt disallows this page",
                    STOP["policy_block"], attempts, cost)

    # 1. Direct request with a Chrome fingerprint (free)
    for _ in range(MAX_DIRECT):
        r = cffi.get(url, impersonate="chrome", timeout=30)
        label, note = classify(r.status_code, r.text, find_price(r.text), 50_000,
                               retry_after=r.headers.get("retry-after"))
        attempts.append({"route": "direct", "label": label, "note": note})
        if label == "success":
            return done(url, label, note, "Use the price.", attempts, cost, r.text)
        if label in STOP:
            return done(url, label, note, STOP[label], attempts, cost)
        if label == "rate_limit":
            wait = int(r.headers.get("retry-after") or 30)
            if wait > MAX_WAIT:
                return done(url, label, note, f"Retry after {wait} seconds.", attempts, cost)
            time.sleep(wait)
            continue
        break  # challenge, blocked or empty_data: escalate

    # 2. Fetch, escalating once
    for params in FETCH_SETUPS:
        r = httpx.get("https://api.zenrows.com/v1/", timeout=180,
                      params={"apikey": os.environ["ZENROWS_API_KEY"], "url": url, **params})
        cost += float(r.headers.get("X-Request-Cost") or 0)
        label, note = classify(r.status_code, r.text, find_price(r.text), 50_000)
        attempts.append({"route": "fetch", "label": label, "note": note})
        if label == "success":
            return done(url, label, note, "Use the price.", attempts, cost, r.text)
        if label in STOP:
            return done(url, label, note, STOP[label], attempts, cost)
    return done(url, label, note, "Page unavailable right now. Don't loop; try again later.",
                attempts, cost)

if __name__ == "__main__":
    # Serve read_product to any MCP client over stdio (MCP Python SDK v2)
    from mcp.server.mcpserver import MCPServer
    server = MCPServer("product-reader")
    server.tool()(read_product)
    server.run()