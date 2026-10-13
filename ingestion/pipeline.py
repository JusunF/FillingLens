import warnings
import asyncpg
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

import asyncio
import asyncpg

from ingestion.edgar_client import (
    get_company_facts,
    get_filing_index,
    find_main_document,
    get_filing_html,
    get_recent_10q_accession,
)
from ingestion.matcher import match_facts_for_filing

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

CONCEPT_ROW_MAP = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": ["Total net sales", "Total revenue", "Total revenues"],
    "NetIncomeLoss": ["Net income"],
    "EarningsPerShareDiluted": ["Diluted earnings per share", "Diluted"],
    "OperatingIncomeLoss": ["Operating income"],
}

DB_CONFIG = dict(
    user="postgres", password="devpass", database="filinglens",
    host="localhost", port=5432
)


async def store_results(pool: asyncpg.Pool, results: list[dict]):
    """Route each result to golden_facts (if matched) or review_queue
    (everything else) — nothing gets silently dropped."""
    async with pool.acquire() as conn:
        for r in results:
            if r.get("status") == "matched":
                await conn.execute(
                    """
                    INSERT INTO golden_facts
                        (company, cik, accession, concept, column_label,
                         xbrl_value, table_value_scaled, relative_error, exact_match)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (company, accession, concept, column_label) DO NOTHING
                    """,
                    r["company"], r["cik"], r["accession"], r["concept"],
                    r.get("column_label"), r.get("xbrl_value"),
                    r.get("table_value_scaled"), r.get("relative_error"),
                    r.get("exact_match"),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO review_queue
                        (company, cik, accession, concept, status, xbrl_value)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    r.get("company"), r.get("cik"), r.get("accession"),
                    r["concept"], r["status"], r.get("xbrl_value"),
                )


async def process_company(cik: str, name: str) -> list[dict]:
    accession_info = await get_recent_10q_accession(cik)
    if not accession_info:
        return [{"company": name, "cik": cik, "concept": "N/A", "status": "no_10q_found"}]

    accession, period_end = accession_info

    index = await get_filing_index(cik, accession)
    doc_name = find_main_document(index)
    if not doc_name:
        return [{"company": name, "cik": cik, "accession": accession, "concept": "N/A", "status": "no_main_doc_found"}]

    html = await get_filing_html(cik, accession, doc_name)
    soup = BeautifulSoup(html, "lxml")

    facts = await get_company_facts(cik)

    results = match_facts_for_filing(
        soup=soup,
        company_facts=facts,
        accession=accession,
        period_end=period_end,
        concept_row_map=CONCEPT_ROW_MAP,
    )

    for r in results:
        r["company"] = name
        r["cik"] = cik
        r["accession"] = accession

    return results
