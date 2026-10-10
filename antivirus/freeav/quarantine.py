"""Quarantaine : deplace les fichiers infectes hors de portee et permet de les restaurer.

Chaque fichier est stocke XOR-encode (pour qu'il ne soit plus executable ni
re-detecte par d'autres antivirus), avec un fichier .json decrivant son origine.
Le dossier de quarantaine n'est accessible qu'a son proprietaire (0700).
"""

import json
import os
import time
import uuid
from pathlib import Path

from .paths import QUARANTINE_DIR, ensure_private_dir

DEFAULT_DIR = QUARANTINE_DIR
XOR_KEY = 0xA5
CHUNK = 1024 * 1024
_XOR_TABLE = bytes(b ^ XOR_KEY for b in range(256))


def _xor(data: bytes) -> bytes:
    return data.translate(_XOR_TABLE)


def _open_private(path: Path, flags: int):
    """Ouvre en creation exclusive, sans suivre de lien symbolique, en mode 0600."""
    flags |= os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) \
        | getattr(os, "O_BINARY", 0)
    return os.fdopen(os.open(path, flags, 0o600), "wb")


class Quarantine:
    def __init__(self, directory: Path = DEFAULT_DIR):
        self.directory = Path(directory)

    def isolate(self, path: Path, threat: str) -> str:
        path = Path(path)
        if path.is_symlink():
            raise OSError(f"{path} est un lien symbolique, mise en quarantaine refusee")
        ensure_private_dir(self.directory)
        item_id = uuid.uuid4().hex
        path = path.resolve()
        blob = self.directory / f"{item_id}.bin"
        with open(path, "rb") as src, _open_private(blob, 0) as dst:
            while chunk := src.read(CHUNK):
                dst.write(_xor(chunk))
        meta = {"original_path": str(path), "threat": threat, "date": time.time()}
        with _open_private(self.directory / f"{item_id}.json", 0) as fh:
            fh.write(json.dumps(meta).encode("utf-8"))
        path.unlink()
        return item_id

    def exists(self, item_id: str) -> bool:
        return (item_id.isalnum()
                and (self.directory / f"{item_id}.json").is_file()
                and (self.directory / f"{item_id}.bin").is_file())

    def list(self) -> list[dict]:
        items = []
        for meta_file in sorted(self.directory.glob("*.json")):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            items.append({"id": meta_file.stem, **meta})
        return items

    def restore(self, item_id: str) -> Path:
        if not self.exists(item_id):
            raise FileNotFoundError(f"Aucun element {item_id!r} en quarantaine")
        meta_file = self.directory / f"{item_id}.json"
        blob = self.directory / f"{item_id}.bin"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        target = Path(meta["original_path"])
        if not target.is_absolute():
            raise OSError(f"Emplacement d'origine invalide : {target}")
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"{target} existe deja, restauration annulee")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(blob, "rb") as src, _open_private(target, 0) as dst:
            while chunk := src.read(CHUNK):
                dst.write(_xor(chunk))
        blob.unlink()
        meta_file.unlink()
        return target

    def delete(self, item_id: str) -> None:
        if not item_id.isalnum():
            raise FileNotFoundError(f"Aucun element {item_id!r} en quarantaine")
        for suffix in (".bin", ".json"):
            (self.directory / f"{item_id}{suffix}").unlink(missing_ok=True)
