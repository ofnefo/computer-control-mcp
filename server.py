"""Shared stdio MCP. Run in the project virtual environment."""
from typing import Literal
from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from engine import Computer

computer = Computer()
mcp = FastMCP('computer-control', instructions='Shared Windows control. Prefer app API/CLI or browser integration. List windows, acquire exact window, observe refs, act semantically, verify, release. Physical input is a guarded fallback; never bypass USER_ACTIVE/LEASE_BUSY with a raw tool. Read the skills/computer-control/SKILL.md.')


@mcp.tool(annotations={'readOnlyHint': True})
def computer_status() -> dict:
    """Inspect backend, user idle time and shared leases, without moving focus or mouse."""
    return computer.status()


@mcp.tool(annotations={'readOnlyHint': True})
def computer_windows() -> dict:
    """List visible Windows windows with exact w-HWND, process, title, bounds and focus."""
    return computer.windows()


@mcp.tool()
def computer_acquire(owner: str, window_id: str, ttl: int = 120) -> dict:
    """Reserve one exact window for a stable agent owner (5..300s); returns a lease token.
    Different windows can be used concurrently. Same window: LEASE_BUSY, never steal.
    """
    return computer.acquire(owner, window_id, ttl)


@mcp.tool()
def computer_release(owner: str, window_id: str, token: str) -> dict:
    """Release your window lease after verification, including an expired own lease."""
    return computer.leases.release(window_id, owner, token)


@mcp.tool()
def computer_renew(owner: str, window_id: str, token: str, ttl: int = 120) -> dict:
    """Renew a current owned lease (5..300s); expired leases must be acquired again."""
    return computer.leases.renew(window_id, owner, token, ttl)


@mcp.tool(annotations={'readOnlyHint': True})
def computer_observe(owner: str, window_id: str, token: str, depth: int = 8) -> dict:
    """Read this window's accessibility tree and qualified refs, without screenshots or focus.
    Ref namespace belongs to the lease. Fresh snapshot after mutations or STALE_REF.
    """
    return computer.observe(owner, window_id, token, depth)


@mcp.tool()
def computer_action(owner: str, window_id: str, token: str,
                    action: Literal['click','set-value','clear','select','toggle','check','uncheck','expand','collapse','scroll-to'],
                    ref: str, text: str | None = None) -> dict:
    """Perform strict semantic UIA action on a ref from this lease; unsupported patterns fail.
    set-value accepts literal text, delivered through stdin, never process arguments/clipboard.
    Refuse if target is foreground and user idle <5s; foreground idle >=5s may act.
    Prefer background targets; never poll a typing pause after USER_ACTIVE. Observe to verify.
    """
    return computer.action(owner, window_id, token, action, ref, text)


@mcp.tool(annotations={'readOnlyHint': True})
def computer_screenshot(owner: str, window_id: str, token: str):
    """Capture only the target window when visual evidence is needed; no automatic screenshot loop."""
    result = computer.screenshot(owner, window_id, token)
    if 'capture_path' in result:
        return Image(path=result['capture_path'])
    return result


@mcp.tool()
def computer_input(owner: str, window_id: str, token: str,
                   action: Literal['click','right-click','key','text'],
                   x: int | None = None, y: int | None = None, value: str | None = None) -> dict:
    """ONE physical action, only if target is foreground and user idle >=5s.
    Global desktop lease prevents other cooperative agents using input simultaneously.
    Click coordinates are physical desktop pixels, never scaled preview pixels. Covered points fail.
    key: one chord (ctrl+s). text: literal <=32 chars, no clipboard. Never automatic focus.
    USER_ACTIVE/FOCUS_CHANGED: stop and use semantic/API; don't bypass with Windows MCP.
    """
    return computer.physical(owner, window_id, token, action, x, y, value)


if __name__ == '__main__':
    mcp.run(transport='stdio', show_banner=False)
