import re
import numpy as np
from rank_bm25 import BM25Okapi
from fastembed import TextEmbedding

from ingestion.narrative_chunker import load_chunks

FILINGS = [
    ("sample_filing.html", "Apple"),
    ("sample_microsoft.html", "Microsoft"),
    ("sample_amazon.html", "Amazon"),
]


def Q(set_, company, q, must):
    return {"set": set_, "company": company, "q": q, "must_contain": must}


# Gold = right company AND a verbatim phrase present in the retrieved chunk.
# "orig" = written after keyword-searching the chunks. "new" = from a random sample.
QUESTIONS = [
    # ---- orig ----
    Q("orig", "Apple", "How much does Apple owe its contract manufacturers in purchase commitments?", "$57.0 billion"),
    Q("orig", "Apple", "How much stock did Apple buy back last quarter?", "$25.8 billion"),
    Q("orig", "Apple", "What is Apple's current quarterly dividend per share?", "$0.27 per share"),
    Q("orig", "Apple", "Why did Apple's research and development spending go up?", "investments in artificial intelligence"),
    Q("orig", "Apple", "Why was Apple's tax rate higher this quarter than a year ago?", "higher effective tax rate on foreign earnings"),
    Q("orig", "Microsoft", "How did Microsoft's stock buybacks change over the nine months?", "$3.8 billion increase in common stock repurchases"),
    Q("orig", "Microsoft", "What drove the rise in Microsoft's operating expenses?", "AI talent, and data"),
    Q("orig", "Microsoft", "What was Microsoft's effective tax rate this quarter?", "effective tax rate was 19% and 18%"),
    Q("orig", "Amazon", "What could cause Amazon's effective tax rate to change?", "Our effective tax rates could be affected by numerous factors"),
    Q("orig", "Amazon", "What ways of raising capital does Amazon say it keeps evaluating?", "We continually evaluate opportunities to sell additional equity or debt securities"),
    Q("orig", "Amazon", "How do US tax rules let Amazon cut taxable income through depreciation?", "enhanced accelerated depreciation deductions"),
    # ---- new (random sample) ----
    Q("new", "Microsoft", "How fast did Microsoft's Azure business grow?", "Azure and other cloud services revenue increased 40%"),
    Q("new", "Microsoft", "What happened to revenue at LinkedIn?", "LinkedIn revenue increased 12%"),
    Q("new", "Microsoft", "What does Microsoft leave out when it reports adjusted net income?", "exclude net gains and losses from investments in OpenAI"),
    Q("new", "Microsoft", "Why did Microsoft's tax rate go up compared with last year?", "changes in the mix of our earnings and tax expenses"),
    Q("new", "Microsoft", "How does Microsoft determine the value of most of its investments?", "A majority of our investments are priced by pricing vendors"),
    Q("new", "Amazon", "How much did currency moves add to Amazon's fulfillment costs over the half year?", "increased fulfillment costs by $523 million"),
    Q("new", "Amazon", "How much cash and marketable securities does Amazon hold?", "$123.0 billion"),
    Q("new", "Amazon", "How much of Amazon's cash is restricted?", "restricted cash, cash equivalents, and marketable securities were $3.3 billion and $2.7 billion"),
    Q("new", "Amazon", "Where does Amazon have to pay income tax?", "subject to income taxes in the U.S. (federal and state) and numerous foreign jurisdictions"),
    Q("new", "Apple", "How did the exchange rate of Japan's currency affect Apple's sales there?", "weakness in the yen relative to the U.S. dollar"),
    Q("new", "Apple", "What drove Apple's sales growth in the Americas?", "higher net sales of iPhone, Services and Mac"),
    Q("new", "Apple", "Which countries did the new import tariffs target, according to Apple?", "China, India, Japan, South Korea, Taiwan, Vietnam"),
    Q("new", "Apple", "Why is Apple's effective tax rate below the US statutory rate?", "lower than the statutory federal income tax rate"),
    Q("new", "Apple", "Does Apple think it has enough cash for the coming year?", "sufficient to satisfy its cash requirements and capital return program"),
    Q("new", "Apple", "Did Apple's Services margin percentage change this quarter?", "Services gross margin percentage was flat"),
]

# Questions the filings cannot answer. These are easy ones; add near-misses later.
UNANSWERABLE = [
    "What did Apple say about its self-driving car program?",
    "What did Microsoft say about its cryptocurrency mining operations?",
    "What did Amazon say about opening a theme park?",
]

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def tokenize(text):
    return re.findall(r"\w+", text.lower())


