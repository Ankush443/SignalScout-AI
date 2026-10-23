from urllib.parse import urlparse


def assess_source(signal):
    if not isinstance(signal, dict):
        raise TypeError("signal must be a dictionary")

    source_url = signal.get("source_url")

    if not isinstance(source_url, str) or not source_url.strip():
        return "missing_source"

    source_url = source_url.strip()

    try:
        parsed = urlparse(source_url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or any(char.isspace() for char in source_url)
        ):
            return "invalid_source_url"

    except (ValueError, TypeError):
        return "invalid_source_url"

    # This status must come from a trusted verification process,
    # not merely from the presence of a URL.
    if signal.get("verification_status") == "verified":
        return "verified"

    return "unverified"
