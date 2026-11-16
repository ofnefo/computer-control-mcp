"""Cross-process cooperative leases. A live operation cannot be stolen after TTL."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time


class Busy(RuntimeError):
    pass


class Leases:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS leases (resource TEXT PRIMARY KEY, owner TEXT, token TEXT, deadline REAL, identity TEXT)')

    @contextlib.contextmanager
    def db(self):
        connection = sqlite3.connect(self.root / 'leases.sqlite3', timeout=3)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextlib.contextmanager
    def mutex(self, resource):
        """OS releases the byte lock on crash; files are never unlinked (no ABA race)."""
        path = self.root / (hashlib.sha256(resource.encode()).hexdigest() + '.lock')
        with open(path, 'a+b') as stream:
            stream.seek(0, 2)
            if not stream.tell():
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    raise Busy('OPERATION_BUSY: another operation is still running') from None
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    raise Busy('OPERATION_BUSY: another operation is still running') from None
                try:
                    yield
                finally:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def acquire(self, resource, owner, identity, ttl=120):
        if not owner or len(owner) > 100 or not 5 <= ttl <= 300:
            raise ValueError('owner required; TTL must be 5..300 seconds')
        with self.mutex(resource), self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT owner,deadline FROM leases WHERE resource=?', (resource,)).fetchone()
            if row and row[1] > time.time():
                raise Busy(f'LEASE_BUSY: {resource} held by {row[0]} until {row[1]}')
            token = secrets.token_hex(24)
            deadline = time.time() + ttl
            db.execute('INSERT OR REPLACE INTO leases VALUES (?,?,?,?,?)',
                       (resource, owner, token, deadline, json.dumps(identity, sort_keys=True)))
        return dict(resource=resource, owner=owner, token=token, deadline=deadline)

    def require(self, resource, owner, token, identity=None):
        with self.db() as db:
            row = db.execute('SELECT owner,token,deadline,identity FROM leases WHERE resource=?', (resource,)).fetchone()
        if not row or row[0] != owner or not secrets.compare_digest(row[1], token) or row[2] <= time.time():
            raise Busy('LEASE_REQUIRED: acquire an unexpired lease with this owner and token')
        if identity is not None and json.loads(row[3]) != identity:
            raise Busy('WINDOW_CHANGED: process/window identity changed; release and attach again')
        return json.loads(row[3])

    @contextlib.contextmanager
    def operation(self, resource, owner, token, identity=None):
        with self.mutex(resource):
            self.require(resource, owner, token, identity)
            yield

    def renew(self, resource, owner, token, ttl=120):
        if not 5 <= ttl <= 300:
            raise ValueError('TTL must be 5..300 seconds')
        with self.operation(resource, owner, token), self.db() as db:
            deadline = time.time() + ttl
            db.execute('UPDATE leases SET deadline=? WHERE resource=?', (deadline, resource))
        return dict(resource=resource, deadline=deadline)

    def release(self, resource, owner, token):
        with self.mutex(resource), self.db() as db:
            # Expiry does not prevent the original owner cleaning up; a replaced token does.
            row = db.execute('SELECT owner,token FROM leases WHERE resource=?', (resource,)).fetchone()
            if not row or row[0] != owner or not secrets.compare_digest(row[1], token):
                raise Busy('NOT_OWNER: cannot release another lease')
            db.execute('DELETE FROM leases WHERE resource=?', (resource,))
        return dict(released=resource)

    def status(self):
        with self.db() as db:
            rows = db.execute('SELECT resource,owner,deadline FROM leases').fetchall()
        return [dict(resource=r, owner=o, deadline=d, expired=d <= time.time()) for r,o,d in rows]
