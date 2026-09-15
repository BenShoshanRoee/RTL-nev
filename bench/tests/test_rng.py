"""Determinism contract for rtlenv.rng. The fixture is shared with the TypeScript suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rtlenv.rng import Rng, child_seed, seed_from_string, sha256_hex

FIXTURE = Path(__file__).resolve().parents[2] / (
    "packages/core-semantic/tests/fixtures/rng-parity.json"
)
PARITY = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_sha256_known_vectors() -> None:
    assert sha256_hex("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_hex("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    for text, hexdigest in PARITY["sha256"].items():
        assert sha256_hex(text) == hexdigest


def test_child_seed_matches_fixture_for_1000_namespaces() -> None:
    cs = PARITY["child_seeds"]
    assert len(cs["namespaces"]) == 1000
    assert [child_seed(cs["root"], ns) for ns in cs["namespaces"]] == cs["seeds"]


def test_child_seed_is_uint32_and_depends_on_both_inputs() -> None:
    a = child_seed(1, "catalog")
    assert 0 <= a < 2**32
    assert child_seed(2, "catalog") != a
    assert child_seed(1, "copy") != a
    with pytest.raises(ValueError):
        child_seed(-1, "x")
    with pytest.raises(ValueError):
        child_seed(2**32, "x")


def test_streams_match_fixture() -> None:
    for s in PARITY["streams"]:
        assert [Rng(s["seed"]).next32() for _ in range(0)] == []
        r = Rng(s["seed"])
        assert [r.next32() for _ in s["next32"]] == s["next32"]
        r = Rng(s["seed"])
        assert [r.float() for _ in s["float"]] == s["float"]
        r = Rng(s["seed"])
        assert [r.int(0, 1000) for _ in s["int_0_1000"]] == s["int_0_1000"]
        assert Rng(s["seed"]).shuffle(list(range(10))) == s["shuffle_10"]
        r = Rng(s["seed"])
        assert [r.weighted([0, 1, 2], [0.5, 0.3, 0.2]) for _ in s["weighted"]] == s["weighted"]


@pytest.mark.parametrize("seed", [0, 12345, 4294967295])
def test_same_seed_same_output(seed: int) -> None:
    a, b = Rng(seed), Rng(seed)
    assert [a.next32() for _ in range(100)] == [b.next32() for _ in range(100)]


def test_different_seed_different_output() -> None:
    a, b = Rng(1), Rng(2)
    assert [a.next32() for _ in range(8)] != [b.next32() for _ in range(8)]


def test_isolation_between_namespaces() -> None:
    root = Rng(777)
    b1 = [root.child("B").next32() for _ in range(50)]
    a = root.child("A")
    for _ in range(1000):
        a.next32()
    assert [root.child("B").next32() for _ in range(50)] == b1


def test_int_range_and_float_interval() -> None:
    r = Rng(9)
    seen = set()
    for _ in range(5000):
        v = r.int(-3, 3)
        assert -3 <= v < 3
        seen.add(v)
        f = r.float()
        assert 0.0 <= f < 1.0
    assert seen == {-3, -2, -1, 0, 1, 2}
    with pytest.raises(ValueError):
        r.int(5, 5)


def test_shuffle_is_a_permutation_and_pure() -> None:
    src = [1, 2, 3, 4, 5]
    out = Rng(3).shuffle(src)
    assert src == [1, 2, 3, 4, 5]
    assert sorted(out) == src


def test_order_independence() -> None:
    ids = ["c", "a", "b"]
    forward = {i: Rng(child_seed(42, i)).next32() for i in ids}
    reverse = {i: Rng(child_seed(42, i)).next32() for i in reversed(ids)}
    assert forward == reverse


def test_seed_from_string_stable() -> None:
    assert seed_from_string("run-2026-09-15") == seed_from_string("run-2026-09-15")
    assert seed_from_string("a") != seed_from_string("b")
