import asyncio
import asyncpg
from ingestion.pipeline import DB_CONFIG
from ingestion.goldenset_gen import generate_question

async def main():
    conn = await asyncpg.connect(**DB_CONFIG)
    rows = await conn.fetch(
        "SELECT company, concept, column_label, xbrl_value, exact_match FROM golden_facts ORDER BY id"
    )
    await conn.close()

    for row in rows:
        qa = generate_question(dict(row))
        if qa:
            print(f"\nQ: {qa['question']}")
            print(f"A: {qa['expected_value_display']}  (raw: {qa['expected_value']})")

asyncio.run(main())