"""Reparer mon PC : diagnostic des problemes courants et reparations reversibles.

Principes de securite :
  - le diagnostic ne modifie rien ;
  - rien n'est repare sans demande explicite (identifiant ou bouton) ;
  - chaque modification est sauvegardee dans ~/.freeav/repair-backups et peut etre
    annulee (sauf nettoyage des fichiers temporaires et outils Windows, signales comme tels) ;
  - sous Windows, un point de restauration systeme est cree avant les reparations
    quand FreeAV a les droits administrateur ;
  - l'annulation ne rejoue que des actions inverses prevues (jamais une commande), sur
    les seules cles de registre que FreeAV repare, depuis son propre dossier de sauvegarde ;
  - en administrateur, les sauvegardes vont dans %ProgramData%\\FreeAV, que seuls les
    administrateurs peuvent modifier : un programme sans droits ne peut pas y deposer un
    faux journal pour obtenir les droits administrateur au prochain "Annuler".
"""

import base64
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..paths import APP_DIR, ensure_private_dir
from . import checks
from .checks import ALL_CHECKS, SEVERITY_ORDER, Finding, MalwareCheck, old_temp_files, \
    within
from .platform import RegistryError, System

BACKUP_DIR = APP_DIR / "repair-backups"
HOSTS_MARK = "# FreeAV a desactive : "

__all__ = ["Finding", "System", "diagnose", "apply_fixes", "undo", "list_backups", "FixResult"]

UNDO_ACTIONS = {"reg_set", "reg_delete", "file_restore", "hosts_uncomment", "task_enable"}
REPAIRED_KEYS = (
    [(hive, key) for hive, key in checks.RUN_KEYS]
    + [(hive, checks.WINLOGON) for hive in ("HKLM", "HKCU")]
    + [("HKCU", checks.INTERNET_SETTINGS)]
    + [(hive, key) for _, key in checks.BROWSER_POLICIES for hive in ("HKLM", "HKCU")]
    + [("HKLM", checks.DEFENDER)]
)


class UnsafeBackupError(ValueError):
    """Journal d'annulation ou dossier de sauvegarde auquel FreeAV ne doit pas faire confiance."""


def _repaired_key(hive: str, key: str) -> bool:
    key = key.lower().rstrip("\\")
    return any(hive == h and (key == k.lower() or key.startswith(k.lower() + "\\"))
               for h, k in REPAIRED_KEYS)


def check_undo_step(action: dict, backup_dir: Path) -> None:
    """Refuse toute etape d'annulation que FreeAV n'aurait pas pu ecrire lui-meme."""
    kind = action.get("type") if isinstance(action, dict) else None
    if kind not in UNDO_ACTIONS:
        raise UnsafeBackupError(f"action d'annulation refusee : {kind!r}")
    if kind in ("reg_set", "reg_delete"):
        if not (isinstance(action.get("hive"), str) and isinstance(action.get("key"), str)
                and _repaired_key(action["hive"], action["key"])):
            raise UnsafeBackupError(f"cle de registre hors du perimetre de FreeAV : "
                                    f"{action.get('hive')}\\{action.get('key')}")
    if kind == "file_restore":
        source = Path(str(action.get("from", "")))
        target = Path(str(action.get("to", "")))
        if not (source.is_absolute() and target.is_absolute()
                and within(source, backup_dir) and source.parent == backup_dir
                and source.name.endswith("_" + target.name)):
            raise UnsafeBackupError("restauration de fichier refusee : elle ne vient pas de la "
                                    "sauvegarde de cette reparation")


