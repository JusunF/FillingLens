import re
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


def is_numeric_cell(text: str) -> bool:
    """True for cells like '$', '1,234', '(171)', '12.5%', '—'."""
    stripped = re.sub(r"[\s$(),%.\-\u2013\u2014]", "", text)
    return stripped == "" or stripped.isdigit()


def is_data_table(table) -> bool:
    """True if the table looks like financial data (many numeric cells).
    Heading/layout tables have almost no numeric cells."""
    cells = [c.get_text(strip=True) for c in table.find_all(["td", "th"])]
    cells = [c for c in cells if c]
    if not cells:
        return False
    numeric = sum(1 for c in cells if is_numeric_cell(c))
    return numeric >= 4 and numeric / len(cells) >= 0.3


def extract_narrative_text(soup: BeautifulSoup) -> str:
    """Full filing text. Numeric data tables are removed (the matcher covers
    them); text-only tables (headings, layout) are kept by unwrapping."""
    for table in reversed(soup.find_all("table")):
        if is_data_table(table):
            table.decompose()
        else:
            table.unwrap()
    text = soup.get_text(separator="\n")
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def extract_mdna(full_text: str) -> str | None:
    """Return the text of Item 2 (MD&A). Picks the candidate with the most
    text before the next 'Item 3' / 'Item 4', which skips the table-of-contents
    entry. End patterns use only the first word of the heading because some
    filings (small-caps formatting) split later words across elements."""
    start_pattern = re.compile(
        r"Item\s*2\.?\s*Management.{0,3}s\s+Discussion\s+and\s+Analysis", re.IGNORECASE
    )
    end_pattern = re.compile(
        r"Item\s*3\.?\s*Quantitative|Item\s*4\.?\s*Controls", re.IGNORECASE
    )

    best = None
    for m in start_pattern.finditer(full_text):
        end = end_pattern.search(full_text, m.end())
        if not end:
            continue  # no end marker: skip rather than swallow the rest of the filing
        section = full_text[m.start():end.start()]
        if best is None or len(section) > len(best):
            best = section
    return best


def chunk_text(section: str, target_words: int = 250, overlap_paragraphs: int = 1) -> list[str]:
    """Group paragraphs (lines) into ~target_words chunks. The last
    `overlap_paragraphs` paragraphs repeat at the start of the next chunk so
    an answer that straddles a boundary isn't cut in half."""
    paragraphs = section.split("\n")
    chunks, current, count = [], [], 0

    for para in paragraphs:
        words = len(para.split())
        if current and count + words > target_words:
            chunks.append("\n".join(current))
            current = current[-overlap_paragraphs:] if overlap_paragraphs else []
            count = sum(len(p.split()) for p in current)
        current.append(para)
        count += words

    if current:
        chunks.append("\n".join(current))
    return chunks


def load_chunks(html_path: str, company: str) -> list[dict]:
    """Parse one saved filing into chunk records tagged with company."""
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    mdna = extract_mdna(extract_narrative_text(soup))
    if not mdna:
        return []
    return [
        {"company": company, "chunk_id": f"{company}-{i}", "text": c}
        for i, c in enumerate(chunk_text(mdna))
    ]