# Third-party provenance

No third-party executable, environment, model, credential or captured desktop data is committed in this repository.

| Project | Use | Version / license |
| --- | --- | --- |
| [Vercel agent-desktop](https://github.com/vercel-labs/agent-desktop) | Native CLI for snapshots, qualified refs, strict headless actions and window capture | 1.2.0, Apache-2.0 |
| [CursorTouch Windows-MCP](https://github.com/CursorTouch/Windows-MCP) | `Desktop.click` and `Desktop.shortcut` in a bounded child process | 0.8.7, MIT |
| [FastMCP](https://github.com/jlowin/fastmcp) | stdio server and image responses | 4.0.11, Apache-2.0 |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Protocol smoke client | 2.3.0, MIT |
| [bvosk agent-windows](https://github.com/bvosk/agent-windows) | Design reference for exact-window/session ownership and observe/act/verify | No code or binaries copied |

The Windows x64 agent-desktop 1.2.0 archive SHA-256 is `a4199f741a441cedd349bf56c5eba01783b1261258b498efeb7ec9945220c3e8`, verified against the upstream GitHub release asset digest. Its source and license are available from the linked upstream repository. Python packages install their licensing metadata into the environment.

The facade is original Python, not a fork of the native backends. Unicode physical text uses Win32 SendInput rather than clipboard paste. No cloud service, persistent daemon, auto-start task, forced focus or process-kill endpoint is added.
