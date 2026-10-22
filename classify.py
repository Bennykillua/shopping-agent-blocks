# classify.py

# Text that only appears on challenge pages
CHALLENGE = ["access to this page has been denied", "verify you are human", "press & hold",
             "cf-chl", "enter the characters you see below", "captcha"]
# Challenge pages in the test were under 10 KB and full product pages over 1 MB,
# so 100 KB leaves room on both sides
CHALLENGE_PAGE_MAX = 100_000  
POLICY = ["unauthorized ai agent", "unauthorized agent"]

def classify(status, body, price, baseline_len, retry_after=None, tool_error=False):
    text = body.lower()
    # Full product pages load anti-bot scripts that contain challenge text,
    # so a marker only counts on a page small enough to be a challenge page
    hit = None
    if len(body) < CHALLENGE_PAGE_MAX:
        hit = next((m for m in CHALLENGE if m in text), None)

    if status == 429 or (status == 503 and retry_after):
        if hit:
            return "challenge", f"status={status} with marker={hit}"
        return "rate_limit", f"status={status}, retry_after={retry_after}"
    if tool_error and "robots.txt" in text:
        # The tool could not read robots.txt: that is a block, not a rule
        if "received status" in text:
            return "blocked", "robots.txt itself was refused"
        return "policy_block", "robots.txt disallows this agent"
    if any(m in text for m in POLICY):
        return "policy_block", "page names unauthorized agents"
    if status == 200 and price:
        return "success", f"price={price}"
    if hit:
        return "challenge", f"marker={hit}"
    if status in (404, 410):
        return "not_found", f"status={status}: page doesn't exist, don't retry"
    if status is None or status >= 400:
        return "blocked", f"status={status}, cause unknown"
    if len(body) < 0.2 * baseline_len:
        return "empty_data", "shell page, likely needs JavaScript"
    return "empty_data", "full page, price missing"
