from urllib.parse import urlsplit

import keyring


def origin_of(url: str) -> str:
    address = urlsplit(url)
    if address.scheme != "https" or not address.hostname or address.username is not None:
        raise ValueError("凭据只支持 HTTPS 来源。")
    return f"https://{address.netloc}"


def credential(origin: str, name: str) -> str | None:
    return keyring.get_password("ruin:" + origin_of(origin), name)
