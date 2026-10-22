# try_tool.py
import csv, json
from agent_tool import read_product

for u in csv.DictReader(open("urls.csv")):
    result = read_product(u["url"])
    print(u["retailer"], json.dumps({k: result[k] for k in
          ("ok", "label", "reason", "next_step", "attempts", "cost_usd")}, indent=2))