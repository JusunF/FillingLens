import numpy as np
from fastembed import TextEmbedding

from ingestion.narrative_chunker import load_chunks
from retrieval_eval import FILINGS, QUESTIONS, index_text, is_gold, rank_of_gold

SIZES = [100, 150, 250, 400]
model = TextEmbedding("BAAI/bge-small-en-v1.5")


def build(size):
    chunks = []
    for path, company in FILINGS:
        chunks.extend(load_chunks(path, company, target_words=size))
    vecs = np.array(list(model.embed([index_text(c, True) for c in chunks])))
    return chunks, vecs


for size in SIZES:
    chunks, vecs = build(size)
    avg_words = sum(len(c["text"].split()) for c in chunks) // len(chunks)
    ranks, split, misses = [], 0, []

    for item in QUESTIONS:
        if not any(is_gold(c, item) for c in chunks):
            split += 1  # gold phrase straddles a chunk boundary at this size
        scores = vecs @ np.array(list(model.embed([item["q"]])))[0]
        r = rank_of_gold(scores, chunks, item)
        ranks.append(r)
        if size == 250 and r != 1:
            top = chunks[int(np.argmax(scores))]
            gold = next((c for c in chunks if is_gold(c, item)), None)
            misses.append((item, r, gold, top))

    n = len(ranks)
    mrr = sum(1 / r for r in ranks if r) / n
    h1 = sum(1 for r in ranks if r == 1)
    h3 = sum(1 for r in ranks if r and r <= 3)
    print(f"target={size:>3}w chunks={len(chunks):>3} avg={avg_words:>3}w "
          f"hit@1={h1}/{n} hit@3={h3}/{n} MRR={mrr:.3f} gold-split={split}")

    for item, r, gold, top in misses:
        print(f"   rank {r} | {item['q'][:60]}")
        print(f"      gold: {gold['chunk_id'] if gold else None} "
              f"({len(gold['text'].split()) if gold else 0}w)")
        print(f"      top1: {top['chunk_id']} {top['text'][:110]!r}")