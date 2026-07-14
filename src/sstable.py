from memtable import Memtable, KeyDeletedError, KeyNotFoundError
import json 
import os 
from typing import Any 



class SSTable:

    def __init__(self, path: str) -> None:
        self.path = path

    def flush_memtable(self, memtable: Memtable) -> None:
        with open(self.path, "w", encoding = "utf-8") as f:
            for key,value in memtable.items():
                is_deleted = memtable.is_tombstone(value)
                record = {
                    "key": key,
                    "value": value if not is_deleted else None,
                    "deleted": is_deleted
                }
                f.write(json.dumps(record) + "\n")
        
            f.flush()
            os.fsync(f.fileno())

    def get(self, key) -> Any:
        found_record = None 
        with open(self.path, "r") as f:
            for line in f:
                record = json.loads(line)
                if record["key"] == key:
                    found_record = record
                    break
        if found_record is None:
            raise KeyNotFoundError(key)
        if found_record["deleted"]:
            raise KeyDeletedError(key)
        else:
            return found_record["value"]