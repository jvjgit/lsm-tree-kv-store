import pytest

from memtable import Memtable, KeyDeletedError, KeyNotFoundError


def test_get_on_empty_memtable_raises_not_found():
    memtable = Memtable()
    with pytest.raises(KeyNotFoundError):
        memtable.get("missing")


def test_put_then_get_returns_value():
    memtable = Memtable()
    memtable.put("a", 1)
    assert memtable.get("a") == 1


def test_put_then_delete_then_get_raises_deleted():
    memtable = Memtable()
    memtable.put("a", 1)
    memtable.delete("a")
    with pytest.raises(KeyDeletedError):
        memtable.get("a")


def test_delete_on_never_written_key_still_raises_deleted():
    # deleting a key that was never put still writes a tombstone —
    # this matters because the memtable can't know whether an older
    # SSTable already has a value for this key
    memtable = Memtable()
    memtable.delete("never_written")
    with pytest.raises(KeyDeletedError):
        memtable.get("never_written")


def test_delete_then_put_resurrects_key():
    memtable = Memtable()
    memtable.delete("a")
    memtable.put("a", "resurrected")
    assert memtable.get("a") == "resurrected"


def test_put_twice_overwrites_value():
    memtable = Memtable()
    memtable.put("a", 1)
    memtable.put("a", 2)
    assert memtable.get("a") == 2


def test_size_increments_only_on_new_keys():
    memtable = Memtable()
    assert memtable.size() == 0

    memtable.put("a", 1)
    assert memtable.size() == 1

    memtable.put("a", 2)  # overwrite, not a new key
    assert memtable.size() == 1

    memtable.put("b", 1)
    assert memtable.size() == 2

    memtable.delete("b")  # already exists, delete doesn't add a new slot
    assert memtable.size() == 2

    memtable.delete("c")  # brand new key, tombstone IS a new slot
    assert memtable.size() == 3

    memtable.delete("c")  # deleting an already-deleted key again, no change
    assert memtable.size() == 3


def test_falsy_values_are_distinguishable_from_missing():
    # the whole reason get() raises exceptions instead of returning None:
    # a real value of None/0/"" must never be confused with "not found"
    memtable = Memtable()
    memtable.put("a", None)
    memtable.put("b", 0)
    memtable.put("c", "")

    assert memtable.get("a") is None
    assert memtable.get("b") == 0
    assert memtable.get("c") == ""

    with pytest.raises(KeyNotFoundError):
        memtable.get("never_written")