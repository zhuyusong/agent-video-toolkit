"""Content identities, atomic state and process-owned locks."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import portalocker

MAX_JSON_BYTES = 16 * 1024 * 1024


class InputError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise InputError("JSON exceeds 16 MiB")
    return json.loads(path.read_text("utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(InputError("Non-finite JSON")))


def atomic_json(path, value):
    path = Path(path)
    data = canonical(value)
    if len(data) > MAX_JSON_BYTES:
        raise InputError("JSON exceeds 16 MiB; no state was committed")
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value):
        raise InputError("Invalid identifier")
    return value


def confined(root, *parts):
    root = Path(root).resolve()
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root):
        raise InputError("Path escapes runtime")
    # Reject links/junctions inside the runtime, even when they point inward.
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise InputError("Linked runtime paths are unsupported")
    return path


@contextmanager
def locked(folder, name="state", timeout=5):
    path = confined(folder, name + ".lock")
    try:
        with portalocker.Lock(str(path), mode="a+b", timeout=timeout):
            yield
    except portalocker.exceptions.LockException as exc:
        raise InputError("Operation busy; query the existing run") from exc
