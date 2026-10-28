"""MCP stdio adapter; no model client or account configuration."""
import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .contracts import INSTRUCTIONS
from .project import Toolkit


def create_server(root):
    if not Path(root).is_absolute():
        raise ValueError("MCP runtime must be an absolute path")
    toolkit = Toolkit(root)
    server = FastMCP("agent-video-toolkit", instructions=INSTRUCTIONS)
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)

    @server.tool(annotations=read)
    def avt_projects() -> dict:
        """List frozen local runs. No network or model calls."""
        return toolkit.projects()

    @server.tool(annotations=write)
    def avt_prepare(manifest_path: str, visual_brief: str, workers: int = 4, preview_width: int | None = None, allow_synthetic: bool = False) -> dict:
        """Snapshot real inputs and allocate up to four equal-role paragraph workers."""
        return toolkit.prepare(manifest_path, visual_brief, workers, preview_width, allow_synthetic)

    @server.tool(annotations=write)
    def avt_task(run_id: str, worker_id: str, claimant: str) -> dict:
        """Claim/read an assigned paragraph task; every worker owns the complete picture job."""
        return toolkit.task(run_id, worker_id, claimant)

    @server.tool(annotations=write)
    def avt_submit(run_id: str, worker_id: str, claim_token: str, result: dict, expected_sha256: str | None = None) -> dict:
        """Validate and commit complete design and Canvas code with a CAS revision guard."""
        return toolkit.submit(run_id, worker_id, claim_token, result, expected_sha256)

    @server.tool(annotations=write)
    def avt_assemble(run_id: str) -> dict:
        """Verify frozen inputs and all results, then bind their ordered frame coverage."""
        return toolkit.assemble(run_id)

    @server.tool(annotations=write)
    def avt_render(run_id: str) -> dict:
        """Start one local render. Repeated calls return the same request, including failures."""
        return toolkit.render(run_id)

    @server.tool(annotations=read)
    def avt_status(run_id: str) -> dict:
        """Read progress and verified output paths; technical checks do not approve aesthetics."""
        return toolkit.status(run_id)

    return server


def main():
    parser = argparse.ArgumentParser(description="Agent Video Toolkit MCP stdio server")
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    create_server(args.root).run(transport="stdio")


if __name__ == "__main__":
    main()
