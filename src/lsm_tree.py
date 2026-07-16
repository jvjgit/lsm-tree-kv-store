from typing import Any
import os 
from memtable import Memtable
from wal import WAL
from sstable import SSTable

class LSMTree:

    def __init__(self, wal_path: str, sstable_dir: str, max_memtable_size: int = 1000) -> None:
        self._memtable = Memtable()
        self._wal = WAL(wal_path)
        self._wal.replay(self._memtable)
        self._max_memtable_size = max_memtable_size
        self._sstable_dir = sstable_dir
        os.makedirs(self._sstable_dir, exist_ok = True)
        self._sstable_counter = 0
        self._sstables = []
        existing_filenames = os.listdir(self._sstable_dir) #to check if existing files in directory 
        sorted_filenames = sorted(existing_filenames)
        for filename in sorted_filenames:
            full_path = os.path.join(self._sstable_dir, filename)
            self._sstables.append(full_path)
            self._sstable_counter += 1
  


    def put(self, key: str, value: Any) -> None:
        self._wal.log_put(key, value)
        self._memtable.put(key, value)
        if self._memtable.size() >= self._max_memtable_size :
            self._flush()
    
    def delete(self, key: str) -> None:
        self._wal.log_delete(key)
        self._memtable.delete(key)
        if self._memtable.size() >= self._max_memtable_size :
            self._flush()

    def get(self, key: str) -> Any:
        return self._memtable.get(key)
    
    def _next_sstable_path(self) -> str:
        self._sstable_counter += 1
        filename = "sstable_" + str(self._sstable_counter).zfill(6) + ".db"
        path = os.path.join(self._sstable_dir, filename)
        return path 
    
    def _flush(self) -> None:
        path = self._next_sstable_path()
        new_sstable = SSTable(path)
        new_sstable.flush_memtable(self._memtable)
        self._sstables.append(path)
        self._memtable = Memtable() #order matters, flush memtable first create new one and then rotate the wal
        self._wal.rotate()
        
    
    
