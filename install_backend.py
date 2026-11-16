"""Install the pinned Windows x64 backend after verifying its release checksum."""
import hashlib
import io
from pathlib import Path
import platform
import tarfile
import urllib.request

URL = 'https://github.com/vercel-labs/agent-desktop/releases/download/v1.2.0/agent-desktop-v1.2.0-x86_64-pc-windows-msvc.tar.gz'
SHA256 = 'a4199f741a441cedd349bf56c5eba01783b1261258b498efeb7ec9945220c3e8'


def main():
    if platform.system() != 'Windows' or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise SystemExit('This installer supports Windows x64 only.')
    target = Path(__file__).resolve().parent / 'vendor' / 'agent-desktop.exe'
    if target.exists():
        raise SystemExit('Backend already exists; no file was overwritten.')
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(10 * 1024 * 1024 + 1)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('Checksum mismatch; nothing installed.')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name == 'agent-desktop.exe']
        if len(members) != 1:
            raise SystemExit('Unexpected release layout; nothing installed.')
        with archive.extractfile(members[0]) as source:
            binary = source.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        output.write(binary)
    print(f'Installed agent-desktop 1.2.0: {target}')


if __name__ == '__main__':
    main()
