from datetime import date as date_cls
from ingestion.chunker import (
    extract_table_grid,
    clean_row,
    merge_headers,
    parse_column_end_date,
)

CONCEPT_SCALE = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": 1_000_000,
    "Revenues": 1_000_000,
    "NetIncomeLoss": 1_000_000,
    "OperatingIncomeLoss": 1_000_000,
    "CostOfRevenue": 1_000_000,
    "GrossProfit": 1_000_000,
    "Assets": 1_000_000,
    "EarningsPerShareBasic": 1,
    "EarningsPerShareDiluted": 1,
    "WeightedAverageNumberOfSharesOutstandingBasic": 1,
    "WeightedAverageNumberOfDilutedSharesOutstanding": 1,
}
DEFAULT_SCALE = 1_000_000

# Sanity ceiling per concept — used to reject an implausible match (e.g. a
# "Diluted" row that's actually share count, not EPS) so the search can keep
# looking instead of silently accepting a wrong row.
PLAUSIBLE_MAX = {
    "EarningsPerShareBasic": 100,
    "EarningsPerShareDiluted": 100,
}


def classify_period_length(start_iso: str, end_iso: str) -> str | None:
    days = (date_cls.fromisoformat(end_iso) - date_cls.fromisoformat(start_iso)).days
    if days < 100:
        return "Three Months Ended"
    elif days < 130:
        return "Six Months Ended"
    elif days < 300:
        return "Nine Months Ended"
    elif days < 380:
        return "Year Ended"
    return None


def match_fact_to_table(fact: dict, table_values: dict[str, str], concept: str) -> dict | None:
    """Try to match fact against table_values. Returns None if no column
    matches the period, OR if the matched value fails a plausibility check
    (caller should treat None as 'keep searching', not 'give up')."""
    expected_period_text = classify_period_length(fact["start"], fact["end"])
    if not expected_period_text:
        return None

    scale = CONCEPT_SCALE.get(concept, DEFAULT_SCALE)
    max_plausible = PLAUSIBLE_MAX.get(concept)

    for col_label, val_str in table_values.items():
        col_end_date = parse_column_end_date(col_label)
        if not col_end_date:
            continue
        if str(col_end_date) != fact["end"]:
            continue
        if expected_period_text not in col_label:
            continue

        try:
            table_val_scaled = float(val_str.replace(",", "")) * scale
        except ValueError:
            continue

        if max_plausible and abs(table_val_scaled) > max_plausible:
            continue  # implausible for this concept — likely wrong row, keep scanning other columns

        xbrl_val = fact["val"]
        if xbrl_val != 0:
            relative_error = abs(table_val_scaled - xbrl_val) / abs(xbrl_val)
        else:
            relative_error = abs(table_val_scaled - xbrl_val)

        exact_match = relative_error < 0.001

        return {
            "column_label": col_label,
            "table_value_scaled": table_val_scaled,
            "xbrl_value": xbrl_val,
            "exact_match": exact_match,
            "relative_error": relative_error,
            "concept": concept,
        }

    return None


def build_table_values(table) -> dict[str, str] | None:
    """Parse one <table> tag into {column_label: value} for its data rows.
    Returns None if the table doesn't have a usable header/data structure."""
    grid = extract_table_grid(table)
    cleaned_grid = [clean_row(row) for row in grid if clean_row(row)]
    if len(cleaned_grid) < 3:
        return None

    period_row, date_row = cleaned_grid[0], cleaned_grid[1]
    try:
        column_labels = merge_headers(period_row, date_row)
    except ZeroDivisionError:
        return None

    return cleaned_grid, column_labels


def find_match_for_concept(
    soup,
    fact: dict,
    concept: str,
    row_label_candidates: list[str],
    anchor_labels: list[str],
) -> dict | None:
    """Search every table, try every candidate row label, and return the
    first result that both matches the period AND passes the plausibility
    check. Keeps searching across tables/labels instead of stopping at the
    first row-label hit — this is what lets it skip a 'Diluted' share-count
    row in favor of the real 'Diluted' EPS row elsewhere in the filing."""
    for table in soup.find_all("table"):
        text = table.get_text()
        if not any(anchor in text for anchor in anchor_labels):
            continue

        built = build_table_values(table)
        if not built:
            continue
        cleaned_grid, column_labels = built
        data_rows = cleaned_grid[2:]

        for row_label in row_label_candidates:
            row = next((r for r in data_rows if r[0] == row_label), None)
            if not row:
                continue

            _label, *values = row
            if len(values) != len(column_labels):
                continue

            table_values = dict(zip(column_labels, values))
            result = match_fact_to_table(fact, table_values, concept)
            if result:
                return result  # found a plausible, period-matched value — done

    return None  # exhausted every table/candidate — no confident match


def match_facts_for_filing(
    soup,
    company_facts: dict,
    accession: str,
    period_end: str,
    concept_row_map: dict[str, list[str]],
) -> list[dict]:
    us_gaap = company_facts["facts"]["us-gaap"]
    results = []
    all_labels = [label for labels in concept_row_map.values() for label in labels]

    for concept, row_label_candidates in concept_row_map.items():
        if concept not in us_gaap:
            results.append({"concept": concept, "status": "concept_not_found"})
            continue

        entries = us_gaap[concept]["units"].get("USD") or us_gaap[concept]["units"].get("USD/shares")
        if not entries:
            results.append({"concept": concept, "status": "no_usd_units"})
            continue

        target = next(
            (e for e in entries
             if e["accn"] == accession and e["end"] == period_end
             and (date_cls.fromisoformat(e["end"]) - date_cls.fromisoformat(e["start"])).days < 100),
            None
        )
        if not target:
            results.append({"concept": concept, "status": "no_xbrl_entry"})
            continue

        result = find_match_for_concept(soup, target, concept, row_label_candidates, all_labels)
        if not result:
            results.append({"concept": concept, "status": "no_confident_match", "xbrl_value": target["val"]})
            continue

        result["status"] = "matched"
        results.append(result)

    return results