PROGRAMDATA_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$root = [Environment]::GetFolderPath('CommonApplicationData')
$p = [IO.Path]::Combine($root, 'FreeAV')
$trusted = 'S-1-5-32-544', 'S-1-5-18'
$sid = [Security.Principal.SecurityIdentifier]
if ([IO.Directory]::Exists($p) -or [IO.File]::Exists($p)) {
  $item = [IO.DirectoryInfo]::new($p)
  $owner = $item.GetAccessControl('Owner').GetOwner($sid).Value
  if (($trusted -notcontains $owner) -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    # Dossier cree par quelqu'un d'autre : on le met de cote sans rien lire ni suivre dedans.
    [IO.Directory]::Move($p, $p + '.non-sur-' + [DateTime]::Now.ToString('yyyyMMddHHmmss'))
  }
}
$dir = [IO.Directory]::CreateDirectory($p)
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetOwner([Security.Principal.SecurityIdentifier]'S-1-5-32-544')
$acl.SetAccessRuleProtection($true, $false)
foreach ($t in $trusted) {
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
    [Security.Principal.SecurityIdentifier]$t, 'FullControl', 'ContainerInherit,ObjectInherit',
    'None', 'Allow'))
}
$dir.SetAccessControl($acl)
$check = ([IO.DirectoryInfo]::new($p)).GetAccessControl()
if ($trusted -notcontains $check.GetOwner($sid).Value) { 'ERREUR proprietaire'; exit 3 }
foreach ($rule in $check.GetAccessRules($true, $true, $sid)) {
  if ($rule.AccessControlType -eq 'Allow' -and $trusted -notcontains $rule.IdentityReference.Value) {
    ('ERREUR acces ' + $rule.IdentityReference.Value); exit 4
  }
}
'OK ' + $p
"""


def admin_backup_root(system: System) -> Path:
    """%ProgramData%\\FreeAV\\repair-backups, verrouille pour les seuls administrateurs."""
    result = system.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                         "Bypass", "-Command", PROGRAMDATA_SCRIPT], timeout=60)
    lines = (result.stdout or "").strip().splitlines()
    if result.returncode != 0 or not lines or not lines[-1].startswith("OK "):
        raise UnsafeBackupError("impossible de proteger le dossier de sauvegarde "
                                f"administrateur : {(result.stdout or result.stderr).strip()}")
    return Path(lines[-1][3:].strip()) / "repair-backups"


def backup_root_for(system: System) -> Path:
    if system.is_windows and system.is_admin:
        return admin_backup_root(system)
    return BACKUP_DIR


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
                if not within(path, directory):  # re-verifie juste avant de supprimer
                    continue
                size = path.lstat().st_size
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
                backup_root: Path | None = None) -> tuple[list[FixResult], Path | None]:
    """Repare les problemes choisis. Retourne les resultats et le fichier de sauvegarde."""
    system = system or System()
    backup_root = Path(backup_root) if backup_root else backup_root_for(system)
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


def list_backups(backup_root: Path | None = None, system: System | None = None) -> list[Path]:
    if backup_root is None:
        backup_root = backup_root_for(system or System())
    return sorted(Path(backup_root).glob("*.json")) if Path(backup_root).is_dir() else []


def undo(journal: Path | None = None, system: System | None = None,
         backup_root: Path | None = None) -> list[tuple[str, bool, str]]:
    """Annule une serie de reparations (la derniere par defaut), dans l'ordre inverse.
    Seuls les journaux du dossier de sauvegarde de FreeAV sont acceptes, et chaque etape
    est verifiee avant d'etre rejouee."""
    system = system or System()
    backup_root = Path(backup_root) if backup_root else backup_root_for(system)
    if journal is None:
        backups = list_backups(backup_root)
        if not backups:
            raise FileNotFoundError("aucune reparation a annuler"
                                    + (" (celles faites sans droits administrateur s'annulent "
                                       "sans ces droits)" if system.is_admin and system.is_windows
                                       else ""))
        journal = backups[-1]
    journal = Path(journal)
    if journal.suffix != ".json" or journal.parent.resolve() != backup_root.resolve() \
            or journal.is_symlink():
        raise UnsafeBackupError(f"{journal} n'est pas un journal du dossier de sauvegarde "
                                f"{backup_root}")
    data = json.loads(journal.read_text(encoding="utf-8"))
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list):
        raise UnsafeBackupError("journal d'annulation illisible")
    backup_dir = journal.with_suffix("")
    for step in steps:  # tout ou rien : un journal douteux n'est pas rejoue du tout
        if not isinstance(step, dict):
            raise UnsafeBackupError("journal d'annulation illisible")
        check_undo_step(step.get("action"), backup_dir)
    report, remaining = [], []
    for step in reversed(steps):
        try:
            message, _ = _apply(step["action"], system, backup_dir)
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
