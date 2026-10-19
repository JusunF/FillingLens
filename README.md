# FilingLens

FilingLens is an experimental toolkit for exploring how financial information can be extracted and searched in SEC quarterly filings. It combines structured XBRL facts with filing tables and narrative text, with the goal of making company disclosures easier to inspect and evaluate.

## What it does

The project currently has two main workflows:

- **Ingest and reconcile filing facts.** The `ingestion` package can find a company's latest 10-Q through SEC EDGAR, download its primary filing document and company facts, and compare selected quarterly XBRL values with values parsed from filing tables. Candidate matches are checked against the reporting period and plausible value ranges. Results are marked as matched or sent to a review queue.
- **Evaluate narrative search.** `retrieval_eval.py` extracts the Management's Discussion and Analysis (MD&A) section from saved filing HTML, splits it into overlapping text chunks, and ranks those chunks with BM25. It compares raw chunk text with text prefixed by the company name and a short report label, then reports hit@1, hit@3, hit@5, and mean reciprocal rank (MRR) against a small set of phrase-based reference questions.

The repository includes sample filing HTML for Apple, Microsoft, and Amazon, which the retrieval evaluation uses. The ingestion workflow is built around a local PostgreSQL database; `docker-compose.yml` provides a development database service.

## Repository layout

```text
.
├── ingestion/
│   ├── edgar_client.py       # SEC EDGAR requests and filing selection
│   ├── chunker.py            # Filing table parsing and period labels
│   ├── matcher.py            # Match XBRL facts to filing table values
│   ├── narrative_chunker.py  # Extract MD&A and create text chunks
│   ├── goldenset_gen.py      # Generate question records from matched facts
│   └── pipeline.py           # Orchestrate ingestion and database writes
├── retrieval_eval.py         # BM25 retrieval evaluation on sample filings
├── sample_*.html             # Saved example filing documents
└── docker-compose.yml        # Local PostgreSQL service
```

## Getting started

Use Python 3.10 or newer. Install the packages imported by the project:

```bash
python -m pip install asyncpg beautifulsoup4 httpx lxml python-dotenv rank-bm25
```

### Run the retrieval evaluation

From the repository root, run:

```bash
python retrieval_eval.py
```

The script loads the included sample filing files, extracts MD&A chunks, runs the raw and company-prefixed BM25 variants, and prints each question's rank and aggregate retrieval metrics. Its reference checks require the expected phrase to appear in a chunk belonging to the expected company; this is a small development evaluation, not a broad benchmark.

### Run the SEC ingestion workflow

1. Create a `.env` file with an SEC-compliant user agent, for example:

   ```dotenv
   EDGAR_USER_AGENT="FilingLens research contact@example.com"
   ```

   Replace the example contact with your own identifying contact information.

2. Start the local database:

   ```bash
   docker compose up -d postgres
   ```

3. Create the database tables expected by `ingestion/pipeline.py` (`golden_facts` and `review_queue`) before running the pipeline. The repository currently does not include a schema or migration file.

4. Configure PostgreSQL credentials in `ingestion/pipeline.py` if your local database differs from its development defaults.

The ingestion client fetches current SEC submissions, company facts, and filing documents at runtime. The pipeline module contains the ingestion and persistence functions; a command-line entry point and company run list are not currently included.

## Current scope and limitations

- The retrieval evaluation uses three saved filings and a hand-written set of questions with expected phrases.
- Search currently uses BM25 lexical ranking; it does not generate answers or use embeddings.
- The ingestion matcher handles a configured set of XBRL concepts and filing table labels. Unmatched cases are reported for review rather than treated as verified results.
- The ingestion workflow requires SEC network access, a valid `EDGAR_USER_AGENT`, and the PostgreSQL tables described above.
- This is a prototype for development and evaluation, not an audited financial data source.

## GitHub description

**Short description:**

> Experimental toolkit for extracting, reconciling, and searching financial data in SEC 10-Q filings.

**Longer description:**

> FilingLens explores SEC filing analysis by matching selected XBRL facts to reported financial tables and evaluating BM25 retrieval over MD&A text from sample company filings. It includes SEC EDGAR ingestion helpers, filing parsers, a review path for uncertain matches, and a small retrieval evaluation for Apple, Microsoft, and Amazon filings.
