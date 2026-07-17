import pytest

from lsm_tree import LSMTree
from memtable import KeyDeletedError, KeyNotFoundError


def make_tree(tmp_path, max_memtable_size=1000):
    wal_path = str(tmp_path / "test.wal")
    sstable_dir = str(tmp_path / "sstables")
    return LSMTree(wal_path, sstable_dir, max_memtable_size=max_memtable_size)


def test_get_from_memtable_without_flush(tmp_path):
    tree = make_tree(tmp_path)
    tree.put("a", 1)
    assert tree.get("a") == 1


def test_get_after_single_flush_reads_from_sstable(tmp_path):
    # small threshold so we can force a flush without writing thousands of keys
    tree = make_tree(tmp_path, max_memtable_size=2)

    tree.put("a", 1)
    tree.put("b", 2)  # hits threshold (size 2), triggers a flush here

    # memtable should now be empty/fresh; "a" must come from the SSTable
    assert tree._memtable.size() == 0
    assert tree.get("a") == 1
    assert tree.get("b") == 2


def test_memtable_value_wins_over_older_sstable(tmp_path):
    tree = make_tree(tmp_path, max_memtable_size=2)

    tree.put("x", "old")
    tree.put("filler", "irrelevant")  # forces a flush, "x": "old" goes to disk

    tree.put("x", "new")  # fresh memtable, most recent write

    assert tree.get("x") == "new"


def test_newer_sstable_wins_over_older_sstable(tmp_path):
    tree = make_tree(tmp_path, max_memtable_size=2)

    tree.put("x", "v1")
    tree.put("filler1", "a")  # flush #1: x=v1 goes to sstable_000001

    tree.put("x", "v2")
    tree.put("filler2", "b")  # flush #2: x=v2 goes to sstable_000002

    # memtable is empty again; both sstables have "x" — newest must win
    assert tree._memtable.size() == 0
    assert tree.get("x") == "v2"


def test_tombstone_shadows_older_sstable_value(tmp_path):
    tree = make_tree(tmp_path, max_memtable_size=2)

    tree.put("x", "v1")
    tree.put("filler", "a")  # flush #1: x=v1 durably on disk

    tree.delete("x")  # tombstone lands in the fresh memtable

    with pytest.raises(KeyDeletedError):
        tree.get("x")


def test_tombstone_in_older_sstable_shadows_even_older_value(tmp_path):
    tree = make_tree(tmp_path, max_memtable_size=2)

    tree.put("x", "v1")
    tree.put("filler1", "a")  # flush #1: x=v1

    tree.delete("x")
    tree.put("filler2", "b")  # flush #2: tombstone for x

    tree.put("filler3", "c")
    tree.put("filler4", "d")  # flush #3: forces memtable empty again

    with pytest.raises(KeyDeletedError):
        tree.get("x")


def test_full_restart_recovers_sstable_and_wal_state(tmp_path):
    wal_path = str(tmp_path / "test.wal")
    sstable_dir = str(tmp_path / "sstables")

    tree = LSMTree(wal_path, sstable_dir, max_memtable_size=2)
    tree.put("flushed_key", "on_disk")
    tree.put("filler", "forces_flush")  # this pair triggers a flush

    tree.put("wal_only_key", "still_in_memtable")  # not yet flushed

    del tree  # simulate a crash: no clean shutdown

    recovered = LSMTree(wal_path, sstable_dir, max_memtable_size=2)

    # this one must come from the reconstructed SSTable list
    assert recovered.get("flushed_key") == "on_disk"
    # this one must come from WAL replay into the fresh memtable
    assert recovered.get("wal_only_key") == "still_in_memtable"

    with pytest.raises(KeyNotFoundError):
        recovered.get("never_written")