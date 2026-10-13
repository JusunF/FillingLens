import os
import httpx
from dotenv import load_dotenv

load_dotenv()

HEADERS = {"User-Agent": os.environ["EDGAR_USER_AGENT"]}

async def get_company_facts(cik:str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"
    async with httpx.AsyncClient(headers=HEADERS) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

async def get_filing_html(cik:str, accession:str, doc_name: str) -> str:
    accession_nodash = accession.replace("-", "")
    cik_nodash = str(int(cik))
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_nodash}/{accession_nodash}/{doc_name}"
    async with httpx.AsyncClient(headers=HEADERS) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text

async def get_filing_index(cik: str, accession: str) -> dict:
    """Fetch the machine-readable index of files in a filing, so you don't
    have to guess the main document's filename."""
    accession_nodash = accession.replace("-", "")
    cik_nodash = str(int(cik))
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_nodash}/{accession_nodash}/index.json"
    async with httpx.AsyncClient(headers=HEADERS) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


def find_main_document(index_json: dict) -> str | None:
    """Pick the primary filing document — the largest .htm file that isn't
    an exhibit. EDGAR's index JSON 'type' field is just a UI icon hint, not
    a real document-type signal, so filename + size heuristics are used
    instead."""
    items = index_json.get("directory", {}).get("item", [])

    candidates = []
    for doc in items:
        name = doc.get("name", "")
        if not name.endswith(".htm"):
            continue
        if "exhibit" in name.lower():
            continue
        try:
            size = int(doc.get("size", 0) or 0)
        except ValueError:
            size = 0
        candidates.append((size, name))

    if not candidates:
        return None

    candidates.sort(reverse=True)  # largest first
    return candidates[0][1]

async def get_recent_10q_accession(cik: str) -> tuple[str, str] | None:
    """Return (accession, period_end) for the most recent 10-Q filing."""
    cik_padded = f"{int(cik):010d}"
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    async with httpx.AsyncClient(headers=HEADERS) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    recent = data["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "10-Q":
            accession = recent["accessionNumber"][i]
            period_end = recent["reportDate"][i]
            return accession, period_end
    return None