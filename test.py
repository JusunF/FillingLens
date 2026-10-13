import asyncio
import asyncpg
from ingestion.pipeline import DB_CONFIG

async def main():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=== golden_facts ===")
    rows = await conn.fetch("SELECT company, concept, xbrl_value, table_value_scaled, exact_match FROM golden_facts ORDER BY id")
    for r in rows:
        print(dict(r))

    print("\n=== review_queue ===")
    rows = await conn.fetch("SELECT company, concept, status FROM review_queue ORDER BY id")
    for r in rows:
        print(dict(r))

    await conn.close()

asyncio.run(main())