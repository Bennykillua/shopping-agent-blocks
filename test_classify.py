# test_classify.py
import json, statistics
from classify import classify

# Answer key: what each retailer actually sent back, checked by opening the saved file.
# MCP rows only contain the tool's error text, not the page, so the label is the
# best the classifier can do from what the agent receives.
EXPECTED = {
    ("shopbop", "plain"): "success",
    ("shopbop", "mcp"): "success",
    ("belk", "plain"): "challenge",          # PerimeterX px-captcha page, status 403
    ("belk", "mcp"): "blocked",              # tool returned only "status code 403"
    ("bloomingdales", "plain"): "blocked",   # "Access Denied 403" page, nothing to solve
    ("bloomingdales", "mcp"): "blocked",     # robots.txt itself was refused
    ("wayfair", "plain"): "challenge",       # PerimeterX px-captcha page, status 429
    ("wayfair", "mcp"): "rate_limit",        # tool returned only "status code 429"
    ("sephora", "plain"): "blocked",         # Akamai "Access Denied" page
    ("sephora", "mcp"): "blocked",           # robots.txt itself was refused
}

def test_real_pages():
    rows = [json.loads(line) for line in open("runs/results.jsonl")]
    sizes = [r["body_len"] for r in rows if r["status"] == 200 and r["price"]]
    baseline = statistics.median(sizes) if sizes else 50_000
    for r in rows:
        body = open(r["file"], encoding="utf-8").read()
        label, note = classify(r["status"], body, r["price"], baseline,
                               retry_after=r.get("retry_after"),
                               tool_error=r.get("tool_error", False))
        assert label == EXPECTED[(r["retailer"], r["route"])], f'{r["retailer"]} {r["route"]}: {note}'

def test_captcha_script_on_good_page():
    body = '<script src="recaptcha.js"></script><meta itemprop="price" content="19.99">'
    assert classify(200, body, "19.99", 100)[0] == "success"

def test_bare_403_is_not_policy():
    assert classify(403, "Forbidden", None, 50_000)[0] == "blocked"

def test_retry_after_on_403_is_not_rate_limit():
    assert classify(403, "Forbidden", None, 50_000, retry_after="0")[0] == "blocked"

def test_refused_robots_txt_is_not_policy():
    msg = ("When fetching robots.txt (https://www.sephora.com/robots.txt), received status 403 "
           "so assuming that autonomous fetching is not allowed")
    assert classify(None, msg, None, 50_000, tool_error=True)[0] == "blocked"

def test_plain_404_is_not_found():
    assert classify(404, "<h1>Page not found</h1>", None, 50_000)[0] == "not_found"