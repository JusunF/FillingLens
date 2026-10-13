import re
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from rank_bm25 import BM25Okapi

from ingestion.narrative_chunker import extract_narrative_text, extract_mdna, chunk_text

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Gold = a verbatim phrase that must appear in a retrieved chunk
# Survives re-chunking, unlike hardcoded chunk indices
QUESTIONS = [
    {"q": "How much does Apple owe its contract manufacturers in purchase commitments?",
     "must_contain": "$57.0 billion"},
    {"q": "How much stock did Apple but back last quarter?",
     "must_contain": "$25.8 billion"},
    {"q": "What is the current quarterly dividend per share?",
     "must_contain": "$0.27 per share"},
    {"q": "Why did research and development spending go up?",
     "must_contain": "investments in artificial intelligence"},
    {"q": "Why was the tax rate higher this quarter than a year ago?",
     "must_contain": "higher effective tax rate on foreign earnings"},
]

K_VALUES = (1,3,5)

def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())

def first_hit_rank(ranked_chunks: list[str], phrase: str) -> int | None:
    """1-based rank of the first chunk containing the phrase, else None."""
    p = norm(phrase)
    for i, chunk in enumerate(ranked_chunks, start=1):
        if p in norm(chunk):
            return i
    return None

def main():
    with open("sample_filing.html", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    chunks = chunk_text(extract_mdna(extract_narrative_text(soup)))
    print(f"{len(chunks)} chunks indexed\n")

    bm25 = BM25Okapi([tokenize(c) for c in chunks])

    ranks = []
    for item in QUESTIONS:
        scores = bm25.get_scores(tokenize(item["q"]))
        order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
        ranked = [chunks[i] for i in order]
        rank = first_hit_rank(ranked, item["must_contain"])
        ranks.append(rank)
        print(f"rank={rank} | {item['q']}")

    print()
    for k in K_VALUES:
        hits = sum(1 for r in ranks if r is not None and r <= k)
        print(f"hit@{k}: {hits}/{len(ranks)}")
    mrr = sum(1 / r for r in ranks if r) / len(ranks)
    print(f"MRR: {mrr:.3f}")

main()