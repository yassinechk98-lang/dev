"""Moteur d'analyse : parcourt les fichiers et les compare aux signatures."""

import hashlib
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .clamav import ClamdClient, ClamdError
from .signatures import SignatureDB
from .yara_engine import YaraEngine

MAX_SIZE = 200 * 1024 * 1024  # fichiers plus gros ignores (200 Mo)


@dataclass
class Detection:
    path: Path
    threat: str
    engine: str  # "signatures", "yara" ou "clamav"


@dataclass
class ScanReport:
    scanned: int = 0
    skipped: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.detections


def hash_file(path: Path) -> tuple[str, str]:
    sha256, md5 = hashlib.sha256(), hashlib.md5()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def iter_files(target: Path, exclude: set[Path] | None = None) -> Iterator[Path]:
    exclude = {p.resolve() for p in exclude or set()}
    if target.is_file():
        yield target
        return
    for root, dirs, files in os.walk(target):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if (root_path / d).resolve() not in exclude]
        for name in files:
            path = root_path / name
            if not path.is_symlink():
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
            return Detection(path, threat, "signatures")
        if self.yara and (threat := self.yara.match(path)):
            return Detection(path, threat, "yara")
        if self.clamd and (threat := self.clamd.scan_file(path)):
            return Detection(path, threat, "clamav")
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
                except (OSError, ClamdError) as exc:
                    report.errors.append((path, str(exc)))
                    continue
                report.scanned += 1
                if detection:
                    report.detections.append(detection)
        return report
