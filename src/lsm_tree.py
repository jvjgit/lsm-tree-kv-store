from typing import Any

from memtable import Memtable
from wal import WAL

class LSMTree:

    def __init__(self, path: str) -> None:
        self._memtable = Memtable()
        self._wal = WAL(path)
        self._wal.replay(self._memtable)
    
    def put(self, key: str, value: Any) -> None:
        self._wal.log_put(key, value)
        self._memtable.put(key, value)
    
    def delete(self, key: str) -> None:
        self._wal.log_delete(key)
        self._memtable.delete(key)

    def get(self, key: str) -> Any:
        return self._memtable.get(key)
    
    
