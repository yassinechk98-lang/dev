"""Reparer mon PC : diagnostic des problemes courants et reparations reversibles.

Principes de securite :
  - le diagnostic ne modifie rien ;
  - rien n'est repare sans demande explicite (identifiant ou bouton) ;
  - chaque modification est sauvegardee dans ~/.freeav/repair-backups et peut etre
    annulee (sauf nettoyage des fichiers temporaires et outils Windows, signales comme tels) ;
  - sous Windows, un point de restauration systeme est cree avant les reparations
    quand FreeAV a les droits administrateur.
"""

import base64
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..paths import APP_DIR, ensure_private_dir
from .checks import ALL_CHECKS, SEVERITY_ORDER, Finding, MalwareCheck, old_temp_files
from .platform import RegistryError, System

BACKUP_DIR = APP_DIR / "repair-backups"
HOSTS_MARK = "# FreeAV a desactive : "

__all__ = ["Finding", "System", "diagnose", "apply_fixes", "undo", "list_backups", "FixResult"]


@dataclass
class FixResult:
    finding: Finding
    ok: bool
    message: str


def diagnose(system: System | None = None, is_malware: MalwareCheck | None = None) -> list[Finding]:
    system = system or System()
    is_malware = is_malware or (lambda path: None)
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        try:
            findings.extend(check(system, is_malware))
        except Exception as exc:  # un diagnostic qui echoue ne doit pas cacher les autres
            findings.append(Finding(key=f"error:{check.__name__}", category="Erreur",
                                    title=f"Diagnostic impossible ({check.__name__})",
                                    detail=str(exc), severity="info"))
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.category, f.title))


def _encode(value):
    return {"bytes": base64.b64encode(value).decode()} if isinstance(value, bytes) else value


def _decode(value):
    return base64.b64decode(value["bytes"]) if isinstance(value, dict) and "bytes" in value else value


def _apply(action: dict, system: System, backup_dir: Path) -> tuple[str, dict | None]:
    """Execute une action et retourne (message, action inverse pour l'annulation)."""
    kind = action["type"]
    reg = system.registry
    if kind in ("reg_delete", "reg_set"):
        old = reg.get(action["hive"], action["key"], action["name"])
        inverse = ({"type": "reg_set", "hive": action["hive"], "key": action["key"],
                    "name": action["name"], "value": _encode(old[0]), "kind": old[1]} if old else
                   {"type": "reg_delete", "hive": action["hive"], "key": action["key"],
                    "name": action["name"]})
        if kind == "reg_delete":
            reg.delete(action["hive"], action["key"], action["name"])
        else:
            reg.set(action["hive"], action["key"], action["name"], _decode(action["value"]),
                    action["kind"])
        return "registre modifie", inverse
    if kind == "file_move":
        source = Path(action["path"])
        ensure_private_dir(backup_dir)
        dest = backup_dir / f"{uuid.uuid4().hex[:8]}_{source.name}"
        shutil.move(str(source), dest)
        return f"deplace dans {dest}", {"type": "file_restore", "from": str(dest), "to": str(source)}
    if kind == "file_restore":
        source, target = Path(action["from"]), Path(action["to"])
        if target.exists():
            raise FileExistsError(f"{target} existe deja")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), target)
        return "fichier remis en place", None
    if kind == "hosts_comment":
        text = system.hosts_path.read_bytes().decode("latin-1")
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.rstrip("\r\n") == action["line"]:
                ending = line[len(line.rstrip("\r\n")):]
                lines[i] = HOSTS_MARK + action["line"] + (ending or "\n")
                system.hosts_path.write_bytes("".join(lines).encode("latin-1"))
                return "ligne desactivee", {"type": "hosts_uncomment", "line": action["line"]}
        raise ValueError("la ligne n'est plus dans le fichier hosts")
    if kind == "hosts_uncomment":
        text = system.hosts_path.read_bytes().decode("latin-1")
        marked = HOSTS_MARK + action["line"]
        if marked not in text:
            raise ValueError("la ligne desactivee n'est plus dans le fichier hosts")
        system.hosts_path.write_bytes(text.replace(marked, action["line"], 1).encode("latin-1"))
        return "ligne reactivee", None
    if kind in ("task_disable", "task_enable"):
        flag = "/disable" if kind == "task_disable" else "/enable"
        result = system.run(["schtasks", "/change", "/tn", action["name"], flag])
        if result.returncode != 0:
            raise OSError((result.stderr or result.stdout or "echec de schtasks").strip())
        return ("tache desactivee", {"type": "task_enable", "name": action["name"]}) \
            if kind == "task_disable" else ("tache reactivee", None)
    if kind == "clean_temp":
        directory = Path(action["dir"])
        name = directory.name.lower()
        if "temp" not in name and "tmp" not in name:  # garde-fou : jamais hors d'un dossier temporaire
            raise ValueError(f"{directory} ne ressemble pas a un dossier temporaire")
        removed = freed = 0
        for path in old_temp_files(directory):
            try:
                size = path.stat().st_size
                path.unlink()
                removed, freed = removed + 1, freed + size
            except OSError:
                pass  # fichier utilise par un programme : on le laisse
        return f"{removed} fichiers supprimes, {freed // (1024 * 1024)} Mo liberes", None
    if kind == "command":
        result = system.run(action["args"], timeout=action.get("timeout", 300))
        output = " ".join((result.stdout or result.stderr or "").split())[-300:]
        if result.returncode != 0:
            raise OSError(output or f"code de sortie {result.returncode}")
        return output or "termine", None
    raise ValueError(f"action inconnue : {kind}")


