# fetch_mcp.py
import asyncio, csv, os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from probe import find_price
from classify import classify

load_dotenv()
FAILED = {"belk", "bloomingdales", "wayfair", "sephora"}

async def main():
    urls = [u for u in csv.DictReader(open("urls.csv")) if u["retailer"] in FAILED]
    server = StdioServerParameters(command="npx", args=["-y", "@zenrows/mcp"],
                                   env={"ZENROWS_API_KEY": os.environ["ZENROWS_API_KEY"]})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        for u in urls:
            res = await s.call_tool("scrape", {"url": u["url"], "response_type": "html",
                                               "proxy_country": "US"})
            is_error = getattr(res, "is_error", getattr(res, "isError", False))
            text = res.content[0].text if res.content else ""
            price = find_price(text)
            label, note = classify(None if is_error else 200, text, price, 50_000,
                                   tool_error=is_error)
            print(f'{u["retailer"]:<14}{label:<12}price={price}')

if __name__ == "__main__":
    asyncio.run(main())