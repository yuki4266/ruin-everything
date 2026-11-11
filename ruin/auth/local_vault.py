"""Private, atomic local authentication records. Never return secrets to an agent."""
import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from filelock import FileLock
from tldextract import TLDExtract

ROOT = Path.home() / '.ruin'
# Use the packaged PSL, including private suffixes, without network access.
_suffix = TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)


def hostname(url):
    parsed = urlsplit(url)
    return parsed.hostname.lower().rstrip('.') if parsed.scheme == 'https' and parsed.hostname else None


class PrivateJSON:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    def read(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return {}
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError('Local auth file must belong to the current user.')
            os.fchmod(stream.fileno(), 0o600)
            try:
                data = json.load(stream)
                if not isinstance(data, dict):
                    raise ValueError()
                return data
            except (ValueError, UnicodeError):
                raise RuntimeError('Local auth file contains invalid JSON; it was not overwritten.') from None

    def update(self, change):
        with FileLock(str(self.path) + '.lock', mode=0o600):
            data = self.read()
            change(data)
            name = None
            try:
                with NamedTemporaryFile(mode='w', dir=self.path.parent, delete=False) as stream:
                    name = stream.name
                    os.fchmod(stream.fileno(), 0o600)
                    json.dump(data, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.path)
            finally:
                if name and os.path.exists(name):
                    os.unlink(name)


class LocalVault:
    def __init__(self, root=ROOT):
        self.file = PrivateJSON(Path(root) / 'auth_vault.json')

    def save(self, url, username, password):
        host = hostname(url)
        if not host or not isinstance(username, str) or not isinstance(password, str) or not password:
            return
        if len(username) > 4096 or len(password) > 16384:
            return
        def save(data):
            previous = data.get(host, {})
            data[host] = {'username': username or previous.get('username', ''), 'password': password}
        self.file.update(save)

    def lookup(self, url):
        host = hostname(url)
        if not host:
            return None
        data = self.file.read()
        if host in data:
            return data[host]
        # Never search sibling subdomains. Only a record captured on the actual
        # registrable domain is eligible as the requested fallback.
        domain = _suffix(host).top_domain_under_public_suffix
        return data.get(domain) if domain else None
