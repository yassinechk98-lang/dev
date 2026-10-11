"""Mise a jour de FreeAV lui-meme (FreeAV.exe sous Windows).

Chaque version publiee par la CI s'accompagne d'un petit fichier FreeAV.json (numero de
version, empreinte SHA-256 et adresse de FreeAV.exe) dans la meme pre-release GitHub que
le telechargement direct. FreeAV le lit, propose la nouvelle version si elle est plus
recente, et ne remplace rien sans l'accord de l'utilisateur :
  - telechargement uniquement en HTTPS depuis github.com (et ses serveurs de fichiers) ;
  - fichier refuse si son empreinte ne correspond pas a celle annoncee, ou si ce n'est pas
    un programme Windows ;
  - l'ancien FreeAV.exe est garde (FreeAV.old.exe) jusqu'au demarrage suivant, et remis en
    place si le remplacement echoue.

Rien n'est envoye : FreeAV ne fait que telecharger deux fichiers publics. La verification
automatique (a l'ouverture de FreeAV et dans l'entretien quotidien) contacte github.com, qui
voit donc l'adresse IP et l'heure ; elle se coupe avec `FreeAV.exe app-update --auto-check off`
ou la case de l'interface.
"""

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__
from .clamav_local import FREEAV_TEST_RELEASE

