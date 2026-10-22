# batch.py
import collections, csv, datetime, os, time
import httpx
from dotenv import load_dotenv
from probe import find_price
from classify import classify

load_dotenv()
API = "https://async.api.zenrows.com/v1"
H = {"X-API-Key": os.environ["ZENROWS_API_KEY"], "Content-Type": "application/json"}

# Per-retailer settings learned from the Fetch test; everything else uses auto mode
OVERRIDES = {"belk": {"js_render": "true", "premium_proxy": "true", "wait": "5000"}}

tasks = [{"url": u["url"], "external_id": f'{u["retailer"]}-{i}',
          "zenrows_params": OVERRIDES.get(u["retailer"], {"mode": "auto"})}
         for i, u in enumerate(csv.DictReader(open("urls.csv")))]
job = httpx.post(f"{API}/jobs", headers=H, json={
    "type": "regular", "status": "closed",
    "zenrows_params": {"proxy_country": "us"},
    "tasks": tasks,
}).json()
job_id = job["job_id"]

delay = 2
while True:
    run = httpx.get(f"{API}/jobs/{job_id}", headers=H).json()["latest_run"]
    if run["status"] in {"completed", "failed", "stopped"}:
        break
    time.sleep(delay); delay = min(delay * 1.5, 15)

rows = httpx.get(f"{API}/jobs/{job_id}/results", headers=H, params={"status": "all"}).json()["results"]
seen, blocked = collections.Counter(), collections.Counter()
for row in rows:
    retailer = row["external_id"].rsplit("-", 1)[0]
    seen[retailer] += 1
    if not row.get("result_url"):
        blocked[retailer] += 1
        continue
    body = httpx.get(row["result_url"]).text
    if classify(200, body, find_price(body), 50_000)[0] != "success":
        blocked[retailer] += 1

today = datetime.date.today().isoformat()
with open("runs/block_rate.csv", "a") as f:
    for r in sorted(seen):
        f.write(f"{today},{job_id},{r},{seen[r]},{blocked[r]},{blocked[r] / seen[r]:.0%}\n")
        print(f"{r:<14}{blocked[r]}/{seen[r]} blocked")
print(run["stats"])