def create_restore_point(system: System) -> bool:
    if not (system.is_windows and system.is_admin):
        return False
    try:
        result = system.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             "Checkpoint-Computer -Description 'FreeAV - avant reparation' "
                             "-RestorePointType MODIFY_SETTINGS"], timeout=600)
        return result.returncode == 0
    except OSError:
        return False


def apply_fixes(findings: list[Finding], system: System | None = None,
                backup_root: Path = BACKUP_DIR) -> tuple[list[FixResult], Path | None]:
    """Repare les problemes choisis. Retourne les resultats et le fichier de sauvegarde."""
    system = system or System()
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{uuid.uuid4().hex[:4]}"
    backup_dir = backup_root / stamp
    results, undo_steps = [], []
    for finding in findings:
        if not finding.fixable:
            results.append(FixResult(finding, False, "rien a reparer automatiquement"))
            continue
        if finding.needs_admin and not system.is_admin:
            results.append(FixResult(finding, False,
                                     "droits administrateur necessaires : relancez FreeAV "
                                     "en tant qu'administrateur"))
            continue
        try:
            message, inverse = _apply(finding.action, system, backup_dir)
        except (OSError, RegistryError, ValueError) as exc:
            results.append(FixResult(finding, False, str(exc)))
            continue
        if inverse:
            undo_steps.append({"title": finding.title, "action": inverse})
        results.append(FixResult(finding, True, message))
    if not undo_steps:
        return results, None
    ensure_private_dir(backup_root)
    journal = backup_root / f"{stamp}.json"
    journal.write_text(json.dumps({"date": time.time(), "steps": undo_steps}, indent=1),
                       encoding="utf-8")
    return results, journal


def list_backups(backup_root: Path = BACKUP_DIR) -> list[Path]:
    return sorted(Path(backup_root).glob("*.json")) if Path(backup_root).is_dir() else []


def undo(journal: Path | None = None, system: System | None = None,
         backup_root: Path = BACKUP_DIR) -> list[tuple[str, bool, str]]:
    """Annule une serie de reparations (la derniere par defaut), dans l'ordre inverse."""
    system = system or System()
    if journal is None:
        backups = list_backups(backup_root)
        if not backups:
            raise FileNotFoundError("aucune reparation a annuler")
        journal = backups[-1]
    data = json.loads(Path(journal).read_text(encoding="utf-8"))
    report, remaining = [], []
    for step in reversed(data["steps"]):
        try:
            message, _ = _apply(step["action"], system, Path(journal).with_suffix(""))
            report.append((step["title"], True, message))
        except (OSError, RegistryError, ValueError) as exc:
            report.append((step["title"], False, str(exc)))
            remaining.insert(0, step)
    if remaining:
        data["steps"] = remaining
        Path(journal).write_text(json.dumps(data, indent=1), encoding="utf-8")
    else:
        Path(journal).rename(Path(journal).with_suffix(".annule"))
    return report
