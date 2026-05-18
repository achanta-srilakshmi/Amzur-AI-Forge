import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_URL_REGEX = re.compile(r"https?://[^\s<>\"']+")


def _trim_url(raw_url: str) -> str:
    return raw_url.strip().rstrip(".,);]\"'")


def _normalize_google_sheet_url(parsed_url: tuple[str, str, str, str, str, str]) -> str:
    scheme, netloc, path, params, query, fragment = parsed_url
    query_params = parse_qs(query, keep_blank_values=True)
    fragment_params = parse_qs(fragment, keep_blank_values=True)

    if "gid" not in query_params and "gid" in fragment_params:
        query_params["gid"] = fragment_params["gid"]

    normalized_query = urlencode(query_params, doseq=True)
    return urlunparse((scheme, netloc, path, params, normalized_query, ""))


def _classify_and_normalize_url(raw_url: str) -> tuple[str, str] | None:
    candidate = _trim_url(raw_url)
    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if host.endswith("docs.google.com") and path.startswith("/spreadsheets/"):
        normalized = _normalize_google_sheet_url(parsed)
        return ("google_sheet", normalized)

    if host.endswith("docs.google.com") and path.startswith("/document/"):
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        return ("shared_doc", normalized)

    if host.endswith("drive.google.com") and (
        path.startswith("/file/") or path.startswith("/open")
    ):
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        return ("shared_doc", normalized)

    if path.endswith(".csv") or path.endswith(".xlsx"):
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        return ("shared_doc", normalized)

    return None


def extract_shared_source_links(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for raw_url in _URL_REGEX.findall(text):
        classified = _classify_and_normalize_url(raw_url)
        if classified is None:
            continue
        if classified in seen:
            continue
        seen.add(classified)
        found.append(classified)

    return found