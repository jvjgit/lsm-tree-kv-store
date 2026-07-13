import json

import pytest

from lsm_tree import LSMTree
from memtable import KeyDeletedError, KeyNotFoundError


def test_crash_recovery_clean_writes(tmp_path):
    wal_path = str(tmp_path / "test.wal")

    # before crash phase
    tree = LSMTree(wal_path)
    tree.put("a", 1)
    tree.put("b", 2)
    tree.put("c", 3)
    tree.delete("b")

    # simulate a crash: no clean shutdown, no explicit close/flush call,
    # just discard the object and let a new process pick up the WAL later
    del tree

    # after crash phase 
    recovered = LSMTree(wal_path)

    assert recovered.get("a") == 1
    assert recovered.get("c") == 3

    with pytest.raises(KeyDeletedError):
        recovered.get("b")

    with pytest.raises(KeyNotFoundError):
        recovered.get("never_written")


def test_crash_recovery_with_truncated_last_record(tmp_path):
    wal_path = str(tmp_path / "test.wal")

    # write some good records via the normal API
    tree = LSMTree(wal_path)
    tree.put("x", 10)
    tree.put("y", 20)
    del tree

    # now simulate a crash mid-write: append a truncated, invalid JSON
    # line directly to the file, bypassing log_put entirely
    with open(wal_path, "a", encoding="utf-8") as f:
        f.write('{"op": "put", "key": "z", "valu')  # deliberately cut off, no newline

    # replay should discard the broken trailing record and recover everything before it
    recovered = LSMTree(wal_path)

    assert recovered.get("x") == 10
    assert recovered.get("y") == 20

    with pytest.raises(KeyNotFoundError):
        recovered.get("z")


def test_crash_recovery_with_corruption_mid_file_raises(tmp_path):
    wal_path = str(tmp_path / "test.wal")

    # hand-craft a WAL file with a bad record in the MIDDLE, not the end
    with open(wal_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"op": "put", "key": "a", "value": 1}) + "\n")
        f.write("not valid json at all\n")
        f.write(json.dumps({"op": "put", "key": "b", "value": 2}) + "\n")

    with pytest.raises(ValueError):
        LSMTree(wal_path)