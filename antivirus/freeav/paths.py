"""Emplacements des donnees de FreeAV, tous sous ~/.freeav et accessibles au seul utilisateur."""

import os
from pathlib import Path

APP_DIR = Path.home() / ".freeav"
QUARANTINE_DIR = APP_DIR / "quarantine"
SIGNATURES_DIR = APP_DIR / "signatures"  # bases telechargees (MalwareBazaar...)
YARA_DIR = APP_DIR / "yara"              # regles YARA ajoutees par l'utilisateur


def ensure_private_dir(path: Path) -> Path:
    """Cree le dossier si besoin et le rend lisible par son seul proprietaire (0700)."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o700)
    return path
