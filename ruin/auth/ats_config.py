"""Local ATS credentials. Never return secrets in command or tool results."""

import os
import secrets
import string
from pathlib import Path

from dotenv import dotenv_values, set_key
from filelock import FileLock


def config_path():
    return Path(os.environ.get("RUIN_ATS_ENV_FILE", str(Path.home() / ".ruin/.env"))).expanduser()


def strong(value):
    return (isinstance(value, str) and 16 <= len(value) <= 128 and
            all(any(c in alphabet for c in value) for alphabet in
                (string.ascii_uppercase, string.ascii_lowercase, string.digits, string.punctuation)) and
            not any(c.isspace() for c in value))


def settings():
    path = config_path()
    values = {}
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("The ATS env file must be a regular private file (mode 0600).")
        values = dotenv_values(path, interpolate=False)
    password = os.environ.get("ATS_DEFAULT_PASSWORD", values.get("ATS_DEFAULT_PASSWORD"))
    recover = os.environ.get("ATS_AUTO_RECOVER", values.get("ATS_AUTO_RECOVER", "false"))
    if password and not strong(password):
        raise ValueError("ATS_DEFAULT_PASSWORD must contain 16+ characters, upper/lowercase, digits and a special character.")
    return {"ats_default_password": password, "ats_auto_recover": str(recover).lower() in {"true", "1", "yes"}}


def setup():
    """Explicit opt-in: preserve a configured password, otherwise generate once."""
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with FileLock(str(path) + ".lock"):
        current = settings()
        password = current["ats_default_password"]
        if not password:
            alphabet = string.ascii_letters + string.digits + "!@#%_-+=?"
            while not strong(password):
                password = ''.join(secrets.choice(alphabet) for _ in range(24))
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        set_key(str(path), "ATS_DEFAULT_PASSWORD", password, quote_mode="always")
        set_key(str(path), "ATS_AUTO_RECOVER", "true", quote_mode="always")
        os.chmod(path, 0o600)
    return {"path": str(path), "password_configured": True, "auto_recover": True}
