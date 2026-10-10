"""Moteur ClamAV integre (Windows) : FreeAV installe la version officielle de ClamAV
(Cisco Talos) dans %LOCALAPPDATA%\\FreeAV\\ClamAV, sans droits administrateur, puis
telecharge ses signatures officielles avec freshclam (environ 300 Mo, mises a jour chaque
jour par Talos).

Le paquet ClamAV est construit par la CI depuis la release officielle (empreinte verifiee) et
FreeAV.exe contient son empreinte SHA-256 (data/clamav.json) : un paquet modifie est refuse.
L'analyse se fait entierement sur le PC (clamscan) ; rien n'est envoye.
"""

import hashlib
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .updater import _HttpsOnlyRedirects

MANIFEST = Path(__file__).parent / "data" / "clamav.json"  # ecrit par la CI Windows
MAX_PACKAGE = 300 * 1024 * 1024
FREEAV_TEST_RELEASE = "https://github.com/yassinechk98-lang/dev/releases/download/"


class ClamavError(Exception):
    pass


def home_dir(environ: dict | None = None) -> Path:
    env = os.environ if environ is None else environ
    base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "FreeAV" / "ClamAV"


def manifest() -> dict | None:
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (isinstance(data, dict) and str(data.get("url", "")).startswith(FREEAV_TEST_RELEASE)
            and len(str(data.get("sha256", ""))) == 64):
        return None
    return data


def _find(root: Path, name: str) -> Path | None:
    hits = sorted(root.rglob(name)) if root.is_dir() else []
    return hits[0] if hits else None


class LocalClamav:
    def __init__(self, root: Path | None = None, runner=None):
        self.root = Path(root) if root else home_dir()
        self.runner = runner or _run

    @property
    def database(self) -> Path:
        return self.root / "database"

    @property
    def clamscan(self) -> Path | None:
        return _find(self.root / "program", "clamscan.exe") or _find(self.root / "program", "clamscan")

    @property
    def freshclam(self) -> Path | None:
        return _find(self.root / "program", "freshclam.exe") or _find(self.root / "program", "freshclam")

    def installed(self) -> bool:
        return self.clamscan is not None

    def ready(self) -> bool:
        """Installe et avec des signatures (main.cvd/cld, daily.cvd/cld)."""
        return self.installed() and any(self.database.glob("daily.c[lv]d"))

    # -- installation -------------------------------------------------------------------
    def install(self, info: dict | None = None,
                progress: Callable[[str], None] = lambda message: None,
                package: Path | None = None) -> None:
        """Telecharge le paquet indique par le manifeste (ou utilise package, deja verifie
        par l'appelant), l'installe, puis telecharge les signatures."""
        info = info or manifest()
        if not info and package is None:
            raise ClamavError("cette version de FreeAV ne propose pas l'installation de ClamAV")
        with tempfile.TemporaryDirectory() as tmp:
            if package is None:
                progress(f"Telechargement de ClamAV {info.get('version', '')}...")
                package = Path(tmp) / "clamav.zip"
                _download(info["url"], package, info["sha256"])
            progress("Installation de ClamAV...")
            staging = self.root / "program.new"
            shutil.rmtree(staging, ignore_errors=True)
            _safe_extract(package, staging)
        if not (_find(staging, "clamscan.exe") or _find(staging, "clamscan")):
            shutil.rmtree(staging, ignore_errors=True)
            raise ClamavError("paquet ClamAV incomplet (clamscan introuvable)")
        shutil.rmtree(self.root / "program", ignore_errors=True)
        staging.rename(self.root / "program")
        self.database.mkdir(parents=True, exist_ok=True)
        self._write_config()
        self.update(progress)

    def _write_config(self) -> Path:
        conf = self.root / "freshclam.conf"
        conf.write_text(f"DatabaseDirectory {self.database}\n"
                        "DatabaseMirror database.clamav.net\n"
                        "ConnectTimeout 60\nReceiveTimeout 600\n", encoding="utf-8")
        return conf

    def update(self, progress: Callable[[str], None] = lambda message: None) -> str:
        if not self.freshclam:
            raise ClamavError("ClamAV n'est pas installe")
        progress("Telechargement des signatures officielles ClamAV (environ 300 Mo la premiere fois)...")
        conf = self.root / "freshclam.conf"
        if not conf.exists():
            self._write_config()
        result = self.runner([str(self.freshclam), f"--config-file={conf}", "--stdout"], 3600)
        output = " ".join((result.stdout or result.stderr or "").split())
        if result.returncode not in (0, 1) or not any(self.database.glob("daily.c[lv]d")):
            raise ClamavError(f"mise a jour des signatures ClamAV impossible : {output[-300:]}")
        return output[-300:]

    def uninstall(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # -- analyse ---------------------------------------------------------------------------
    def scan_paths(self, paths: list[Path]) -> dict[Path, str]:
        if not self.ready():
            raise ClamavError("ClamAV n'a pas encore de signatures")
        found: dict[Path, str] = {}
        with tempfile.TemporaryDirectory() as tmp:
            listing = Path(tmp) / "fichiers.txt"
            listing.write_text("\n".join(str(p) for p in paths) + "\n", encoding="utf-8")
            result = self.runner([str(self.clamscan), f"--database={self.database}",
                                  f"--file-list={listing}", "--infected", "--no-summary",
                                  "--stdout"], 3600 * 6)
        if result.returncode not in (0, 1):
            raise ClamavError(" ".join((result.stdout or result.stderr or "").split())[-300:])
        for line in (result.stdout or "").splitlines():
            line = line.rstrip()
            if line.endswith(" FOUND") and ": " in line:
                path, threat = line[:-len(" FOUND")].rsplit(": ", 1)
                found[Path(path)] = threat
        return found


class ClamscanEngine:
    """Adaptateur pour le Scanner : n'est cree que si ClamAV est pret."""
    name = "clamav"

    def __init__(self, local: LocalClamav):
        self.local = local

    def scan_paths(self, paths: list[Path]) -> dict[Path, str]:
        return self.local.scan_paths(paths)


def _download(url: str, dest: Path, sha256: str) -> None:
    if not url.startswith("https://"):
        raise ClamavError("seules les sources HTTPS sont acceptees")
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
                                         _HttpsOnlyRedirects())
    size = 0
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "FreeAV"}),
                         timeout=120) as resp, open(dest, "wb") as out:
            while chunk := resp.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PACKAGE:
                    raise ClamavError("paquet ClamAV trop volumineux, refuse")
                out.write(chunk)
    except (urllib.error.URLError, OSError) as exc:
        raise ClamavError(f"telechargement de ClamAV impossible : {exc}") from None
    _check_hash(dest, sha256)


def _check_hash(path: Path, sha256: str) -> None:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != sha256.lower():
        raise ClamavError("le paquet ClamAV telecharge ne correspond pas a l'empreinte attendue : "
                          "installation refusee")


def _safe_extract(package: Path, dest: Path) -> None:
    """Extraction sans sortir du dossier (noms en ../ ou absolus refuses, pas de liens)."""
    dest.mkdir(parents=True)
    base = dest.resolve()
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            target = (dest / member.filename).resolve()
            if base not in target.parents and target != base:
                raise ClamavError(f"paquet ClamAV invalide ({member.filename})")
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ClamavError("paquet ClamAV invalide (lien symbolique)")
        archive.extractall(dest)


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
