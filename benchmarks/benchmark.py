"""
Benchmark script for the LSM-tree key-value store.

Measures:
1. Write throughput: LSMTree vs a naive "in-place update" file store
   (simulating the random-write pattern a B-tree-style engine does).
2. Read latency degradation as more SSTables accumulate (no compaction).

Run from the project root with the venv active:
    python benchmarks/benchmark.py
"""

import json
import os
import random
import shutil
import sqlite3
import string
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lsm_tree import LSMTree  # noqa: E402


def random_key(n: int) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def random_value(n: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))



# Baseline 1: naive in-place file store — one JSON file, rewritten on every
# single write, to simulate the cost of random in-place updates (the thing
# LSM-trees are specifically designed to avoid).

class NaiveInPlaceStore:
    def __init__(self, path: str) -> None:
        self.path = path
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({}, f)

    def put(self, key: str, value) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data[key] = value
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())



# Baseline 2: sqlite3 (stdlib) as a "real database" reference point.

class SqliteStore:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()

    def put(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()  # commit per write, fair comparison to fsync-per-write


def benchmark_write_throughput(num_writes: int, tmp_dir: str) -> None:
    print(f"\n=== Write throughput ({num_writes} puts) ===")
    keys = [random_key(10) for _ in range(num_writes)]
    values = [random_value(50) for _ in range(num_writes)]

    # LSMTree
    lsm_dir = os.path.join(tmp_dir, "lsm")
    os.makedirs(lsm_dir, exist_ok=True)
    tree = LSMTree(
        wal_path=os.path.join(lsm_dir, "wal.log"),
        sstable_dir=os.path.join(lsm_dir, "sstables"),
        max_memtable_size=200,
    )
    start = time.perf_counter()
    for k, v in zip(keys, values):
        tree.put(k, v)
    lsm_elapsed = time.perf_counter() - start
    print(f"LSMTree:              {lsm_elapsed:.3f}s  ({num_writes / lsm_elapsed:.0f} puts/sec)")

    # Naive in-place store
    naive_path = os.path.join(tmp_dir, "naive.json")
    naive = NaiveInPlaceStore(naive_path)
    start = time.perf_counter()
    for k, v in zip(keys, values):
        naive.put(k, v)
    naive_elapsed = time.perf_counter() - start
    print(f"Naive in-place store: {naive_elapsed:.3f}s  ({num_writes / naive_elapsed:.0f} puts/sec)")

    # sqlite3
    sqlite_path = os.path.join(tmp_dir, "bench.db")
    sqlite_store = SqliteStore(sqlite_path)
    start = time.perf_counter()
    for k, v in zip(keys, values):
        sqlite_store.put(k, v)
    sqlite_elapsed = time.perf_counter() - start
    print(f"sqlite3 (commit/write): {sqlite_elapsed:.3f}s  ({num_writes / sqlite_elapsed:.0f} puts/sec)")

    print(f"\nLSMTree was {naive_elapsed / lsm_elapsed:.1f}x faster than the naive in-place store.")


def benchmark_read_degradation(num_flushes: int, keys_per_flush: int, tmp_dir: str) -> None:
    print(f"\n=== Read latency vs. number of SSTables (no compaction) ===")
    lsm_dir = os.path.join(tmp_dir, "lsm_read")
    os.makedirs(lsm_dir, exist_ok=True)
    tree = LSMTree(
        wal_path=os.path.join(lsm_dir, "wal.log"),
        sstable_dir=os.path.join(lsm_dir, "sstables"),
        max_memtable_size=keys_per_flush,
    )

    # write the very first key, then force it into the OLDEST sstable by
    # filling up subsequent memtables with filler until we've triggered
    # num_flushes flushes total. we'll then measure how long it takes to
    # look up that first key once it's buried behind N-1 newer sstables.
    target_key = "the_oldest_key"
    tree.put(target_key, "original_value")

    for flush_num in range(num_flushes):
        for _ in range(keys_per_flush):
            tree.put(random_key(10), random_value(20))

        num_sstables_so_far = len(tree._sstables)
        start = time.perf_counter()
        for _ in range(50):  # repeat lookups to get a stable average
            tree.get(target_key)
        elapsed = (time.perf_counter() - start) / 50
        print(f"  {num_sstables_so_far:2d} SSTables on disk -> avg get() latency: {elapsed * 1000:.4f} ms")


def main() -> None:
    tmp_dir = "benchmark_tmp"
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)

    try:
        benchmark_write_throughput(num_writes=2000, tmp_dir=tmp_dir)
        benchmark_read_degradation(num_flushes=15, keys_per_flush=50, tmp_dir=tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()