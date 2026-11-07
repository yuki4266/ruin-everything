"""Edit the local identity in a temporary, network-isolated Chrome window."""

import json
import os
import tempfile
from pathlib import Path

import phonenumbers as phones
from playwright.async_api import async_playwright

from ruin.auth.auto_registrar import identity
from ruin.browser.context import chrome_executable


def normalize_numbers(entries, default):
    if not entries or type(default) is not int or not 0 <= default < len(entries):
        raise ValueError("Choose a default phone number.")
    result = []
    for index, entry in enumerate(entries, 1):
        try:
            region = entry["region"]
            number = phones.parse(entry["number"], region)
            if not phones.is_possible_number(number) or number.extension:
                raise ValueError
        except (KeyError, ValueError, phones.NumberParseException):
            raise ValueError(f"Check phone number {index} and its country or region.") from None
        result.append({"region": phones.region_code_for_number(number) or region,
                       "number": phones.format_number(number, phones.PhoneNumberFormat.E164)})
    return result, result[default]["number"]


def save_profile(profile, path):
    path.parent.mkdir(exist_ok=True, parents=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temp:
        try:
            json.dump(profile, temp, indent=2)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
            os.replace(temp.name, path)
        finally:
            Path(temp.name).unlink(missing_ok=True)


async def setup():
    profile = identity()
    regions = {r: phones.country_code_for_region(r) for r in sorted(phones.SUPPORTED_REGIONS)}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=chrome_executable(), headless=False,
                                           args=["--lang=en-US", "--window-size=820,900"])
        page = await browser.new_page(locale="en-US", no_viewport=True)
        await page.route("**/*", lambda route: route.abort())
        await page.set_content(Path(__file__).with_name("identity_setup.html").read_text())
        entries = profile.get("phone_numbers") or [{"region": "", "number": profile.get("phone", "")}]
        await page.evaluate("data => initialize(data)", {
            "regions": regions, "entries": entries, "phone": profile.get("phone", ""),
            "email": profile.get("email", ""), "password": profile.get("default_password", ""),
            "enabled": profile.get("auto_signup") is True})
        await page.bring_to_front()
        while True:
            await page.wait_for_function("window.submission != null", timeout=0)
            data = await page.evaluate("() => {const data=window.submission;window.submission=null;return data}")
            if data == "cancel":
                return
            try:
                entries, default = normalize_numbers(data["entries"], data["defaultIndex"])
            except ValueError as exc:
                await page.locator("#status").evaluate("(s,v)=>s.textContent=v", str(exc))
                await page.locator("#save").evaluate("b=>b.disabled=false")
                continue
            profile.update(email=data["email"], default_password=data["password"], phone_numbers=entries,
                           phone=default, auto_signup=data["enabled"])
            save_profile(profile, Path.home() / ".ruin/identity.json")
            print("Local identity saved.")
            return
