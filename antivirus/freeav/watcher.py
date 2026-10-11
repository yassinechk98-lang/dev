"""Protection en temps reel : surveille des dossiers (Telechargements, Bureau...) et
analyse chaque nouveau fichier des qu'il a fini d'etre ecrit.

La surveillance compare regulierement le contenu des dossiers (pas de pilote ni de
dependance) : un fichier n'est analyse qu'une fois sa taille et sa date stables, pour
ne pas lire un telechargement en cours. Les fichiers deja presents au demarrage ne sont
pas re-analyses (l'analyse complete s'en charge). Seules les menaces confirmees sont
mises en quarantaine ; un resultat "suspect" (YARA) est signale, jamais deplace.
"""

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .clamav import ClamdError
from .quarantine import Quarantine
from .scanner import Detection, Scanner, _excluded
from .yara_engine import YaraScanError

MAX_DEPTH = 3          # sous-dossiers surveilles (une archive extraite, par exemple)
MAX_FILES = 20000      # au-dela, le dossier est trop gros pour etre surveille ainsi
PARTIAL_SUFFIXES = (".crdownload", ".part", ".partial", ".download", ".tmp")


def default_folders(home: Path | None = None) -> list[Path]:
    home = Path(home) if home else Path.home()
    names = ("Downloads", "Telechargements", "Téléchargements", "Desktop", "Bureau")
    return [home / n for n in names if (home / n).is_dir()]


@dataclass
class WatchEvent:
    kind: str            # "menace", "suspect", "quarantaine", "usb", "erreur"
    path: Path
    message: str
    detection: Detection | None = None


