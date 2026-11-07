import pyotp


def current_code(secret: str) -> str:
    """Generate a standard six-digit, 30-second TOTP from a base32 seed."""
    return pyotp.TOTP(secret).now()
