"""Quarantaine : deplace les fichiers infectes hors de portee et permet de les restaurer.

Chaque fichier est stocke XOR-encode (pour qu'il ne soit plus executable ni
re-detecte par d'autres antivirus), avec un fichier .json decrivant son origine.
"""

import json
import time
import uuid
from pathlib import Path

DEFAULT_DIR = Path.home() / ".freeav" / "quarantine"
XOR_KEY = 0xA5


def _xor(data: bytes) -> bytes:
    return bytes(b ^ XOR_KEY for b in data)


class Quarantine:
    def __init__(self, directory: Path = DEFAULT_DIR):
        self.directory = Path(directory)

    def isolate(self, path: Path, threat: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        item_id = uuid.uuid4().hex
        path = Path(path).resolve()
        (self.directory / f"{item_id}.bin").write_bytes(_xor(path.read_bytes()))
        meta = {"original_path": str(path), "threat": threat, "date": time.time()}
        (self.directory / f"{item_id}.json").write_text(json.dumps(meta), encoding="utf-8")
        path.unlink()
        return item_id

    def list(self) -> list[dict]:
        items = []
        for meta_file in sorted(self.directory.glob("*.json")):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            items.append({"id": meta_file.stem, **meta})
        return items

    def restore(self, item_id: str) -> Path:
        meta_file = self.directory / f"{item_id}.json"
        blob = self.directory / f"{item_id}.bin"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        target = Path(meta["original_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_xor(blob.read_bytes()))
        blob.unlink()
        meta_file.unlink()
        return target

    def delete(self, item_id: str) -> None:
        for suffix in (".bin", ".json"):
            (self.directory / f"{item_id}{suffix}").unlink(missing_ok=True)
