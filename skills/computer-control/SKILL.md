---
name: computer-control
description: "Use when controlling Windows apps or the desktop: управление компьютером, окна, кнопки, UI Automation, мышь, клавиатура, agent-desktop, agent-windows, Windows MCP. One shared API-first workflow with window leases and guarded physical input for Codex, Claude and other agents. Not a visual-design or cloud-desktop skill."
---

# Computer control

Use the companion computer-control-mcp server. One workflow for every agent.
Run on the Windows host with the application in its interactive session. Remote agents delegate UI work to an agent in that session; SSH/session 0 cannot drive the interactive desktop reliably.

## Choose the shortest reliable route

| Task | Route |
| --- | --- |
| Files, Git, builds, system information | Existing CLI/API, no GUI |
| Logged-in browser | A browser integration with its own agent profile; never the user's personal profile |
| Adobe, Excel, Figma, ArtCraft, other app with a connected API | Its existing MCP/COM/CLI and domain skill; reserve the target window for interactive writes |
| Native Windows controls | `computer-control`: scoped accessibility tree and semantic actions |
| Canvas, custom-painted UI, Tk/Java controls without accessibility | App scripting/headless CLI first; targeted screenshot and guarded physical input only when needed |
| Managed cloud desktop | The cloud environment's own skill; this tool controls local Windows only |

The native backend is pinned Vercel `agent-desktop` 1.2.0. From bvosk `agent-windows` we adopt isolated target sessions, attach-by-window and the observe/ref/verify workflow; we do **not** run its unguarded click/fill fallback or require its .NET 10 daemon. Existing CursorTouch Windows-MCP supplies the bounded physical fallback. See [provenance and limitations](references/backends.md).

## Normal loop (no screenshot needed)

1. `computer_status` and `computer_windows`; select exact `w-<HWND>` by title, PID and app. A title substring is not ownership.
2. `computer_acquire(owner=<stable agent id>, window_id=..., ttl=120)`. Keep its token local to this task. `LEASE_BUSY` names the current owner: coordinate or use another window. Never release another agent's reservation.
3. `computer_observe` with owner/window/token. Use returned qualified `@s…:e…` refs. Prefer AutomationId/name/role and exact window context; never guess a ref or reuse one across leases.
4. `computer_action`: semantic `click`, `set-value`, `check`, `uncheck`, `select`, `expand`, etc. Text stays out of child process arguments and the clipboard. Unsupported patterns fail; there is no implicit `--headed` fallback.
5. Observe after mutation and verify the actual value/state. If delivery is unknown, inspect before retrying; do not duplicate a submit/save/send. Reobserve on stale refs or changed UI. One failed strategy plus one relevant fallback, then explain the specific blocker.
6. Renew before expiry only while working. Release in `finally` after verification. Different windows can progress concurrently; the same window cannot.

For long tasks, track your own app process and give temporary jobs a finite lifetime; acquiring a window does not reserve GPU/RAM or own the process. It never authorizes killing, closing, moving or minimizing someone else's window.

## Coexist with the user

Prefer background semantic operations. A semantic write returns `USER_ACTIVE` when the target is foreground and the last user input was less than five seconds ago. At five seconds or more it may act on that already-selected, leased window without changing focus. This is an inactivity heuristic, not proof the user has finished: do not keep retrying after `USER_ACTIVE` or use a typing pause as permission. Background writes to a different leased window can proceed while the user uses another window.
For a real pointer/key action use **only** `computer_input`: one action under a global desktop-input lease, target already foreground, user idle at least five seconds. It does not bring a window forward. Clicks verify the point still belongs to that top-level window. Use physical pixel coordinates from the actual capture/window bounds, not resized chat previews.

`USER_ACTIVE`, `FOCUS_CHANGED`, `POINT_NOT_IN_TARGET`: stop physical actions, continue independent work or semantic/API work. If foregrounding is essential and API access is impossible, tell the user exactly which window to activate when convenient. Do not loop waiting for a brief typing pause, steal focus, lock input, hide windows, or bypass the guard through raw Windows MCP, PowerShell or a direct backend.

`computer_screenshot` returns one window image only on demand. Use for visual checks or inaccessible controls, not before every command. Minimized, protected, elevated or inaccessible windows may refuse capture/control; do not restore or elevate them implicitly. An empty Chromium tree can need a longer accessibility warmup, not repeated screenshots.

This is cooperative coordination, **not** a security boundary: the user and old/raw tools can still act. There is a small race between presence checks and one delivered input event. Never claim guaranteed isolation or zero mistakes. Existing chats retain old tool connections until refreshed; they must follow this skill via its canonical path meanwhile.

## CLI fallback (same guard and state as MCP)

From the repository root:
`.venv/Scripts/python.exe -X utf8 -B engine.py`

Feed a JSON request on stdin (PowerShell here-string or a private local file); do not put entered text or tokens in arguments:

```json
{"command":"windows"}
```

Commands: `status`, `windows`, `acquire`, `observe`, `action`, `screenshot`, `physical`, `renew`, `release`. For renew/release the CLI key is `resource` (the window_id). Other keys match MCP. Keep entered data and screenshots out of Git/logs; captures are local under `%LOCALAPPDATA%/computer-control-mcp/captures` (or `COMPUTER_CONTROL_STATE/captures`).

## Acceptance

- Background field update and button invocation verified by reading the real fixture window; foreground and cursor unchanged.
- A second process cannot acquire the same window; a different window can proceed.
- Expired lease cannot steal an in-flight operation; wrong tokens and changed process identity fail.
- User activity, focus changes and covered click coordinates refuse physical input.
- MCP initialize/list/tools/call works; each connected agent discovers this same skill and server entry point.
