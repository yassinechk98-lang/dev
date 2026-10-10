"""Installation de FreeAV sur le PC (Windows, pour l'utilisateur courant, sans droits
administrateur), comme un logiciel classique :
  - FreeAV.exe copie dans %LOCALAPPDATA%\\FreeAV ;
  - raccourcis dans le menu Demarrer et sur le Bureau ;
  - "Analyser avec FreeAV" dans le clic droit de l'Explorateur (fichiers, dossiers, lecteurs) ;
  - entree dans Parametres > Applications, d'ou FreeAV se desinstalle.

La desinstallation retire tout cela, la protection automatique et le moteur ClamAV integre.
Les donnees personnelles (quarantaine, journal, cle abuse.ch dans ~/.freeav) sont gardees.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, schedule
from .repair.platform import System

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\FreeAV"
MENU_KEYS = [r"Software\Classes\*\shell\FreeAV",
             r"Software\Classes\Directory\shell\FreeAV",
             r"Software\Classes\Drive\shell\FreeAV"]
MENU_LABEL = "Analyser avec FreeAV"
REG_SZ, REG_DWORD = 1, 4

SHORTCUT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
  $link = $shell.CreateShortcut((Join-Path $folder 'FreeAV.lnk'))
  $link.TargetPath = $env:FREEAV_EXE
  $link.WorkingDirectory = Split-Path $env:FREEAV_EXE
  $link.IconLocation = $env:FREEAV_EXE + ',0'
  $link.Description = 'FreeAV - antivirus gratuit'
  $link.Save()
}
'OK'
"""

REMOVE_SHORTCUTS_SCRIPT = r"""
foreach ($folder in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
  $path = Join-Path $folder 'FreeAV.lnk'
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
}
'OK'
"""


class InstallError(Exception):
    pass


def target_exe(system: System) -> Path:
    return schedule.install_dir(system) / "FreeAV.exe"


def is_installed(system: System) -> bool:
    return bool(system.is_windows and system.registry.get("HKCU", UNINSTALL_KEY, "DisplayName"))


def running_installed_copy(system: System) -> bool:
    return bool(getattr(sys, "frozen", False)) and \
        Path(sys.executable).resolve() == target_exe(system).resolve()


def _powershell(system: System, script: str, exe: Path) -> None:
    import os
    previous = os.environ.get("FREEAV_EXE")
    os.environ["FREEAV_EXE"] = str(exe)  # passe par l'environnement : aucun echappement a faire
    try:
        result = system.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-Command", script], timeout=120)
    finally:
        if previous is None:
            os.environ.pop("FREEAV_EXE", None)
        else:
            os.environ["FREEAV_EXE"] = previous
    if result.returncode != 0 or "OK" not in (result.stdout or ""):
        raise InstallError((result.stderr or result.stdout or "raccourcis impossibles").strip()[-300:])


def install(system: System, source: Path | None = None) -> list[str]:
    """Installe (ou met a jour) FreeAV pour l'utilisateur courant. Retourne les etapes faites."""
    if not system.is_windows:
        raise InstallError("l'installation est prevue pour Windows")
    source = Path(source or sys.executable)
    exe = target_exe(system)
    done = []
    if source.resolve() != exe.resolve():
        exe.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, exe)
        except PermissionError as exc:  # FreeAV installe deja ouvert (protection en cours)
            schedule.request_stop()
            try:
                schedule.wait_and(lambda: shutil.copy2(source, exe))
            except PermissionError:
                raise InstallError(f"fermez FreeAV puis recommencez ({exc})") from None
    done.append(f"FreeAV copie dans {exe.parent}")

    _powershell(system, SHORTCUT_SCRIPT, exe)
    done.append("raccourcis FreeAV dans le menu Demarrer et sur le Bureau")

    reg = system.registry
    for key in MENU_KEYS:
        reg.set("HKCU", key, "", MENU_LABEL, REG_SZ)
        reg.set("HKCU", key, "Icon", f"{exe},0", REG_SZ)
        reg.set("HKCU", key + r"\command", "",
                subprocess.list2cmdline([str(exe), "gui", "--scan"]) + ' "%1"', REG_SZ)
    done.append(f"« {MENU_LABEL} » dans le clic droit de l'Explorateur")

    size_kb = exe.stat().st_size // 1024
    values = {"DisplayName": ("FreeAV - antivirus gratuit", REG_SZ),
              "DisplayVersion": (__version__, REG_SZ),
              "Publisher": ("FreeAV (projet open source)", REG_SZ),
              "DisplayIcon": (f"{exe},0", REG_SZ),
              "InstallLocation": (str(exe.parent), REG_SZ),
              "UninstallString": (subprocess.list2cmdline([str(exe), "uninstall"]), REG_SZ),
              "QuietUninstallString": (subprocess.list2cmdline([str(exe), "uninstall", "--yes"]),
                                       REG_SZ),
              "URLInfoAbout": ("https://github.com/yassinechk98-lang/dev", REG_SZ),
              "NoModify": (1, REG_DWORD), "NoRepair": (1, REG_DWORD),
              "EstimatedSize": (size_kb, REG_DWORD)}
    for name, (value, kind) in values.items():
        reg.set("HKCU", UNINSTALL_KEY, name, value, kind)
    done.append("FreeAV visible dans Parametres > Applications (desinstallation possible)")
    return done


def uninstall(system: System) -> list[str]:
    if not system.is_windows:
        raise InstallError("la desinstallation est prevue pour Windows")
    done = []
    try:
        done += schedule.remove(system, keep_copy=True)
    except schedule.ScheduleError as exc:
        done.append(f"protection automatique : {exc}")
    for key in MENU_KEYS:
        system.registry.delete_key("HKCU", key)
    done.append("clic droit « Analyser avec FreeAV » retire")
    exe = target_exe(system)
    try:
        _powershell(system, REMOVE_SHORTCUTS_SCRIPT, exe)
        done.append("raccourcis retires")
    except InstallError as exc:
        done.append(f"raccourcis non retires : {exc}")
    system.registry.delete_key("HKCU", UNINSTALL_KEY)
    from .clamav_local import LocalClamav, home_dir
    LocalClamav(home_dir(system.environ)).uninstall()
    done.append("moteur ClamAV integre supprime")
    if exe.exists():
        if running_installed_copy(system):
            # Un programme ne peut pas effacer son propre fichier : Windows le fera juste apres.
            system.run(["cmd", "/c", "start", "", "/min", "cmd", "/c",
                        f'ping 127.0.0.1 -n 4 >nul & del /f /q "{exe}" & rmdir "{exe.parent}"'],
                       timeout=30)
            done.append(f"FreeAV.exe sera supprime dans quelques secondes ({exe.parent})")
        else:
            try:
                schedule.wait_and(exe.unlink)
                shutil.rmtree(exe.parent, ignore_errors=True)
                done.append(f"FreeAV supprime de {exe.parent}")
            except OSError as exc:
                done.append(f"FreeAV.exe encore utilise, a supprimer a la main : {exe} ({exc})")
    done.append("vos donnees (quarantaine, journal) sont gardees dans ~/.freeav")
    return done
