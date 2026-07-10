import json
import os
from typing import Any, TextIO
from memtable import Memtable


class WAL:

    def __init__(self, path: str) -> None:
        self.path = path
        self._file = open(self.path, "a", encoding = "utf-8")

    def log_put(self, key: str, value: Any) -> None:
        self._append({"op": "put", "key": key, "value": value})
    
    def log_delete(self, key: str) -> None:
        self._append({"op": "delete", "key": key, "value": None})

    def replay(self, memtable: Memtable) -> None:
        with open(self.path, "r", encoding = "utf-8") as f:
            lines = f.readlines()
        
        i = 0
        for raw_line in lines:
            is_last_line = i == len(lines) - 1
            stripped = raw_line.strip()
            if not stripped:
                i += 1
                continue 
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                if is_last_line:
                    break 
                raise ValueError(
                    f"corrupt WAL record on line {i + 1} of {self.path}: {raw_line!r}"
                )
            
            self._apply(record, memtable)

            i += 1

    def _append(self, record: dict) -> None:
        newLine = json.dumps(record) + "\n" 
        self._file.write(newLine)
        self._file.flush() #from pythons internal buffer to the os
        os.fsync(self._file.fileno()) #from the os to the actual disk
    

    def _apply(self, record: dict, memtable: Memtable) -> None:
        op = record["op"]
        key = record["key"]

        if op == "put":
            memtable.put(key, record["value"])
        elif op == "delete":
            memtable.delete(key)
        else:
            raise ValueError(f"unknown WAL operation: {op!r}")
    
    def rotate(self) -> None:
        self._file.close()
        os.remove(self.path)
        self._file = open(self.path, "a", encoding="utf-8")