def _snapshot(folders: list[Path], exclude: set[Path]) -> dict[Path, tuple]:
    """{fichier: (taille, date, identifiant, changement)} : un fichier remplace par un autre
    de meme taille et meme date change quand meme d'identifiant."""
    state: dict[Path, tuple] = {}
    stack = [(Path(f), 0) for f in folders]
    while stack and len(state) < MAX_FILES:
        folder, depth = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            if _excluded(path, exclude):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if depth < MAX_DEPTH:
                        stack.append((path, depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    st = entry.stat(follow_symlinks=False)
                    state[path] = (st.st_size, st.st_mtime_ns, entry.inode(), st.st_ctime_ns)
            except OSError:
                continue
    return state


class FolderWatcher:
    def __init__(self, scanner: Scanner, folders: list[Path], quarantine: Quarantine | None = None,
                 exclude: set[Path] | None = None,
                 on_event: Callable[[WatchEvent], None] | None = None,
                 removable_drives: Callable[[], set[str]] | None = None):
        self.scanner = scanner
        # Cles USB et cartes memoire : analysees entierement des qu'elles sont branchees.
        self.removable_drives = removable_drives
        self._drives = set(removable_drives()) if removable_drives else set()
        self.folders = [Path(f) for f in folders]
        self.quarantine = quarantine
        self.exclude = set(exclude or set())
        if quarantine:
            self.exclude.add(Path(quarantine.directory))
        self.on_event = on_event or (lambda event: None)
        self._known = _snapshot(self.folders, self.exclude)  # deja presents : pas re-analyses
        self._pending: dict[Path, tuple] = {}
        self._drive_scans: list[threading.Thread] = []
        self.scanned = 0

    def poll(self) -> list[WatchEvent]:
        """Un tour de surveillance. Retourne les evenements produits."""
        events: list[WatchEvent] = []
        if self.removable_drives:
            drives = set(self.removable_drives())
            for drive in sorted(drives - self._drives):
                # En arriere-plan : Telechargements et Bureau restent surveilles pendant
                # l'analyse d'une grosse cle.
                scan = threading.Thread(target=self._scan_drive, args=(drive,), daemon=True)
                scan.start()
                self._drive_scans.append(scan)
            self._drives = drives
            self._drive_scans = [t for t in self._drive_scans if t.is_alive()]
        current = _snapshot(self.folders, self.exclude)
        for path, sig in current.items():
            if self._known.get(path) == sig:
                continue
            if path.name.lower().endswith(PARTIAL_SUFFIXES):
                continue  # telechargement en cours : le fichier final sera analyse
            if self._pending.get(path) != sig:
                self._pending[path] = sig  # nouveau ou encore en ecriture : on attend un tour
                continue
            del self._pending[path]
            self._known[path] = sig
            if event := self._scan(path):
                events.append(event)
        for path in set(self._known) - set(current):
            del self._known[path]
        for path in set(self._pending) - set(current):
            del self._pending[path]
        for event in events:
            self.on_event(event)
        return events

    def _scan_drive(self, drive: str) -> list[WatchEvent]:
        """Analyse complete d'un lecteur amovible ; les evenements partent par on_event."""
        try:
            report = self.scanner.scan([Path(drive)], exclude=self.exclude)
        except Exception as exc:  # cle retiree pendant l'analyse, moteur en erreur...
            event = WatchEvent("erreur", Path(drive), f"cle USB {drive} : analyse impossible ({exc})")
            self.on_event(event)
            return [event]
        events = []
        for det in report.detections:
            if det.suspect or not self.quarantine:
                events.append(WatchEvent("suspect" if det.suspect else "menace", det.path,
                                         f"cle USB {drive} : {det.threat}", det))
                continue
            try:
                self.quarantine.isolate(det.path, det.threat, det.sha256)
                events.append(WatchEvent("quarantaine", det.path, f"cle USB {drive} : menace "
                                         f"bloquee ({det.threat}), mise en quarantaine", det))
            except OSError as exc:
                events.append(WatchEvent("menace", det.path, f"cle USB {drive} : {det.threat} "
                                         f"(quarantaine impossible : {exc})", det))
        self.scanned += report.scanned
        verdict = (f"{len(report.threats)} menace(s)" if report.detections else "aucune menace")
        events.append(WatchEvent("usb", Path(drive), f"cle USB {drive} analysee : "
                                 f"{report.scanned} fichiers, {verdict}"))
        for event in events:
            self.on_event(event)
        return events

    def wait_drives(self, timeout: float | None = None) -> None:
        """Attend la fin des analyses de cles USB en cours."""
        for scan in list(self._drive_scans):
            scan.join(timeout)

    def _scan(self, path: Path) -> WatchEvent | None:
        try:
            if path.stat().st_size > self.scanner.max_size:
                return None
            detection = self.scanner.scan_file(path)
        except FileNotFoundError:
            return None
        except (OSError, ClamdError, YaraScanError) as exc:
            return WatchEvent("erreur", path, f"analyse impossible : {exc}")
        self.scanned += 1
        if not detection:
            return None
        if detection.suspect:
            return WatchEvent("suspect", path, f"fichier suspect ({detection.threat}), a verifier",
                              detection)
        if not self.quarantine:
            return WatchEvent("menace", path, f"menace detectee : {detection.threat}", detection)
        try:
            self.quarantine.isolate(path, detection.threat, detection.sha256)
        except OSError as exc:
            return WatchEvent("menace", path, f"menace detectee : {detection.threat} "
                              f"(quarantaine impossible : {exc})", detection)
        self._known.pop(path, None)
        return WatchEvent("quarantaine", path,
                          f"menace bloquee : {detection.threat}, fichier mis en quarantaine", detection)

    def run(self, stop: threading.Event, interval: float = 2.0,
            stop_file: Path | None = None) -> None:
        """Surveille jusqu'a stop, ou jusqu'a ce que stop_file soit cree apres le demarrage
        (c'est ainsi que "Tout retirer" arrete la protection lancee a l'ouverture de session)."""
        started = time.time()
        while not stop.wait(interval):
            if stop_file is not None:
                try:
                    if stop_file.stat().st_mtime >= started:
                        return
                except OSError:
                    pass
            self.poll()


def removable_drives() -> set[str]:
    """Lecteurs amovibles branches (cles USB, cartes SD), par exemple {"E:\\"}. Windows."""
    if os.name != "nt":
        return set()
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mask, drives = kernel32.GetLogicalDrives(), set()
    for i in range(26):
        if mask & (1 << i):
            root = f"{chr(65 + i)}:\\"
            if kernel32.GetDriveTypeW(root) == 2:  # DRIVE_REMOVABLE
                drives.add(root)
    return drives


def notify(title: str, message: str) -> None:
    """Previent l'utilisateur meme si FreeAV tourne en arriere-plan (Windows)."""
    if os.name != "nt":
        return
    import ctypes

    def show():
        # MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x30 | 0x40000 | 0x10000)
    threading.Thread(target=show, daemon=True).start()
