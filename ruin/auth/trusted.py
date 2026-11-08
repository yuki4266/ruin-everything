"""Explicit, task-scoped login actions; never a background consent handler."""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ruin.auth.vault import origin_of


def exact_origin(value):
    if not isinstance(value, str) or "*" in value or origin_of(value) != value:
        raise ValueError("Trusted origins must be exact HTTPS origins without a trailing slash.")
    return value


def origin_pattern(value):
    """Accept an exact origin or one explicit leftmost DNS wildcard."""
    if isinstance(value, str) and value.startswith("https://*."):
        exact_origin(value.replace("https://*.", "https://wildcard.", 1))
        host = urlsplit(value).hostname[2:]
        if "." not in host or not valid_dns(host):
            raise ValueError("Wildcard origins require a DNS domain suffix.")
        # Parsing the port also rejects malformed or out-of-range values.
        urlsplit(value).port
        return value
    return exact_origin(value)


def valid_dns(host):
    return len(host) <= 253 and all(re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label
    ) for label in host.split(".")) and not host.replace(".", "").isdigit()


def origin_matches(pattern, url):
    try:
        actual = origin_of(url)
        origin_pattern(pattern)
        if "*" not in pattern:
            return actual == pattern
        expected, address = urlsplit(pattern), urlsplit(actual)
        suffix = expected.hostname[1:]
        return (valid_dns(address.hostname) and address.hostname.endswith(suffix)
                and (443 if address.port is None else address.port) == (443 if expected.port is None else expected.port))
    except (TypeError, ValueError):
        return False


def load_trusted_oauth_clients(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        clients = data["trusted_oauth_clients"]
        if not isinstance(clients, list):
            raise ValueError()
        origins = set()
        for client in clients:
            origin = origin_pattern(client["origin"])
            if origin in origins:
                raise ValueError()
            origins.add(origin)
            if type(client.get("chrome_password_dropdown", False)) is not bool:
                raise ValueError()
            if not isinstance(client.get("actions", []), list):
                raise ValueError()
            for action in client.get("actions", []):
                origin_pattern(action["origin"])
                path_value = action["path"]
                if not isinstance(path_value, str) or not path_value.startswith("/") or any(
                    c in path_value for c in "?#"
                ):
                    raise ValueError()
                if action["kind"] not in {"login", "sso", "stay_signed_in", "trust_browser", "oauth"}:
                    raise ValueError()
                if (action["kind"] != "oauth" or "name" in action) and (
                    not isinstance(action.get("name"), str) or not action["name"].strip()
                ):
                    raise ValueError()
                if action["kind"] == "oauth":
                    exact_origin(origin)
                    if (action["origin"], action["path"]) != ("https://github.com", "/login/oauth/authorize"):
                        raise ValueError()
                    oauth = action["oauth"]
                    if not isinstance(oauth["client_id"], str) or not oauth["client_id"]:
                        raise ValueError()
                    if origin_of(oauth["redirect_uri"]) != origin:
                        raise ValueError()
                    if not isinstance(oauth["scopes"], list) or not all(
                        isinstance(s, str) and s and not any(c.isspace() for c in s) for s in oauth["scopes"]
                    ):
                        raise ValueError()
                elif action["origin"] != origin:
                    # Cross-origin providers require a dedicated OAuth adapter.
                    raise ValueError()
        return clients
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid trusted-auth.json; no trusted login actions were loaded.") from None


def trusted_client(clients, task_url):
    origin = origin_of(task_url)
    matched = [client for client in clients if origin_matches(client["origin"], origin)]
    # An exact override wins; otherwise use the most specific DNS suffix.
    return max(matched, key=lambda c: ("*" not in c["origin"], len(urlsplit(c["origin"]).hostname)), default=None)


def matches_action(action, url):
    location = urlsplit(url)
    if not origin_matches(action["origin"], url) or location.path != action["path"]:
        return False
    if action["kind"] != "oauth":
        # OAuth endpoints cannot be authorized through a generic login rule.
        return not ("oauth" in location.path.lower() or "authorize" in location.path.lower())
    query = parse_qs(location.query, keep_blank_values=True)
    oauth = action["oauth"]
    if any(len(query.get(key, [])) != 1 for key in ("client_id", "redirect_uri", "scope")):
        return False
    return (query["client_id"][0] == oauth["client_id"]
            and query["redirect_uri"][0] == oauth["redirect_uri"]
            and set(query["scope"][0].split()) == set(oauth["scopes"]))
