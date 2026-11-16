# Computer Control MCP

A Windows MCP server and companion agent skill for sharing a desktop with a human and other agents. Select an exact window, reserve it, inspect its accessibility tree, act through semantic controls, verify, and release.

- Nine MCP tools, plus a JSON-over-stdin CLI.
- Per-window leases with process identity checks and cross-process locking.
- Background semantic actions without automatic focus changes.
- Guarded physical input only when the target is already foreground and the user has been idle for at least five seconds.
- On-demand window screenshots. No clipboard text injection or automatic screenshot loop.

This coordinates cooperating agents; it is **not a security boundary**. Human input and tools that bypass this server can still race with an action. An inactivity timer does not establish user consent. Stop after `USER_ACTIVE` instead of repeatedly waiting for a typing pause.

## Requirements

Windows x64, Python **3.14**, and an interactive desktop session. Run under the same Windows user/session as the target apps. SSH services and session 0 are not supported for desktop interaction. Protected, elevated or minimized windows may be inaccessible.

## Install

From PowerShell:

```powershell
git clone https://github.com/ofnefo/computer-control-mcp.git
cd computer-control-mcp
py -3.14 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe install_backend.py
.venv/Scripts/python.exe -m unittest -v test_control
.venv/Scripts/python.exe mcp_probe.py
```

The backend installer downloads the pinned 1.2.0 Windows x64 release (about 1.8 MB), checks SHA-256, and extracts only `agent-desktop.exe` to `vendor/`. It refuses to overwrite an existing backend. No administrator access or cloud API key is required.

## Connect an MCP client

Merge the following into your client's MCP configuration. Replace `C:/tools/computer-control-mcp` with the **absolute** clone path. The server uses stdio; no port or HTTP service is opened.

```json
{
  "mcpServers": {
    "computer-control": {
      "command": "C:/tools/computer-control-mcp/.venv/Scripts/python.exe",
      "args": ["-X", "utf8", "-B", "C:/tools/computer-control-mcp/server.py"]
    }
  }
}
```

For a Codex TOML configuration:

```toml
[mcp_servers.computer-control]
command = "C:/tools/computer-control-mcp/.venv/Scripts/python.exe"
args = ["-X", "utf8", "-B", "C:/tools/computer-control-mcp/server.py"]
```

Copy [skills/computer-control](skills/computer-control) into your agent's skill directory (for example `~/.agents/skills/computer-control`), or point the agent directly to its `SKILL.md`. The skill includes its own provenance reference. Reconnect the MCP client after changing its configuration.

All clients controlling the same desktop **must share one state directory**. By default this is `%LOCALAPPDATA%/computer-control-mcp`, outside the repository. Lease state, backend sessions and captures stay there and may contain private desktop data. Use a private local folder, not a network share or a synced public directory.

Optional environment variables (set identically in every client):

| Variable | Purpose |
| --- | --- |
| `COMPUTER_CONTROL_STATE` | Absolute shared state directory; defaults to the location above |
| `COMPUTER_CONTROL_BACKEND` | Absolute path to a compatible agent-desktop 1.2.0 executable; defaults to `vendor/agent-desktop.exe` |

## Agent workflow

1. Prefer an application's API, CLI or dedicated integration when available.
2. Call `computer_status` and `computer_windows`; identify the exact `w-<HWND>` by title, process and app.
3. Call `computer_acquire` with a stable owner ID. Keep its token private. A busy lease is not yours to release.
4. Call `computer_observe`; use its qualified `@s…:e…` references in `computer_action`.
5. Observe again and verify the actual state. Unknown delivery means inspect before retrying, especially for submit/save/send.
6. Renew before expiry while working; release your lease in `finally`.

`computer_screenshot` is optional visual evidence. `computer_input` is the physical fallback: one click, right-click, key chord or short literal text action. It never brings a window to the foreground. `USER_ACTIVE`, `FOCUS_CHANGED` and `POINT_NOT_IN_TARGET` require stopping physical actions; do not bypass them using another tool.

| Tool | Operation |
| --- | --- |
| `computer_status` | Backend availability, user presence and leases |
| `computer_windows` | Visible windows and identities |
| `computer_acquire` | Reserve one window for 5–300 seconds |
| `computer_renew` | Renew your current reservation |
| `computer_release` | Release your reservation |
| `computer_observe` | Scoped accessibility tree and qualified references |
| `computer_action` | Strict semantic control action |
| `computer_screenshot` | Capture the reserved window |
| `computer_input` | Guarded physical fallback |

## CLI and checks

```powershell
'{"command":"status"}' | .venv/Scripts/python.exe -X utf8 -B engine.py
'{"command":"windows"}' | .venv/Scripts/python.exe -X utf8 -B engine.py
```

CLI commands: `status`, `windows`, `acquire`, `observe`, `action`, `screenshot`, `physical`, `renew`, `release`. The CLI uses `resource` for renew/release, where MCP uses `window_id`. Pass entered text and tokens through stdin, never command arguments.

`test_control.py` checks competing leases, expiration during operations, ownership, identity changes, foreground activity, stdin text delivery and guarded input. `mcp_probe.py` initializes the real stdio server, checks all nine tools and calls status/windows without interacting with apps.

For an opt-in live UI test, launch `fixture.ps1` with Windows PowerShell in the interactive session, then run `.venv/Scripts/python.exe probe.py`. The fixture does not activate itself and closes after 180 seconds. The probe targets only its exact fixture title, changes a text field, invokes its button and checks the result while verifying foreground and cursor are unchanged. It writes an acceptance record and screenshot into the private state folder. Do not run it against another user's fixture.

## License and provenance

The original facade and skill are MIT licensed. External backends are installed separately and retain their licenses. See [THIRD_PARTY.md](THIRD_PARTY.md).
