import random
from ingestion.narrative_chunker import load_chunks

FILINGS = [
    ("sample_filing.html", "Apple"),
    ("sample_microsoft.html", "Microsoft"),
    ("sample_amazon.html", "Amazon"),
]

chunks = []
for path, company in FILINGS:
    chunks.extend(load_chunks(path, company))

random.seed(7)  # fixed seed so you get the same sample every run
for c in random.sample(chunks, 15):
    text = c["text"].replace("\n", " ")
    print(f"\n[{c['chunk_id']}] {text[:450]}")