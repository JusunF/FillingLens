CONCEPT_TEMPLATES = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {
        "label": "total revenue",
        "template": "What was {company}'s total revenue for the {period}?",
        "unit": "USD",
    },
    "NetIncomeLoss": {
        "label": "net income",
        "template": "What was {company}'s net income for the {period}?",
        "unit": "USD",
    },
    "EarningsPerShareDiluted": {
        "label": "diluted earnings per share",
        "template": "What was {company}'s diluted earnings per share (EPS) for the {period}?",
        "unit": "USD_per_share",
    },
    "OperatingIncomeLoss": {
        "label": "operating income",
        "template": "What was {company}'s operating income for the {period}?",
        "unit": "USD",
    },
}

def humanize_period(column_label: str) -> str:
    text = column_label.replace(",", ", ").replace("  ", " ").strip()
    for prefix in ("Three Months Ended", "Six Months Ended", "Nine Months Ended", "Year Ended"):
        if text.startswith(prefix):
            rest = text[len(prefix):].strip()
            return f"{prefix.lower()} {rest}"
    return text


def format_expected_value(value, unit: str) -> str:
    if unit == "USD_per_share":
        return f"${value:.2f} per share"
    if unit == "USD":
        return f"${value:,.0f}"
    return str(value)


def generate_question(golden_fact_row: dict) -> dict | None:
    """
    golden_fact_row: a dict matching the golden_facts table schema
        (company, concept, column_label, xbrl_value, relative_error, exact_match, ...)

    Returns a QA record: {question, expected_value, expected_value_display,
    unit, tolerance, source_company, source_concept, source_column}
    or None if the concept has no template or the row wasn't a confident match.
    """
    concept = golden_fact_row["concept"]
    if concept not in CONCEPT_TEMPLATES:
        return None
    if not golden_fact_row.get("exact_match"):
        return None  # only synthesize questions from confidently matched facts

    template_info = CONCEPT_TEMPLATES[concept]
    period_phrase = humanize_period(golden_fact_row["column_label"])
    question = template_info["template"].format(
        company=golden_fact_row["company"],
        period=period_phrase,
    )

    value = float(golden_fact_row["xbrl_value"])

    return {
        "question": question,
        "expected_value": value,
        "expected_value_display": format_expected_value(value, template_info["unit"]),
        "unit": template_info["unit"],
        "tolerance": 0.001,  # relative tolerance, matches matcher's own threshold
        "source_company": golden_fact_row["company"],
        "source_concept": concept,
        "source_column": golden_fact_row["column_label"],
    }