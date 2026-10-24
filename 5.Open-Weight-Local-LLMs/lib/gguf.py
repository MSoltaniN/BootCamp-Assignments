"""Read-only GGUF metadata parser (no tensor data is loaded).

Only the header, the key/value metadata block and the tensor descriptor table are
read. That is enough for sections 7.10 - 7.12 (magic, version, tensor count,
architecture, layer count, kv heads, embedding size, query heads).
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

GGUF_MAGIC = 0x46554747  # b"GGUF" read as a little-endian uint32

# gguf metadata value type ids -> (struct format char, byte size)
_SCALAR = {
    0: ("B", 1),   # uint8
    1: ("b", 1),   # int8
    2: ("H", 2),   # uint16
    3: ("h", 2),   # int16
    4: ("I", 4),   # uint32
    5: ("i", 4),   # int32
    6: ("f", 4),   # float32
    7: ("?", 1),   # bool
    10: ("Q", 8),  # uint64
    11: ("q", 8),  # int64
    12: ("d", 8),  # float64
}
_TYPE_STRING = 8
_TYPE_ARRAY = 9


class GGUFParser:
    """Sequential reader. Never mmaps or loads tensor payloads."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.fh = self.path.open("rb")
        self.size = self.path.stat().st_size

    # -- primitives ---------------------------------------------------------
    def _read(self, n: int) -> bytes:
        buf = self.fh.read(n)
        if len(buf) != n:
            raise EOFError(f"unexpected EOF in {self.path.name}")
        return buf

    def _u32(self) -> int:
        return struct.unpack("<I", self._read(4))[0]

    def _u64(self) -> int:
        return struct.unpack("<Q", self._read(8))[0]

    def _string(self) -> str:
        return self._read(self._u64()).decode("utf-8", errors="replace")

    def _value(self, vtype: int) -> Any:
        if vtype in _SCALAR:
            fmt, size = _SCALAR[vtype]
            return struct.unpack("<" + fmt, self._read(size))[0]
        if vtype == _TYPE_STRING:
            return self._string()
        if vtype == _TYPE_ARRAY:
            itype = self._u32()
            count = self._u64()
            # the tokenizer vocab is a 150k-element array; cap what we materialise
            cap = min(count, 512)
            vals = [self._value(itype) for _ in range(cap)]
            for _ in range(count - cap):
                self._skip(itype)
            if count > cap:
                return {"__array_truncated__": True, "count": count, "head": vals}
            return vals
        raise ValueError(f"unknown gguf value type {vtype}")

    def _skip(self, vtype: int) -> None:
        if vtype in _SCALAR:
            self._read(_SCALAR[vtype][1])
        elif vtype == _TYPE_STRING:
            self._read(self._u64())
        elif vtype == _TYPE_ARRAY:
            itype = self._u32()
            for _ in range(self._u64()):
                self._skip(itype)
        else:
            raise ValueError(f"unknown gguf value type {vtype}")

    # -- structure ----------------------------------------------------------
    def parse(self) -> dict:
        magic = self._u32()
        if magic != GGUF_MAGIC:
            raise ValueError(f"{self.path.name}: bad magic {magic:#010x}, expected 0x46554747")
        version = self._u32()
        tensor_count = self._u64()
        kv_count = self._u64()

        metadata: dict[str, Any] = {}
        for _ in range(kv_count):
            key = self._string()
            metadata[key] = self._value(self._u32())

        tensors = []
        for _ in range(tensor_count):
            name = self._string()
            n_dims = self._u32()
            dims = [self._u64() for _ in range(n_dims)]
            tensors.append({"name": name, "dims": dims, "type": self._u32(), "offset": self._u64()})

        return {
            "file": self.path.name,
            "bytes": self.size,
            "magic": f"0x{magic:08x}",
            "version": version,
            "tensor_count": tensor_count,
            "metadata_count": kv_count,
            "metadata": metadata,
            "tensor_heads": tensors[:5],
        }

    def close(self) -> None:
        self.fh.close()

    def __enter__(self) -> "GGUFParser":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def parse_gguf(path: Path) -> dict:
    with GGUFParser(path) as parser:
        return parser.parse()


def describe(info: dict) -> dict:
    """Extract exactly the fields section 7.10 - 7.12 asks for."""
    md = info["metadata"]
    arch = str(md.get("general.architecture", "unknown"))
    p = f"{arch}."

    def first(*keys: str, default=None):
        for key in keys:
            if key in md:
                return md[key]
        return default

    layers = first(p + "block_count")
    kv_heads = first(p + "attention.head_count_kv")
    q_heads = first(p + "attention.head_count")
    emb = first(p + "embedding_length")
    template = first(p + "chat_template", "tokenizer.chat_template", default="")
    vocab = first(p + "vocab_size")

    kv_per_layer = kv_heads
    if isinstance(kv_heads, list):
        kv_max = max((v for v in kv_heads if isinstance(v, int)), default=None)
    elif isinstance(kv_heads, dict):
        head = kv_heads.get("head", [])
        kv_max = max((v for v in head if isinstance(v, int)), default=None)
    else:
        kv_max = kv_heads

    head_dim = None
    if isinstance(emb, int) and isinstance(q_heads, int) and q_heads:
        head_dim = emb // q_heads

    return {
        "architecture": arch,
        "version": info["version"],
        "tensor_count": info["tensor_count"],
        "metadata_count": info["metadata_count"],
        "bytes": info["bytes"],
        "layers": layers,
        "kv_heads": kv_max,
        "kv_heads_by_layer": kv_per_layer,
        "query_heads": q_heads,
        "embedding": emb,
        "head_dim": head_dim,
        "context_length": first(p + "context_length"),
        "chat_template_present": bool(template),
        "chat_template_length": len(template) if isinstance(template, str) else 0,
        "chat_template": template if isinstance(template, str) else "",
        "vocab_size": vocab,
        "file_type": first("general.file_type"),
        "name": first("general.name"),
    }
