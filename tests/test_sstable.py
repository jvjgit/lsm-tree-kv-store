import json

import pytest

from memtable import Memtable, KeyDeletedError, KeyNotFoundError
from sstable import SSTable


def test_flush_and_lookup_mixed_puts_and_delete(tmp_path):
    memtable = Memtable()
    memtable.put("a", 1)
    memtable.put("b", 2)
    memtable.delete("b")
    memtable.put("c", 3)

    path = str(tmp_path / "test.sst")
    SSTable(path).flush_memtable(memtable)

    # fresh instance, proves we're reading from disk, not memory
    sstable = SSTable(path)

    assert sstable.get("a") == 1
    assert sstable.get("c") == 3

    with pytest.raises(KeyDeletedError):
        sstable.get("b")

    with pytest.raises(KeyNotFoundError):
        sstable.get("never_written")


def test_flushing_empty_memtable_does_not_crash(tmp_path):
    memtable = Memtable()
    path = str(tmp_path / "empty.sst")

    SSTable(path).flush_memtable(memtable)  # should not raise

    sstable = SSTable(path)
    with pytest.raises(KeyNotFoundError):
        sstable.get("anything")


def test_flushed_file_is_sorted_by_key(tmp_path):
    memtable = Memtable()
    # insert deliberately out of order
    memtable.put("zebra", 1)
    memtable.put("apple", 2)
    memtable.put("mango", 3)

    path = str(tmp_path / "sorted.sst")
    SSTable(path).flush_memtable(memtable)

    with open(path, "r", encoding="utf-8") as f:
        keys_on_disk = [json.loads(line)["key"] for line in f]

    assert keys_on_disk == sorted(keys_on_disk)
    assert keys_on_disk == ["apple", "mango", "zebra"]