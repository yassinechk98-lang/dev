"""Protection automatique sous Windows, sans droits administrateur :
  - analyse quotidienne (tache planifiee "FreeAV\\Analyse quotidienne") : met a jour les
    signatures si une cle abuse.ch est enregistree, analyse Telechargements et Bureau,
    verifie les points sensibles du PC et previent en cas de probleme ;
  - protection en temps reel a l'ouverture de session (entree "FreeAV" de
    HKCU\\...\\Run) : surveille Telechargements et Bureau en arriere-plan.

Pour que ces taches ne dependent pas de l'endroit ou FreeAV.exe a ete telecharge,
FreeAV se copie d'abord dans %LOCALAPPDATA%\\FreeAV. Tout s'enleve avec
`freeav schedule --remove`.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from .repair.platform import RegistryError, System

SCAN_TASK = r"FreeAV\Analyse quotidienne"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "FreeAV"
REG_SZ = 1
WATCH_ARGS = ["watch", "--quarantine", "--notify"]
AUTO_ARGS = ["auto", "--notify"]


class ScheduleError(Exception):
    pass


def _quote(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def install_dir(system: System) -> Path:
    base = system.environ.get("LOCALAPPDATA") or str(system.home / "AppData" / "Local")
    return Path(base) / "FreeAV"


def program_command(system: System) -> list[str]:
    """Commande qui lance FreeAV depuis un emplacement stable."""
    if getattr(sys, "frozen", False):  # FreeAV.exe
        source = Path(sys.executable)
        target = install_dir(system) / "FreeAV.exe"
        if source.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, target)
            except PermissionError:
                if not target.exists():  # copie en cours d'utilisation : on garde l'ancienne
                    raise
        return [str(target)]
    return [sys.executable, "-m", "freeav"]


def _check_windows(system: System) -> None:
    if not system.is_windows:
        raise ScheduleError("la protection automatique s'installe sous Windows. Sous Linux, "
                            "ajoutez a votre crontab : 0 12 * * * python3 -m freeav auto")


def _check_time(at: str) -> str:
    hours, _, minutes = at.partition(":")
    if not (hours.isdigit() and minutes.isdigit() and int(hours) < 24 and int(minutes) < 60):
        raise ScheduleError(f"heure invalide : {at!r} (exemple : 12:30)")
    return f"{int(hours):02d}:{int(minutes):02d}"


def install(system: System, program: list[str], at: str = "12:00",
            realtime: bool = True) -> list[str]:
    """Installe l'analyse quotidienne (et la protection en temps reel). Retourne les etapes."""
    _check_windows(system)
    at = _check_time(at)
    result = system.run(["schtasks", "/create", "/f", "/tn", SCAN_TASK, "/sc", "daily",
                         "/st", at, "/tr", _quote(program + AUTO_ARGS)])
    if result.returncode != 0:
        raise ScheduleError((result.stderr or result.stdout or "echec de schtasks").strip())
    done = [f"analyse automatique tous les jours a {at}"]
    if realtime:
        try:
            system.registry.set("HKCU", RUN_KEY, RUN_VALUE, _quote(program + WATCH_ARGS), REG_SZ)
        except RegistryError as exc:
            raise ScheduleError(f"protection en temps reel non installee : {exc}") from exc
        done.append("protection en temps reel a chaque ouverture de session")
    return done


def remove(system: System) -> list[str]:
    _check_windows(system)
    done = []
    if system.run(["schtasks", "/query", "/tn", SCAN_TASK]).returncode == 0:
        result = system.run(["schtasks", "/delete", "/f", "/tn", SCAN_TASK])
        if result.returncode != 0:
            raise ScheduleError((result.stderr or result.stdout or "echec de schtasks").strip())
        done.append("analyse quotidienne supprimee")
    if system.registry.get("HKCU", RUN_KEY, RUN_VALUE):
        system.registry.delete("HKCU", RUN_KEY, RUN_VALUE)
        done.append("protection en temps reel retiree du demarrage")
    return done


def status(system: System) -> dict[str, bool]:
    if not system.is_windows:
        return {"analyse quotidienne": False, "protection en temps reel": False}
    return {"analyse quotidienne": system.run(["schtasks", "/query", "/tn", SCAN_TASK]).returncode == 0,
            "protection en temps reel": bool(system.registry.get("HKCU", RUN_KEY, RUN_VALUE))}

