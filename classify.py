# classify.py
CHALLENGE = ["captcha", "verify you are human", "press & hold", "px-captcha", "cf-chl",
             "enter the characters you see below"]
POLICY = ["unauthorized ai agent", "unauthorized agent"]

def classify(status, body, price, baseline_len, retry_after=None, tool_error=False):
    text = body.lower()
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
    if status is None or status >= 400:
        return "blocked", f"status={status}, cause unknown"
    if len(body) < 0.2 * baseline_len:
        return "empty_data", "shell page, likely needs JavaScript"
    return "empty_data", "full page, price missing"