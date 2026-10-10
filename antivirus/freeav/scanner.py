"""Moteur d'analyse : parcourt les fichiers et les compare aux signatures."""

import hashlib
import os
import stat
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .clamav import ClamdClient, ClamdError
from .signatures import SignatureDB
from .yara_engine import YaraEngine, YaraScanError

MAX_SIZE = 200 * 1024 * 1024  # fichiers plus gros ignores (200 Mo)


@dataclass
class Detection:
    path: Path
    threat: str
    engine: str  # "signatures", "yara" ou "clamav"
    sha256: str = ""

    @property
    def suspect(self) -> bool:
        """Les regles YARA reperent des motifs suspects, pas des malwares certains :
        leurs detections ne sont jamais mises en quarantaine automatiquement."""
        return self.engine == "yara"


@dataclass
class ScanReport:
    scanned: int = 0
    skipped: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.detections

    @property
    def threats(self) -> list[Detection]:
        return [d for d in self.detections if not d.suspect]

    @property
    def suspects(self) -> list[Detection]:
        return [d for d in self.detections if d.suspect]


class NotRegularFile(OSError):
    pass


def hash_file(path: Path) -> tuple[str, str]:
    sha256, md5 = hashlib.sha256(), hashlib.md5()
    # O_NONBLOCK : ouvrir un tube nomme (FIFO) ne doit jamais bloquer l'analyse.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise NotRegularFile(f"{path} n'est pas un fichier ordinaire")
        while chunk := fh.read(1024 * 1024):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def _is_regular(path: Path, follow: bool) -> bool:
    try:
        mode = (os.stat(path) if follow else os.lstat(path)).st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode)


def _excluded(path: Path, exclude: set[Path]) -> bool:
    return any(path == ex or ex in path.parents for ex in exclude)


def iter_files(target: Path, exclude: set[Path] | None = None) -> Iterator[Path]:
    """Fichiers ordinaires a analyser : ni liens symboliques, ni tubes, ni peripheriques."""
    exclude = {Path(p).resolve() for p in exclude or set()}
    if _excluded(target.resolve(), exclude):
        return
    if not target.is_dir():
        if _is_regular(target, follow=True):
            yield target
        return
    for root, dirs, files in os.walk(target):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not _excluded((root_path / d).resolve(), exclude)]
        for name in files:
            path = root_path / name
            if _is_regular(path, follow=False):
                yield path


class Scanner:
    def __init__(self, db: SignatureDB, clamd: ClamdClient | None = None,
                 max_size: int = MAX_SIZE, yara: YaraEngine | None = None):
        self.db = db
        self.clamd = clamd
        self.yara = yara
        self.max_size = max_size

    def scan_file(self, path: Path) -> Detection | None:
        sha256, md5 = hash_file(path)
        if threat := self.db.lookup(sha256, md5):
            return Detection(path, threat, "signatures", sha256)
        if self.clamd and (threat := self.clamd.scan_file(path)):
            return Detection(path, threat, "clamav", sha256)
        if self.yara and (threat := self.yara.match(path)):
            return Detection(path, threat, "yara", sha256)
        return None

    def scan(self, targets: list[Path], exclude: set[Path] | None = None,
             on_file: Callable[[Path], None] | None = None,
             should_stop: Callable[[], bool] | None = None) -> ScanReport:
        report = ScanReport()
        for target in targets:
            for path in iter_files(Path(target), exclude):
                if should_stop and should_stop():
                    return report
                if on_file:
                    on_file(path)
                try:
                    if path.stat().st_size > self.max_size:
                        report.skipped += 1
                        continue
                    detection = self.scan_file(path)
                except (OSError, ClamdError, YaraScanError) as exc:
                    report.errors.append((path, str(exc)))
                    continue
                report.scanned += 1
                if detection:
                    report.detections.append(detection)
        return report
