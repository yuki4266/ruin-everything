from urllib.parse import urlsplit


def origin_of(url: str) -> str:
    address = urlsplit(url)
    if address.scheme != "https" or not address.hostname or address.username is not None:
        raise ValueError("Credentials require an HTTPS origin.")
    return f"https://{address.netloc}"


def credential(origin: str, name: str) -> str | None:
    import keyring

    return keyring.get_password("ruin:" + origin_of(origin), name)