def norm(text):
    return re.sub(r"\s+", " ", text.lower())


def index_text(chunk, prefixed):
    if prefixed:
        return f"{chunk['company']} quarterly report MD&A. {chunk['text']}"
    return chunk["text"]


def is_gold(chunk, item):
    return chunk["company"] == item["company"] and norm(item["must_contain"]) in norm(chunk["text"])


def check_gold(chunks):
    for item in QUESTIONS:
        if not any(is_gold(c, item) for c in chunks):
            print(f"!! GOLD MISSING: [{item['company']}] {item['must_contain']!r}")


def rank_of_gold(scores, chunks, item):
    order = np.argsort(-np.asarray(scores))
    return next((pos for pos, i in enumerate(order, 1) if is_gold(chunks[i], item)), None)


def wrong_company_top1(scores, chunks, item):
    return chunks[int(np.argmax(scores))]["company"] != item["company"]


def rrf(score_lists, k=60):
    fused = np.zeros(len(score_lists[0]))
    for scores in score_lists:
        order = np.argsort(-np.asarray(scores))
        for pos, i in enumerate(order, 1):
            fused[i] += 1.0 / (k + pos)
    return fused


def summarize(name, ranks, wrong):
    n = len(ranks)
    parts = [f"hit@{k}: {sum(1 for r in ranks if r and r <= k):>2}/{n}" for k in (1, 3, 5)]
    mrr = sum(1 / r for r in ranks if r) / n
    print(f"{name:22s} " + "  ".join(parts) + f"  MRR: {mrr:.3f}  wrong-co@1: {sum(wrong)}/{n}")


def main():
    chunks = []
    for path, company in FILINGS:
        chunks.extend(load_chunks(path, company))
    print(f"{len(chunks)} chunks indexed, {len(QUESTIONS)} questions")
    check_gold(chunks)

    bm25_raw = BM25Okapi([tokenize(index_text(c, False)) for c in chunks])
    bm25_pre = BM25Okapi([tokenize(index_text(c, True)) for c in chunks])

    model = TextEmbedding("BAAI/bge-small-en-v1.5")
    doc_vecs = np.array(list(model.embed([index_text(c, True) for c in chunks])))

    def dense_scores(query):
        return doc_vecs @ np.array(list(model.embed([query])))[0]

    names = ["BM25 raw", "BM25 + company", "Dense", "Dense + instruction", "Hybrid (BM25+Dense)"]
    ranks = {n: [] for n in names}
    wrong = {n: [] for n in names}

    for item in QUESTIONS:
        q = item["q"]
        s_pre = bm25_pre.get_scores(tokenize(q))
        s_dense = dense_scores(q)
        score_sets = [
            bm25_raw.get_scores(tokenize(q)),
            s_pre,
            s_dense,
            dense_scores(BGE_QUERY_PREFIX + q),
            rrf([s_pre, s_dense]),
        ]
        for name, scores in zip(names, score_sets):
            ranks[name].append(rank_of_gold(scores, chunks, item))
            wrong[name].append(wrong_company_top1(scores, chunks, item))

    print("\nper-question rank:  " + "  ".join(f"{n[:9]:>9s}" for n in names))
    for i, item in enumerate(QUESTIONS):
        row = "  ".join(f"{str(ranks[n][i]):>9s}" for n in names)
        print(f"{row}   [{item['set']}/{item['company'][:4]}] {item['q'][:55]}")

    for label, keep in [("ALL", None), ("ORIG (keyword-picked)", "orig"), ("NEW (random sample)", "new")]:
        idx = [i for i, it in enumerate(QUESTIONS) if keep is None or it["set"] == keep]
        print(f"\n=== {label}: {len(idx)} questions ===")
        for name in names:
            summarize(name, [ranks[name][i] for i in idx], [wrong[name][i] for i in idx])

    # --- unanswerable: can a similarity threshold separate them? ---
    ans_top = [dense_scores(it["q"]).max() for it in QUESTIONS]
    una_top = [dense_scores(q).max() for q in UNANSWERABLE]
    print("\n=== top-1 dense similarity: answerable vs unanswerable ===")
    print(f"answerable   min/median/max: {min(ans_top):.3f} / {np.median(ans_top):.3f} / {max(ans_top):.3f}")
    print(f"unanswerable min/median/max: {min(una_top):.3f} / {np.median(una_top):.3f} / {max(una_top):.3f}")
    for q, s in zip(UNANSWERABLE, una_top):
        print(f"  {s:.3f}  {q}")

if __name__ == "__main__":
    main()