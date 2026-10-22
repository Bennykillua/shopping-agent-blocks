# Why Your AI Shopping Agent Gets Blocked on Retail Sites (and How to Fix It)

A diagnostic for AI shopping agents that fail on retail product pages. It sends real requests, labels why each one failed, finds what triggered the block, and reads the blocked pages with Zenrows Fetch, the Zenrows MCP server and Zenrows Batch.

## Features

- Sends each product URL as a plain HTTP request and through the MCP fetch tool an agent would use, and saves every response
- Classifies each response as success, challenge, rate limit, policy block, not found, blocked or empty data
- Tests the classifier on real saved responses and on edge cases found during testing
- Changes one factor at a time (headers, self-identification, TLS fingerprint, JavaScript, WebDriver flag) to find what triggered a block
- Reads blocked pages with Zenrows Fetch over the API, the CLI and MCP, and reports what each page cost
- Extracts price and availability, and flags placeholder, regional, sale and sudden-change prices
- Wraps everything as one agent tool with a retry budget that stops on policy blocks and missing pages
- Runs the URL list as a Zenrows Batch job and logs block rate per retailer per run

## Prerequisites

- Python 3.10 or above
- Node.js, for the Zenrows CLI and the Zenrows MCP server
- A Zenrows API key. Get one free at [app.zenrows.com/register](https://app.zenrows.com/register)
- A machine with a US IP address, such as a cloud VM or a GitHub Codespace in a US region. Retailers redirect or block traffic from other countries, which would mix location blocks in with the blocks you're testing for

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Bennykillua/shopping-agent-blocks.git
cd shopping-agent-blocks
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the environment

macOS and Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

## Configuration

Create a `.env` file in the project root:

```
ZENROWS_API_KEY=your_api_key
```

Then list the product pages to test in `urls.csv`, one per line. Use public, signed-out product pages only:

```
retailer,url
belk,https://www.belk.com/p/...
shopbop,https://www.shopbop.com/...
```

## Project structure

```
.
├── probe.py            # sends each URL as a plain request and through the MCP fetch tool
├── classify.py         # labels each response
├── test_classify.py    # tests the classifier on saved responses and edge cases
├── triggers.py         # changes one factor at a time to find the block trigger
├── fetch.py            # reads blocked pages with Zenrows Fetch and reports cost
├── fetch_mcp.py        # reads blocked pages through the Zenrows MCP server
├── extract.py          # extracts and validates price and availability
├── agent_tool.py       # the agent tool, also runnable as an MCP server
├── try_tool.py         # runs the agent tool on every URL
├── batch.py            # runs the list as a Zenrows Batch job and logs block rate
├── urls.csv            # the product pages to test
├── .env.example
├── requirements.txt
└── README.md
```

The scripts create a `runs/` folder for saved responses and logs. It's excluded from version control.

## How it works

```
Product URLs (urls.csv)
  ↓
Send each URL as a plain request and through the MCP fetch tool (probe.py)
  ↓
Label each response (classify.py)
  ↓
Change one factor at a time to find the trigger (triggers.py)
  ↓
Read the blocked pages with Zenrows Fetch (fetch.py, fetch_mcp.py)
  ↓
Extract and validate price and availability (extract.py)
  ↓
One agent tool: free route first, Fetch when needed, stop on a policy block (agent_tool.py)
  ↓
Run at scale and log block rate per retailer (batch.py)
```

## Running the project

Run the scripts in this order. Each one builds on the files the previous one saves.

### Diagnose the blocks (free)

```bash
python probe.py
python -m pytest -v
python triggers.py
```

`probe.py` checks your exit IP first and stops if it isn't in the US.

### Read the blocked pages (uses Zenrows credits)

```bash
python fetch.py
python fetch_mcp.py
```

With the CLI:

```bash
npx -y @zenrows/cli login --env
npx -y @zenrows/cli fetch "PRODUCT_URL" --proxy-country us --out page.html --no-signup
```

### Validate the prices (free)

```bash
python extract.py
```

### Run the agent tool

```bash
python try_tool.py
```

To serve the tool to an MCP client over stdio:

```bash
python agent_tool.py
```

### Run at scale

```bash
python batch.py
```

## Output

- `runs/*.html`: every saved response, one file per retailer and route
- `runs/results.jsonl`: status, body length and price for each request from `probe.py`
- `runs/triggers.jsonl`: the label for each retailer and variant from `triggers.py`
- `runs/fetch_*.html`: the pages Zenrows Fetch returned
- `runs/price_history.json`: the last accepted price per retailer, used to catch sudden changes
- `runs/block_rate.csv`: one row per retailer per Batch run, with the date, job ID and block rate

Each script also prints a summary table to the terminal: the label per response, the credits each Fetch request used, the issues flagged on each price, or the block rate per retailer.

## Technologies

- Python
- Zenrows (Fetch, MCP server, CLI and Batch)
- MCP Python SDK
- httpx
- curl_cffi
- Playwright
- Beautiful Soup
- pytest

## Troubleshooting

- **The script stops with "Run this from a US IP".** Your exit IP isn't in the US. Run the project from a US cloud machine.
- **`No module named 'mcp.server.fastmcp'`.** Version 2 of the MCP Python SDK renamed `FastMCP` to `MCPServer`. Install the versions in `requirements.txt`.
- **A page loads in your browser but the classifier says `empty_data`.** The price is probably in markup `find_price` doesn't read yet. Search the saved page for the price and add a pattern for it.
- **A product page returns `not_found`.** The product was removed. Replace the URL in `urls.csv`.

## Related article

This repository accompanies the Zenrows article:

[Why Your AI Shopping Agent Gets Blocked on Retail Sites (and How to Fix It)]()