BUILD_INFO = Path(__file__).parent / "data" / "build.json"  # ecrit par la CI Windows
ALLOWED_HOSTS = {"github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com"}
CANAL_RE = re.compile(r"^freeav-[a-z]{1,16}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST = 64 * 1024
MAX_EXE = 100 * 1024 * 1024


class SelfUpdateError(Exception):
    pass


@dataclass
class Release:
    build: int
    sha256: str
    size: int
    url: str
    commit: str = ""


def current_build() -> dict | None:
    """Version de ce FreeAV.exe : {"build": 42, "canal": "freeav-test", ...}, ou None
    (FreeAV lance depuis le code source : il se met a jour avec git)."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        data = json.loads(BUILD_INFO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (isinstance(data, dict) and isinstance(data.get("build"), int)
            and CANAL_RE.match(str(data.get("canal", "")))):
        return None
    return data


AUTO_CHECK_SETTING = "check_app_updates"


def auto_check_enabled() -> bool:
    from . import updater
    return updater.load_setting(AUTO_CHECK_SETTING, True, updater.CONFIG_FILE) is not False


def set_auto_check(enabled: bool) -> None:
    from . import updater
    updater.save_setting(AUTO_CHECK_SETTING, bool(enabled), updater.CONFIG_FILE)


def manifest_url(canal: str) -> str:
    return f"{FREEAV_TEST_RELEASE}{canal}/FreeAV.json"


def parse_manifest(raw: bytes, canal: str) -> Release:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise SelfUpdateError("fichier de version illisible") from None
    expected_url = f"{FREEAV_TEST_RELEASE}{canal}/FreeAV.exe"
    if not (isinstance(data, dict) and isinstance(data.get("build"), int)
            and isinstance(data.get("size"), int) and 0 < data["size"] <= MAX_EXE
            and SHA256_RE.match(str(data.get("sha256", "")))
            and data.get("url") == expected_url):
        raise SelfUpdateError("fichier de version invalide : mise a jour refusee")
    return Release(data["build"], data["sha256"], data["size"], data["url"],
                   str(data.get("commit", ""))[:40])


class _GithubOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise SelfUpdateError(f"adresse de telechargement refusee : {parts.scheme}://{parts.hostname}")


def _open(url: str, timeout: float = 60):
    _check_url(url)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), _GithubOnlyRedirects())
    return opener.open(urllib.request.Request(url, headers={"User-Agent": "FreeAV"}),
                       timeout=timeout)


def fetch(url: str, limit: int, dest: Path | None = None) -> bytes:
    """Telecharge url (au plus limit octets), en memoire ou dans dest."""
    size, chunks = 0, []
    try:
        with _open(url) as resp:
            out = open(dest, "wb") if dest else None
            try:
                while chunk := resp.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise SelfUpdateError("fichier trop volumineux, refuse")
                    if out:
                        out.write(chunk)
                    else:
                        chunks.append(chunk)
            finally:
                if out:
                    out.close()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise SelfUpdateError("aucune version publiee pour le moment") from None
        raise SelfUpdateError(f"serveur indisponible ({exc.code})") from None
    except (urllib.error.URLError, OSError) as exc:
        raise SelfUpdateError(f"connexion impossible : {exc}") from None
    return b"".join(chunks)


def check(fetcher: Callable[[str, int], bytes] | None = None,
          build: dict | None = None) -> Release | None:
    """La nouvelle version si elle est plus recente que celle-ci, sinon None."""
    build = build or current_build()
    if not build:
        return None
    raw = (fetcher or (lambda url, limit: fetch(url, limit)))(manifest_url(build["canal"]),
                                                              MAX_MANIFEST)
    release = parse_manifest(raw, build["canal"])
    return release if release.build > build["build"] else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(release: Release, folder: Path,
             fetcher: Callable[[str, int, Path], bytes] | None = None) -> Path:
    """Telecharge la nouvelle version a cote de l'actuelle et la verifie."""
    new = folder / "FreeAV.new.exe"
    new.unlink(missing_ok=True)
    (fetcher or fetch)(release.url, min(release.size, MAX_EXE), new)
    verify(new, release.sha256)
    return new


def verify(path: Path, sha256: str) -> None:
    try:
        ok = _sha256(path) == sha256.lower()
        with open(path, "rb") as fh:
            is_program = fh.read(2) == b"MZ"
    except OSError as exc:
        raise SelfUpdateError(f"fichier telecharge illisible : {exc}") from None
    if not (ok and is_program):
        path.unlink(missing_ok=True)
        raise SelfUpdateError("le fichier telecharge ne correspond pas a la version annoncee : "
                              "mise a jour refusee, FreeAV n'a pas ete modifie")


def replace(target: Path, new: Path) -> Path:
    """Met new a la place de target. Windows autorise a renommer un programme en cours
    d'execution (pas a l'effacer) : l'ancien devient FreeAV.old.exe. Retourne son chemin."""
    old = target.with_name("FreeAV.old.exe")
    for n in range(10):
        try:
            old.unlink(missing_ok=True)
            break
        except PermissionError:  # encore utilise (mise a jour precedente toujours ouverte)
            old = target.with_name(f"FreeAV.old{n + 1}.exe")
    else:
        raise SelfUpdateError("fermez les fenetres FreeAV ouvertes puis recommencez")
    try:
        os.replace(target, old)
    except OSError as exc:
        raise SelfUpdateError(f"FreeAV.exe ne peut pas etre remplace : {exc}") from None
    try:
        os.replace(new, target)
    except OSError as exc:
        os.replace(old, target)  # on remet l'ancienne version
        raise SelfUpdateError(f"remplacement impossible, ancienne version gardee : {exc}") from None
    return old


def cleanup_old(exe: Path | None = None) -> None:
    """Au demarrage : efface les anciennes versions laissees par une mise a jour."""
    if exe is None:
        if not getattr(sys, "frozen", False):
            return
        exe = Path(sys.executable)
    for old in [exe.with_name("FreeAV.new.exe"), *exe.parent.glob("FreeAV.old*.exe")]:
        if old.resolve() != exe.resolve():
            try:
                old.unlink()
            except OSError:
                pass


def start_detached(args: list[str]) -> None:
    """Lance un programme qui continue apres la fermeture de ce FreeAV.

    FreeAV.exe (PyInstaller) place ses processus enfants dans un "job" Windows qui les
    arrete avec lui : on demande d'en sortir (CREATE_BREAKAWAY_FROM_JOB), et sinon on passe
    par WMI, comme pour la desinstallation."""
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    breakaway = 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
    options = dict(close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, cwd=str(Path(args[0]).parent))
    try:
        subprocess.Popen(args, creationflags=flags | breakaway, **options)
        return
    except OSError:
        pass
    from .installer import launch_with_wmi
    from .repair.platform import System
    launch_with_wmi(System(), subprocess.list2cmdline(args))


def update_target(system, running: Path | None = None) -> Path:
    """Le FreeAV.exe a remplacer : la copie installee si FreeAV est installe, sinon celui-ci."""
    from . import installer
    if installer.is_installed(system):
        return installer.target_exe(system)
    return Path(running or sys.executable)


def apply(release: Release, system, progress: Callable[[str], None] = lambda m: None,
          fetcher=None, launcher: Callable[[list[str]], None] | None = None,
          running: Path | None = None) -> list[str]:
    """Telecharge, verifie et installe la nouvelle version, puis relance la protection en
    temps reel si elle etait active. Retourne les etapes faites."""
    from . import installer, schedule
    launcher = launcher or start_detached
    target = update_target(system, running)
    progress(f"Telechargement de FreeAV (version {release.build})...")
    new = download(release, target.parent, fetcher)
    progress("Installation de la nouvelle version...")
    replace(target, new)
    done = [f"FreeAV mis a jour (version {release.build}) : {target}"]
    if installer.is_installed(system):
        system.registry.set("HKCU", installer.UNINSTALL_KEY, "DisplayVersion",
                            f"{__version__} (build {release.build})", installer.REG_SZ)
    from . import quarantine
    run_entry = system.registry.get("HKCU", schedule.RUN_KEY, schedule.RUN_VALUE)
    if not (run_entry and str(target).lower() in str(run_entry[0]).lower()):
        return done
    if quarantine._is_elevated():
        # Relancee d'ici, la protection tournerait en administrateur sur des dossiers
        # modifiables sans droits : elle repartira normalement a la prochaine session.
        done.append("protection en temps reel : nouvelle version a la prochaine ouverture de "
                    "session (FreeAV est lance en administrateur)")
    else:
        schedule.request_stop()  # l'ancienne protection s'arrete...
        launcher([str(target)] + schedule.WATCH_ARGS)  # ...la nouvelle prend le relais
        done.append("protection en temps reel relancee avec la nouvelle version")
    return done
