"""Sandbox compatibility shim (Windows / DSH workspace-write).

Problem: inside this sandbox a directory created by ``tempfile.mkdtemp()`` is not
writable by the creating process (its inherited ACL is dropped), while a
directory created by ``os.mkdir``/``os.makedirs`` without a POSIX mode argument
works normally. pip, ``ensurepip`` and huggingface_hub all use ``mkdtemp`` for
unpack/build/target dirs, so they fail with ``PermissionError: [Errno 13]``.

Fix: replace ``tempfile.mkdtemp`` with an ``os.makedirs``-based implementation
with the same semantics (random name, same prefix/suffix/dir contract). Nothing
outside the process is changed and no privileges are widened.

Used by ``sandbox_pip.py`` and ``sandbox_run.py``; harmless outside the sandbox.
"""

from __future__ import annotations

import os
import random
import string
import tempfile

_ALPHABET = string.ascii_lowercase + string.digits
_ORIGINAL = tempfile.mkdtemp
_patched = False


def mkdtemp_sandbox_safe(suffix: str | None = None, prefix: str | None = None, dir: str | None = None) -> str:
    prefix = "tmp" if prefix is None else prefix
    suffix = "" if suffix is None else suffix
    base = dir or tempfile.gettempdir()
    for _ in range(10000):
        candidate = os.path.join(base, prefix + "".join(random.choices(_ALPHABET, k=8)) + suffix)
        try:
            os.makedirs(candidate)  # no mode= argument -> ACL is inherited
            return candidate
        except FileExistsError:
            continue
    return _ORIGINAL(suffix=suffix, prefix=prefix, dir=dir)


def patch_mkdtemp() -> None:
    global _patched
    if not _patched:
        tempfile.mkdtemp = mkdtemp_sandbox_safe
        _patched = True


def works() -> bool:
    """True when the plain mkdtemp already behaves (non-sandboxed machine)."""
    try:
        d = _ORIGINAL()
    except OSError:
        return False
    try:
        probe = os.path.join(d, "probe.bin")
        with open(probe, "wb") as fh:
            fh.write(b"x")
        return True
    except OSError:
        return False
    finally:
        try:
            import shutil

            shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
