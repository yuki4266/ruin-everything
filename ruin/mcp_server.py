"""Expose the local Ashby receipt journal and watcher to stdio MCP clients."""

import argparse
from typing import Annotated, Literal

from ruin.agent.ashby import application_url, lookup_receipt, resume_ashby
from ruin.browser.context import browser_context
from ruin.config import PROFILE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp", help="Local Chrome HTTP debugging endpoint for the receipt watcher")
    args = parser.parse_args()
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
        from pydantic import BaseModel, Field
    except ModuleNotFoundError as exc:
        if exc.name == "mcp":
            parser.exit(1, "Install the MCP extra with python -m pip install -e '.[mcp]'.\n")
        raise

    class Receipt(BaseModel):
        state: Literal["submitted"]
        site: str
        observed_at: str
        message: str

    class Lookup(BaseModel):
        state: Literal["unrecorded", "submitted"]
        site: str
        observed_at: str | None = None
        message: str | None = None

    server = FastMCP("Ruin Everything")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    def get_ashby_receipt(site: str) -> Lookup:
        """Look up one exact Ashby application URL locally. Unrecorded means the outcome is unknown."""
        site = application_url(site)
        receipt = lookup_receipt(site, PROFILE.parent)
        return Lookup(**receipt) if receipt else Lookup(state="unrecorded", site=site)

    @server.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
    async def watch_ashby_receipt(
        site: str, timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 15
    ) -> Receipt:
        """Return saved evidence or watch the original tab for official success. This never submits the form."""
        site = application_url(site)
        receipt = lookup_receipt(site, PROFILE.parent)
        if receipt:
            return Receipt(**receipt)
        async with browser_context(PROFILE, args.cdp) as context:
            evidence = await resume_ashby(context, site, timeout_seconds, PROFILE.parent, lambda event: None)
        return Receipt(**evidence)

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
