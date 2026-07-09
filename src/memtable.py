from typing import Any, Optional

from sortedcontainers import SortedDict

class KeyNotFoundError(KeyError):
    """Raised when a key was never written to this memtable."""


class KeyDeletedError(KeyError):
    """Raised when a key exists but has been tombstoned (deleted)."""

class Memtable:
    _TOMBSTONE = object() #using sentinal object to represent a deleted item instead of a wrapper

    def __init__(self) -> None:
        self._data = SortedDict() #empty memtable intialised
        self._size = 0 #counting the entries
    
    def put(self, key, value) -> None:
        if key not in self._data:
            self._size += 1
        self._data[key] = value
    
    def delete(self, key) -> None:
        if key not in self._data:
            self._size += 1 #increment size since creating new entry
        self._data[key] = self._TOMBSTONE #cant just delete from self dict because you need to delete from the actual disc so this basically records that 

    def get(self, key) -> Any:
        if key not in self._data:
            raise KeyNotFoundError(key)
        value = self._data[key]
        if value is self._TOMBSTONE:
            raise KeyDeletedError(key)
        return value

    def size(self) -> int:
        return self._size
