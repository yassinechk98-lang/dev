"""Quarantaine : deplace les fichiers infectes hors de portee et permet de les restaurer.

Chaque fichier est stocke XOR-encode (pour qu'il ne soit plus executable ni
re-detecte par d'autres antivirus), avec un fichier .json decrivant son origine.
Le dossier de quarantaine n'est accessible qu'a son proprietaire (0700).
"""

import hashlib
import json
import os
import stat
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


def _inside(path: Path, directory: Path) -> bool:
    real, base = Path(os.path.realpath(path)), Path(os.path.realpath(directory))
    return real == base or base in real.parents


def _is_elevated() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


class Quarantine:
    def __init__(self, directory: Path = DEFAULT_DIR, elevated: bool | None = None):
        self.elevated = _is_elevated() if elevated is None else elevated
        self.directory = Path(directory)

    def isolate(self, path: Path, threat: str, expected_sha256: str = "") -> str:
        """Met le fichier en quarantaine. Si expected_sha256 est donne, refuse le fichier
        s'il a change depuis l'analyse (il pourrait s'agir d'un autre fichier)."""
        path = Path(path)
        if path.is_symlink():
            raise OSError(f"{path} est un lien symbolique, mise en quarantaine refusee")
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise OSError(f"{path} n'est pas un fichier ordinaire")
        ensure_private_dir(self.directory)
        item_id = uuid.uuid4().hex
        path = path.resolve()
        blob = self.directory / f"{item_id}.bin"
        meta_file = self.directory / f"{item_id}.json"
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as src, _open_private(blob, 0) as dst:
                while chunk := src.read(CHUNK):
                    digest.update(chunk)
                    dst.write(_xor(chunk))
            if expected_sha256 and digest.hexdigest() != expected_sha256:
                raise OSError(f"{path} a change depuis l'analyse, mise en quarantaine annulee")
            meta = {"original_path": str(path), "threat": threat, "date": time.time(),
                    "sha256": digest.hexdigest(), "mode": stat.S_IMODE(os.stat(path).st_mode)}
            with _open_private(meta_file, 0) as fh:
                fh.write(json.dumps(meta).encode("utf-8"))
            path.unlink()
        except BaseException:
            # Original impossible a supprimer (dossier en lecture seule, fichier verrouille...) :
            # on retire la copie pour que la quarantaine ne mente pas.
            blob.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)
            raise
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
        if self.elevated and not _inside(target, Path.home()):
            # La quarantaine est modifiable sans droits : en administrateur, une fausse fiche
            # pourrait faire ecrire un fichier dans C:\Windows. On ne restaure alors que dans
            # le dossier personnel.
            raise PermissionError(f"FreeAV est lance en administrateur : restaurez {target} "
                                  "en le relancant sans droits administrateur")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(blob, "rb") as src, _open_private(target, 0) as dst:
            while chunk := src.read(CHUNK):
                dst.write(_xor(chunk))
        if isinstance(meta.get("mode"), int):
            # Droits d'origine (executable...), sans les bits speciaux setuid/setgid.
            target.chmod(meta["mode"] & 0o777)
        blob.unlink()
        meta_file.unlink()
        return target

    def delete(self, item_id: str) -> None:
        if not item_id.isalnum():
            raise FileNotFoundError(f"Aucun element {item_id!r} en quarantaine")
        for suffix in (".bin", ".json"):
            (self.directory / f"{item_id}{suffix}").unlink(missing_ok=True)
