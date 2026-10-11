"""Analyse rapide : les endroits ou les malwares arrivent ou s'installent le plus souvent,
en quelques minutes au lieu d'une analyse complete du disque.

  - Telechargements et Bureau (les votres et ceux de "Public") ;
  - le dossier temporaire de votre session, ou se deballent les installateurs ;
  - les dossiers "Demarrage" et les programmes lances a l'ouverture de session (cles Run).
"""

import sys
from pathlib import Path

from .repair import checks
from .repair.platform import System
from .watcher import default_folders


def quick_targets(system: System | None = None) -> list[Path]:
    system = system or System()
    targets = list(default_folders(system.home))
    if system.is_windows and "PUBLIC" in system.environ:
        public = Path(system.environ["PUBLIC"])
        targets += [public / "Desktop", public / "Downloads"]
    targets += system.temp_dirs()[:1]  # le Temp de la session, pas celui partage de Windows
    targets += checks.startup_folders(system)
    if system.registry:
        for hive, key in checks.RUN_KEYS:
            for _name, value, _kind in system.registry.values(hive, key):
                program = checks.target_of(str(value), system)
                if program and program.is_absolute():
                    targets.append(program)
    seen, result = set(), []
    for target in targets:
        key = str(target).lower() if system.is_windows else str(target)
        if key not in seen and target.exists():
            seen.add(key)
            result.append(target)
    return result


def quick_exclusions() -> set[Path]:
    """FreeAV.exe se deballe dans le dossier temporaire : on ne s'analyse pas soi-meme."""
    unpacked = getattr(sys, "_MEIPASS", None)
    return {Path(unpacked)} if unpacked else set()
