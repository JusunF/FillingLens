import re
from ingestion.narrative_chunker import load_chunks

KEYWORDS = ["repurchase", "dividend", "research and development", "effective tax rate"]

for path, company in [("sample_microsoft.html", "Microsoft"), ("sample_amazon.html", "Amazon")]:
    chunks = load_chunks(path, company)
    print(f"\n################ {company} ################")
    for kw in KEYWORDS:
        print(f"\n--- '{kw}' ---")
        shown = 0
        for c in chunks:
            for sent in re.split(r"(?<=[.!?])\s+", c["text"].replace("\n", " ")):
                if kw in sent.lower() and shown < 2:
                    print(f"[{c['chunk_id']}] {sent[:300]}")
                    shown += 1

amazon = load_chunks("sample_amazon.html", "Amazon")
shortest = min(amazon, key=lambda c: len(c["text"].split()))
print("\n--- Amazon shortest chunk ---")
print(shortest["chunk_id"], repr(shortest["text"][:300]))
print("\n--- Amazon last chunk (tail) ---")
print(repr(amazon[-1]["text"][-300:]))