import json
from pathlib import Path

def deduplicate_signals(signals):
    unique_signals = []
    seen_ids = set()

    for signal in signals:
        signal_id = signal.get("signal_id")

        # keep singals without a usable ID for now.
        if signal_id is None or not str(signal_id).strip():
            unique_signals.append(signal)
            continue

        normalized_id = str(signal_id).strip()

        if normalized_id not in seen_ids:
            seen_ids.add(normalized_id)
            unique_signals.append(signal)

    return unique_signals

def detect_signals(company):
    if not isinstance(company, dict):
        raise TypeError("company must be a dictionary")
    
    signals = company.get("signals") or []

    if not isinstance(signals, list):
        raise ValueError("company signals must be a list")

    funding, hiring = [], []

    for signal in signals:
        if not isinstance(signal, dict):
            continue

        kind = str(signal.get("signal_type", "")).strip().lower()
        
        if kind == "funding":
            funding.append(signal)
        elif kind == "hiring":
            hiring.append(signal)

    return {
        "company": company.get("name"),
        "funding":deduplicate_signals(funding),
        "hiring":deduplicate_signals(hiring),
    }

def main():
    project_root = Path(__file__).resolve().parent.parent
    data_path = project_root / "data" / "sample_companies.json"

    with data_path.open("r", encoding="utf-8") as file:
        companies = json.load(file)

    if not isinstance(companies, list):
        raise ValueError("Sample data must contain a list of companies")
    
    for company in companies:
        print(detect_signals(company))

if __name__ == "__main__":
    main()
