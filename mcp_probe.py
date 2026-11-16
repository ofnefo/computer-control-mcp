"""Read-only stdio protocol smoke check, also checks the published tool schema."""
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server = Path(__file__).with_name('server.py')
    params = StdioServerParameters(command=sys.executable, args=['-X','utf8','-B',str(server)],
                                  env={**os.environ, 'PYTHONUTF8':'1'})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = sorted(t.name for t in (await session.list_tools()).tools)
            assert len(names) == 9, names
            status = await session.call_tool('computer_status', {})
            assert not status.is_error, status
            windows = await session.call_tool('computer_windows', {})
            assert not windows.is_error, windows
            print(json.dumps({'ok':True,'tools':names,'status_ok':True,'windows_ok':True}))


if __name__ == '__main__':
    asyncio.run(main())
