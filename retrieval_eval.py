import re
from rank_bm25 import BM25Okapi
from ingestion.narrative_chunker import load_chunks

FILINGS = [
    ("sample_filing.html", "Apple"),
    ("sample_microsoft.html", "Microsoft"),
    ("sample_amazon.html", "Amazon"),
]

# Gold = right company AND a verbatim phrase present in the retrieved chunk.
QUESTIONS = [
    # Apple
    {"company": "Apple", "q": "How much does Apple owe its contract manufacturers in purchase commitments?",
     "must_contain": "$57.0 billion"},
    {"company": "Apple", "q": "How much stock did Apple buy back last quarter?",
     "must_contain": "$25.8 billion"},
    {"company": "Apple", "q": "What is Apple's current quarterly dividend per share?",
     "must_contain": "$0.27 per share"},
    {"company": "Apple", "q": "Why did Apple's research and development spending go up?",
     "must_contain": "investments in artificial intelligence"},
    {"company": "Apple", "q": "Why was Apple's tax rate higher this quarter than a year ago?",
     "must_contain": "higher effective tax rate on foreign earnings"},
    # Microsoft
    {"company": "Microsoft", "q": "How did Microsoft's stock buybacks change over the nine months?",
     "must_contain": "$3.8 billion increase in common stock repurchases"},
    {"company": "Microsoft", "q": "What drove the rise in Microsoft's operating expenses?",
     "must_contain": "AI talent, and data"},
    {"company": "Microsoft", "q": "What was Microsoft's effective tax rate this quarter?",
     "must_contain": "effective tax rate was 19% and 18%"},
    # Amazon
    {"company": "Amazon", "q": "What could cause Amazon's effective tax rate to change?",
     "must_contain": "Our effective tax rates could be affected by numerous factors"},
    {"company": "Amazon", "q": "What ways of raising capital does Amazon say it keeps evaluating?",
     "must_contain": "We continually evaluate opportunities to sell additional equity or debt securities"},
    {"company": "Amazon", "q": "How do US tax rules let Amazon cut taxable income through depreciation?",
     "must_contain": "enhanced accelerated depreciation deductions"},
]


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def index_text(chunk: dict, prefixed: bool) -> str:
    if prefixed:
        return f"{chunk['company']} quarterly report MD&A. {chunk['text']}"
    return chunk["text"]


def is_gold(chunk: dict, item: dict) -> bool:
    return chunk["company"] == item["company"] and norm(item["must_contain"]) in norm(chunk["text"])


def check_gold(chunks: list[dict]) -> None:
    """Every gold phrase must exist in its company's chunks, or the question is broken."""
    for item in QUESTIONS:
        if not any(is_gold(c, item) for c in chunks):
            print(f"!! GOLD MISSING: [{item['company']}] {item['must_contain']!r}")


def evaluate(chunks: list[dict], prefixed: bool) -> list[int | None]:
    bm25 = BM25Okapi([tokenize(index_text(c, prefixed)) for c in chunks])
    ranks = []
    for item in QUESTIONS:
        scores = bm25.get_scores(tokenize(item["q"]))
        order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
        rank = next((pos for pos, i in enumerate(order, 1) if is_gold(chunks[i], item)), None)
        ranks.append(rank)
    return ranks


def summarize(name: str, ranks: list[int | None]) -> None:
    n = len(ranks)
    parts = [f"hit@{k}: {sum(1 for r in ranks if r and r <= k)}/{n}" for k in (1, 3, 5)]
    mrr = sum(1 / r for r in ranks if r) / n
    print(f"{name:18s} " + "  ".join(parts) + f"  MRR: {mrr:.3f}")


def main():
    chunks = []
    for path, company in FILINGS:
        chunks.extend(load_chunks(path, company))
    print(f"{len(chunks)} chunks indexed\n")
    check_gold(chunks)

    raw = evaluate(chunks, prefixed=False)
    pre = evaluate(chunks, prefixed=True)

    print(f"{'rank (raw / prefixed)':24s} question")
    for item, r1, r2 in zip(QUESTIONS, raw, pre):
        print(f"{str(r1):>5s} / {str(r2):<14s}   [{item['company']}] {item['q']}")

    print()
    summarize("BM25 raw", raw)
    summarize("BM25 + company", pre)


main()