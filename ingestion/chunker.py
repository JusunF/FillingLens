from bs4 import BeautifulSoup
from datetime import date
import re

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def extract_table_grid(table_tag) -> list[list[str]]:
    grid = []
    for row in table_tag.find_all("tr"):
        cells = []
        for cell in row.find_all(["td", "th"]):
            text = cell.get_text(strip=True)
            colspan = int(cell.get("colspan", 1))
            cells.append(text)
            cells.extend([""] * (colspan - 1))
        grid.append(cells)
    return grid


def clean_row(row: list[str]) -> list[str]:
    return [c for c in row if c and c not in ("$", "(", ")")]


def merge_headers(period_row: list[str], date_row: list[str]) -> list[str]:
    """Combine a 'Three/Nine Months Ended' row with a date row into flat
    column labels. Filters the period row down to cells that actually look
    like period phrases first, since units disclaimers or other stray text
    sometimes leak into this row."""
    real_periods = [p for p in period_row if "Ended" in p or "Months" in p or "Year" in p]
    if not real_periods:
        real_periods = period_row  # fallback: use as-is if nothing matched

    labels = []
    dates_per_period = len(date_row) // len(real_periods)
    if dates_per_period == 0:
        raise ZeroDivisionError("no usable period columns")
    for i, period in enumerate(real_periods):
        for j in range(dates_per_period):
            idx = i * dates_per_period + j
            if idx < len(date_row):
                labels.append(f"{period} {date_row[idx]}")
    return labels


def parse_column_end_date(label: str) -> date | None:
    """Extract the period END date from a column label. Handles variations
    like missing spaces ('EndedMarch 31,') by matching month names directly
    rather than relying on whitespace structure."""
    month_pattern = "|".join(MONTHS.keys())
    match = re.search(rf"({month_pattern})\.?\s*(\d{{1,2}}),?\s*(\d{{4}})", label)
    if not match:
        return None
    month_name, day, year = match.groups()
    month = MONTHS.get(month_name)
    if not month:
        return None
    return date(int(year), month, int(day))