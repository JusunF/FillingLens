import re
from bs4 import BeautifulSoup  

def extract_narrative_text(soup: BeautifulSoup) -> str:
    """Full filling text with tables removed, one block element per line."""
    for table in soup.find_all("table"):
        table.decompose()
    text = soup.get_text(separator="\n")
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)

def extract_mdna(full_text:str) -> str | None:
    """Return the text of Item 2 (MD&A). Picks the occurrence with the most
    text before the next 'Item 3', which skips the table-of-contents entry."""
    start_pattern = re.compile(r"Item\s*2\.?\s*Management.{0,3}s Discussion and Analysis", re.IGNORECASE)
    end_pattern = re.compile(r"Item\s*3\.?\s*Quantitative and Qualitative", re.IGNORECASE)

    best = None
    for m in start_pattern.finditer(full_text):
        end = end_pattern.search(full_text, m.end())
        end_idx = end.start() if end else len(full_text)
        section = full_text[m.start():end_idx]
        if best is None or len(section) > len(best):
            best = section
    return section

def chunk_text(section: str, target_words: int = 250, overlap_paragraphs: int = 1) -> list[str]:
    """Group paragraphs (lines) into -target_words chunks. The last
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