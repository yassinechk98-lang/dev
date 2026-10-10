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
    kind: str            # "menace", "suspect", "quarantaine", "erreur"
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
                 on_event: Callable[[WatchEvent], None] | None = None):
        self.scanner = scanner
        self.folders = [Path(f) for f in folders]
        self.quarantine = quarantine
        self.exclude = set(exclude or set())
        if quarantine:
            self.exclude.add(Path(quarantine.directory))
        self.on_event = on_event or (lambda event: None)
        self._known = _snapshot(self.folders, self.exclude)  # deja presents : pas re-analyses
        self._pending: dict[Path, tuple] = {}
        self.scanned = 0

    def poll(self) -> list[WatchEvent]:
        """Un tour de surveillance. Retourne les evenements produits."""
        events: list[WatchEvent] = []
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


def notify(title: str, message: str) -> None:
    """Previent l'utilisateur meme si FreeAV tourne en arriere-plan (Windows)."""
    if os.name != "nt":
        return
    import ctypes

    def show():
        # MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x30 | 0x40000 | 0x10000)
    threading.Thread(target=show, daemon=True).start()
