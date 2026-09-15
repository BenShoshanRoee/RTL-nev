"""The only source of randomness in the Python bench layer.

- ``child_seed(root, namespace)``: SHA-256(f"{root}:{namespace}") -> first 4 bytes -> uint32.
- ``Rng``: sfc32, implemented identically in packages/core-semantic/src/rng.ts. Streams are
  byte-identical across the two languages; the shared fixture is
  packages/core-semantic/tests/fixtures/rng-parity.json, regenerated with
  ``uv run python -m rtlenv.rng --vectors``.

``random``, ``numpy.random``, ``uuid4`` and ``os.urandom`` are forbidden everywhere else
(bench/tests/test_no_unseeded_random.py and ruff S311).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
_M = 0xFFFFFFFF
_TWO32 = 1 << 32


def _assert_seed(seed: int, what: str = "seed") -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < _TWO32:
        raise ValueError(f"{what} must be an integer in [0, 2^32), got {seed!r}")


def sha256_hex(text: str) -> str:
    """SHA-256 of the UTF-8 encoding of ``text``, lowercase hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def child_seed(root: int, namespace: str) -> int:
    """Named child seed: SHA-256(f"{root}:{namespace}") -> first 4 bytes big-endian -> uint32."""
    _assert_seed(root, "root seed")
    return int.from_bytes(hashlib.sha256(f"{root}:{namespace}".encode()).digest()[:4], "big")


def seed_from_string(text: str) -> int:
    """A stable uint32 seed for a string such as a run id."""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")


class Rng:
    """sfc32. State from SHA-256 of the decimal seed, then 12 discarded outputs."""

    __slots__ = ("_a", "_b", "_c", "_d", "namespace", "seed")

    def __init__(self, seed: int, namespace: str = "root") -> None:
        _assert_seed(seed)
        self.seed = seed
        self.namespace = namespace
        digest = hashlib.sha256(str(seed).encode("ascii")).digest()
        self._a = int.from_bytes(digest[0:4], "big")
        self._b = int.from_bytes(digest[4:8], "big")
        self._c = int.from_bytes(digest[8:12], "big")
        self._d = int.from_bytes(digest[12:16], "big")
        for _ in range(12):
            self.next32()

    def next32(self) -> int:
        """Next value as an unsigned 32-bit integer."""
        a, b, c, d = self._a, self._b, self._c, self._d
        t = (a + b + d) & _M
        d = (d + 1) & _M
        a = b ^ (b >> 9)
        b = (c + ((c << 3) & _M)) & _M
        c = ((c << 21) & _M) | (c >> 11)
        c = (c + t) & _M
        self._a, self._b, self._c, self._d = a, b, c, d
        return t

    def float(self) -> float:  # noqa: A003 - mirrors the TypeScript API
        """Uniform in [0, 1) with 32 bits of resolution; exactly next32() / 2^32."""
        return self.next32() / 4294967296.0

    def int(self, min_inclusive: int, max_exclusive: int) -> int:  # noqa: A003
        """Uniform integer in [min, max_exclusive), unbiased by rejection sampling."""
        rng_range = max_exclusive - min_inclusive
        if rng_range < 1 or rng_range > _TWO32:
            raise ValueError(f"int() range must be in [1, 2^32], got {rng_range}")
        bound = _TWO32 - (_TWO32 % rng_range)
        u = self.next32()
        while u >= bound:
            u = self.next32()
        return min_inclusive + (u % rng_range)

    def bool(self, p: float = 0.5) -> bool:  # noqa: A003
        return self.float() < p

    def pick(self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("pick() of an empty sequence")
        return items[self.int(0, len(items))]

    def weighted(self, items: Sequence[T], weights: Sequence[float]) -> T:
        """Weighted choice; weights are summed in order so both languages see the same doubles."""
        if not items or len(items) != len(weights):
            raise ValueError("weighted() needs equal, non-empty items and weights")
        total = 0.0
        for w in weights:
            if not w >= 0:
                raise ValueError("weights must be non-negative numbers")
            total += w
        if total <= 0:
            raise ValueError("weights must not all be zero")
        x = self.float() * total
        acc = 0.0
        for item, w in zip(items, weights, strict=True):
            acc += w
            if x < acc:
                return item
        return items[-1]

    def shuffle(self, items: Sequence[T]) -> list[T]:
        """Fisher-Yates on a copy; the input is never mutated."""
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.int(0, i + 1)
            out[i], out[j] = out[j], out[i]
        return out

    def child(self, namespace: str) -> Rng:
        """A generator for a named sub-system, independent of every other namespace."""
        return Rng(child_seed(self.seed, namespace), f"{self.namespace}/{namespace}")


def _draws(seed: int, n: int, draw: Callable[[Rng], T]) -> list[T]:
    r = Rng(seed)
    return [draw(r) for _ in range(n)]


def parity_vectors() -> dict:
    """The cross-language fixture. Any change here must be mirrored by the TypeScript tests."""
    root = 20260915
    namespaces = [f"ns-{i}" for i in range(1000)]
    streams = [
        {
            "seed": seed,
            "next32": _draws(seed, 200, lambda r: r.next32()),
            "float": _draws(seed, 200, lambda r: r.float()),
            "int_0_1000": _draws(seed, 200, lambda r: r.int(0, 1000)),
            "shuffle_10": Rng(seed).shuffle(list(range(10))),
            "weighted": _draws(seed, 200, lambda r: r.weighted([0, 1, 2], [0.5, 0.3, 0.2])),
        }
        for seed in (0, 12345, 4294967295)
    ]
    return {
        "generated_by": "uv run python -m rtlenv.rng --vectors",
        "sha256": {
            "": sha256_hex(""),
            "abc": sha256_hex("abc"),
            "20260915:catalog": sha256_hex("20260915:catalog"),
            "שלום עולם": sha256_hex("שלום עולם"),
            "مرحبا": sha256_hex("مرحبا"),
        },
        "child_seeds": {
            "root": root,
            "namespaces": namespaces,
            "seeds": [child_seed(root, ns) for ns in namespaces],
        },
        "streams": streams,
    }


if __name__ == "__main__":
    if sys.argv[1:] == ["--vectors"]:
        json.dump(parity_vectors(), sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        sys.exit("usage: python -m rtlenv.rng --vectors")
