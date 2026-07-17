import json

import pytest

from lsm_tree import LSMTree
from memtable import KeyDeletedError, KeyNotFoundError


def make_tree(tmp_path):
    wal_path = str(tmp_path / "test.wal")
    sstable_dir = str(tmp_path / "sstables")
    return LSMTree(wal_path, sstable_dir)


def test_crash_recovery_clean_writes(tmp_path):
    # --- "before crash" phase ---
    tree = make_tree(tmp_path)
    tree.put("a", 1)
    tree.put("b", 2)
    tree.put("c", 3)
    tree.delete("b")

    del tree

    # --- "after crash" phase ---
    recovered = make_tree(tmp_path)

    assert recovered.get("a") == 1
    assert recovered.get("c") == 3

    with pytest.raises(KeyDeletedError):
        recovered.get("b")

    with pytest.raises(KeyNotFoundError):
        recovered.get("never_written")


def test_crash_recovery_with_truncated_last_record(tmp_path):
    tree = make_tree(tmp_path)
    tree.put("x", 10)
    tree.put("y", 20)
    del tree

    wal_path = str(tmp_path / "test.wal")
    with open(wal_path, "a", encoding="utf-8") as f:
        f.write('{"op": "put", "key": "z", "valu')  # deliberately truncated

    recovered = make_tree(tmp_path)

    assert recovered.get("x") == 10
    assert recovered.get("y") == 20

    with pytest.raises(KeyNotFoundError):
        recovered.get("z")


def test_crash_recovery_with_corruption_mid_file_raises(tmp_path):
    wal_path = str(tmp_path / "test.wal")

    with open(wal_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"op": "put", "key": "a", "value": 1}) + "\n")
        f.write("not valid json at all\n")
        f.write(json.dumps({"op": "put", "key": "b", "value": 2}) + "\n")

    with pytest.raises(ValueError):
        make_tree(tmp_path)