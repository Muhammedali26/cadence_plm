"""
src/mcp_servers
===============
CadencePLM Model Context Protocol (MCP) sunucu katmanı.
"""

from __future__ import annotations

from src.mcp_servers.fastmcp_gateway import (
    cadence_mcp,
    mcp,
    tool_get_ebom,
    tool_get_inventory,
    tool_run_impact_simulation,
)

__all__: list[str] = [
    "cadence_mcp",
    "mcp",
    "tool_get_ebom",
    "tool_get_inventory",
    "tool_run_impact_simulation",
]
