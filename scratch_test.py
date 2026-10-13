import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ingestion.narrative_chunker import extract_narrative_text, extract_mdna, chunk_text

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

with open("sample_filing.html", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "lxml")

chunks = chunk_text(extract_mdna(extract_narrative_text(soup)))

for i in (9, 11, 12, 13):
    print(f"\n=========== CHUNK {i} ===========")
    print(chunks[i])