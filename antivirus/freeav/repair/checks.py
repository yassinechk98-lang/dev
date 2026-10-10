"""Diagnostics : chaque fonction inspecte une partie du systeme et retourne des Finding.

Les diagnostics ne modifient jamais rien. Chaque Finding reparable decrit sa
reparation dans `action` (donnees simples), executee ensuite par fixes.py.
"""

import hashlib
import ipaddress
import json
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .platform import System

REG_SZ, REG_EXPAND_SZ, REG_DWORD = 1, 2, 4

DANGER, SUSPECT, INFO, TOOL = "danger", "suspect", "info", "outil"
SEVERITY_ORDER = {DANGER: 0, SUSPECT: 1, INFO: 2, TOOL: 3}


@dataclass
class Finding:
    key: str          # identifiant stable du probleme
    category: str
    title: str
    detail: str
    severity: str
    fix_label: str = ""          # vide : rien a reparer automatiquement
    action: dict = field(default_factory=dict)
    needs_admin: bool = False
    undoable: bool = True

    @property
    def id(self) -> str:
        return hashlib.sha1(self.key.encode("utf-8")).hexdigest()[:8]

    @property
    def fixable(self) -> bool:
        return bool(self.action)


# Une fonction qui dit si un fichier est un malware connu (nom de la menace) ou None.
MalwareCheck = Callable[[Path], str | None]

RUN_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
]
SUSPICIOUS_DIRS = [r"\appdata\local\temp", r"\windows\temp", r"\downloads", r"\telechargements",
                   r"\users\public", r"$recycle.bin", "/tmp/", "/var/tmp/", "/dev/shm/"]
SUSPICIOUS_COMMANDS = [re.compile(p, re.I) for p in (
    r"powershell.*\s-(e|enc|encodedcommand)\s", r"\bmshta(\.exe)?\b", r"\bregsvr32\b.*\/i:http",
    r"\b(wscript|cscript)(\.exe)?\b.*\\(temp|appdata)\\", r"\bcertutil\b.*-urlcache",
    r"\bcurl\b.*\|\s*(sh|bash)", r"\bwget\b.*\|\s*(sh|bash)")]
SCRIPT_SUFFIXES = {".exe", ".scr", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".ps1",
                   ".hta", ".pif", ".com"}
PROTECTED_DOMAINS = ("microsoft.com", "windowsupdate.com", "windows.com", "live.com", "bing.com",
                     "google.com", "googleapis.com", "mozilla.org", "apple.com", "github.com",
                     "virustotal.com", "abuse.ch", "clamav.net", "malwarebytes.com", "avast.com",
                     "avg.com", "kaspersky.com", "bitdefender.com", "eset.com", "norton.com",
                     "mcafee.com", "sophos.com", "trendmicro.com", "f-secure.com")


def _ip_kind(ip: str) -> str:
    """'block' (127.x, 0.0.0.0...), 'local' (reseau prive) ou 'public'."""
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return "public"
    if addr.is_loopback or addr.is_unspecified or addr.is_multicast or str(addr) == "255.255.255.255":
        return "block"
    if addr.is_private or addr.is_link_local:
        return "local"
    return "public"


def target_of(command: str, system: System) -> Path | None:
    """Extrait le programme lance par une ligne de commande de demarrage."""
    command = system.expand(command.strip())
    if command.startswith('"'):
        end = command.find('"', 1)
        return Path(command[1:end]) if end > 1 else None
    match = re.match(r"(.+?\.(exe|com|bat|cmd|vbs|js|ps1|scr|hta))(\s|$)", command, re.I)
    if match:
        return Path(match.group(1))
    return Path(command.split()[0]) if command else None


def _judge_command(command: str, system: System, is_malware: MalwareCheck):
    """Retourne (gravite, raison) pour une commande lancee automatiquement, ou None si saine."""
    target = target_of(command, system)
    lowered = command.lower().replace("/", "\\") if system.is_windows else command.lower()
    exists = bool(target and target.is_absolute() and target.is_file())
    if exists and (threat := is_malware(target)):
        return DANGER, f"programme malveillant ({threat})"
    # Un emplacement suspect compte plus qu'un programme disparu : un malware peut
    # s'effacer en laissant sa tache, prete a le retelecharger.
    if any(d in lowered for d in SUSPICIOUS_DIRS):
        return SUSPECT, "lance depuis un dossier temporaire ou de telechargement"
    if any(p.search(command) for p in SUSPICIOUS_COMMANDS):
        return SUSPECT, "commande cachee ou telechargement de code, typique des malwares"
    if target and target.is_absolute() and not exists and target.suffix:
        return INFO, "le programme n'existe plus (entree orpheline)"
    return None


def check_startup_registry(system: System, is_malware: MalwareCheck) -> list[Finding]:
    findings = []
    if not system.registry:
        return findings
    for hive, key in RUN_KEYS:
        for name, value, _kind in system.registry.values(hive, key):
            verdict = _judge_command(str(value), system, is_malware)
            if not verdict:
                continue
            severity, reason = verdict
            findings.append(Finding(
                key=f"run:{hive}\\{key}:{name}", category="Demarrage",
                title=f"Programme au demarrage : {name}", detail=f"{value} - {reason}",
                severity=severity, fix_label="Retirer du demarrage (sauvegarde)",
                action={"type": "reg_delete", "hive": hive, "key": key, "name": name},
                needs_admin=hive == "HKLM"))
    return findings


WINLOGON = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"


def check_winlogon(system: System, is_malware: MalwareCheck) -> list[Finding]:
    """Shell et Userinit detournes : une technique classique pour relancer un malware."""
    findings = []
    if not system.registry:
        return findings
    root = system.environ.get("SystemRoot", r"C:\Windows")
    expected = {"Shell": "explorer.exe", "Userinit": rf"{root}\system32\userinit.exe,"}
    for name, good in expected.items():
        current = system.registry.get("HKLM", WINLOGON, name)
        if current and str(current[0]).strip().lower() not in (good.lower(), good.lower().rstrip(",")):
            findings.append(Finding(
                key=f"winlogon:{name}", category="Demarrage",
                title=f"Ouverture de session detournee ({name})",
                detail=f"valeur actuelle : {current[0]} (attendu : {good})", severity=DANGER,
                fix_label="Remettre la valeur Windows d'origine",
                action={"type": "reg_set", "hive": "HKLM", "key": WINLOGON, "name": name,
                        "value": good, "kind": REG_SZ}, needs_admin=True))
    user_shell = system.registry.get("HKCU", WINLOGON, "Shell")
    if user_shell:
        findings.append(Finding(
            key="winlogon:HKCU:Shell", category="Demarrage",
            title="Ouverture de session detournee (Shell utilisateur)",
            detail=f"valeur : {user_shell[0]}", severity=DANGER,
            fix_label="Supprimer le detournement",
            action={"type": "reg_delete", "hive": "HKCU", "key": WINLOGON, "name": "Shell"}))
    return findings


def startup_folders(system: System) -> list[Path]:
    if system.is_windows:
        rel = Path("Microsoft", "Windows", "Start Menu", "Programs")
        dirs = []
        if "APPDATA" in system.environ:
            dirs.append(Path(system.environ["APPDATA"]) / rel / "Startup")
        if "ProgramData" in system.environ:
            dirs.append(Path(system.environ["ProgramData"]) / rel / "StartUp")
        return dirs
    return [system.home / ".config" / "autostart"]


def check_startup_folders(system: System, is_malware: MalwareCheck) -> list[Finding]:
    findings = []
    for folder in startup_folders(system):
        if not folder.is_dir():
            continue
        for item in sorted(folder.iterdir()):
            if not item.is_file():
                continue
            verdict = None
            if threat := is_malware(item):
                verdict = (DANGER, f"fichier malveillant ({threat})")
            elif item.suffix.lower() == ".desktop":
                exec_line = next((ln[5:] for ln in item.read_text(errors="replace").splitlines()
                                  if ln.startswith("Exec=")), "")
                verdict = _judge_command(exec_line, system, is_malware) if exec_line else None
            elif item.suffix.lower() in SCRIPT_SUFFIXES:
                verdict = (SUSPECT, "script ou programme place directement dans le demarrage")
            if verdict:
                findings.append(Finding(
                    key=f"startupdir:{item}", category="Demarrage",
                    title=f"Fichier de demarrage : {item.name}", detail=f"{item} - {verdict[1]}",
                    severity=verdict[0], fix_label="Retirer du demarrage (sauvegarde)",
                    action={"type": "file_move", "path": str(item)},
                    needs_admin="ProgramData" in str(item)))
    return findings


TASKS_PS = ("Get-ScheduledTask | Where-Object { $_.State -ne 'Disabled' -and "
            "$_.TaskPath -notlike '\\Microsoft\\*' } | ForEach-Object { [pscustomobject]@{ "
            "Name=$_.TaskName; Path=$_.TaskPath; Actions=(($_.Actions | ForEach-Object { "
            "(($_.Execute + ' ' + $_.Arguments).Trim()) }) -join ' | ') } } | ConvertTo-Json -Compress")


def check_scheduled_tasks(system: System, is_malware: MalwareCheck) -> list[Finding]:
    if not system.is_windows:
        return []
    try:
        result = system.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", TASKS_PS])
        tasks = json.loads(result.stdout or "[]")
    except (OSError, ValueError):
        return []
    findings = []
    for task in [tasks] if isinstance(tasks, dict) else tasks:
        full_name = f"{task.get('Path', '')}{task.get('Name', '')}"
        for command in str(task.get("Actions") or "").split(" | "):
            verdict = _judge_command(command, system, is_malware) if command else None
            if verdict and verdict[0] != INFO:
                findings.append(Finding(
                    key=f"task:{full_name}", category="Taches planifiees",
                    title=f"Tache planifiee : {task.get('Name')}", detail=f"{command} - {verdict[1]}",
                    severity=verdict[0], fix_label="Desactiver la tache",
                    action={"type": "task_disable", "name": full_name}, needs_admin=True))
                break
    return findings


def check_hosts(system: System, is_malware: MalwareCheck) -> list[Finding]:
    """Le fichier hosts peut rediriger vos sites (banque, mises a jour) vers un pirate."""
    try:
        # latin-1 : lecture sans perte, quel que soit l'encodage du fichier
        lines = system.hosts_path.read_bytes().decode("latin-1").splitlines()
    except OSError:
        return []
    findings = []
    for number, raw in enumerate(lines):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        ip, names = parts[0], [n.lower() for n in parts[1:]]
        if not names or any(n in ("localhost", "localhost.localdomain") for n in names):
            continue
        protected = [n for n in names if any(n == d or n.endswith("." + d) for d in PROTECTED_DOMAINS)]
        kind = _ip_kind(ip)
        if protected:
            what = "bloque" if kind == "block" else f"redirige vers {ip}"
            severity, reason = DANGER, f"{', '.join(protected)} {what} (mises a jour ou securite)"
        elif kind == "public":
            severity, reason = SUSPECT, f"{', '.join(names)} redirige vers {ip}"
        else:  # blocage publicitaire ou machine du reseau local : normal
            continue
        findings.append(Finding(
            key=f"hosts:{raw.strip()}", category="Reseau", title="Redirection dans le fichier hosts",
            detail=reason, severity=severity, fix_label="Desactiver la ligne (sauvegarde)",
            action={"type": "hosts_comment", "line": raw, "index": number},
            needs_admin=True))
    return findings


INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def check_proxy(system: System, is_malware: MalwareCheck) -> list[Finding]:
    """Un proxy impose par un malware permet d'espionner ou de modifier vos connexions."""
    findings = []
    if system.registry:
        enabled = system.registry.get("HKCU", INTERNET_SETTINGS, "ProxyEnable")
        server = system.registry.get("HKCU", INTERNET_SETTINGS, "ProxyServer")
        if enabled and enabled[0] == 1 and server:
            findings.append(Finding(
                key=f"proxy:{server[0]}", category="Reseau", title="Proxy Internet active",
                detail=f"toutes vos connexions passent par {server[0]}. Normal en entreprise, "
                       "suspect sur un PC personnel", severity=SUSPECT,
                fix_label="Desactiver le proxy",
                action={"type": "reg_set", "hive": "HKCU", "key": INTERNET_SETTINGS,
                        "name": "ProxyEnable", "value": 0, "kind": REG_DWORD}))
        pac = system.registry.get("HKCU", INTERNET_SETTINGS, "AutoConfigURL")
        if pac and str(pac[0]).strip():
            findings.append(Finding(
                key=f"pac:{pac[0]}", category="Reseau", title="Script de configuration de proxy",
                detail=f"script impose : {pac[0]}", severity=SUSPECT,
                fix_label="Supprimer le script (sauvegarde)",
                action={"type": "reg_delete", "hive": "HKCU", "key": INTERNET_SETTINGS,
                        "name": "AutoConfigURL"}))
    if system.is_windows:
        try:
            out = system.run(["netsh", "winhttp", "show", "proxy"]).stdout
        except OSError:
            out = ""
        if out and not re.search(r"direct|direct access|acc[eè]s direct", out, re.I):
            findings.append(Finding(
                key="winhttp-proxy", category="Reseau", title="Proxy systeme (WinHTTP) configure",
                detail=" ".join(out.split())[:200], severity=SUSPECT,
                fix_label="Reinitialiser le proxy systeme",
                action={"type": "command", "args": ["netsh", "winhttp", "reset", "proxy"]},
                needs_admin=True, undoable=False))
    return findings


BROWSER_POLICIES = [("Google Chrome", r"SOFTWARE\Policies\Google\Chrome"),
                    ("Microsoft Edge", r"SOFTWARE\Policies\Microsoft\Edge")]
HIJACK_VALUES = ("HomepageLocation", "NewTabPageLocation", "DefaultSearchProviderSearchURL")


def check_browser_policies(system: System, is_malware: MalwareCheck) -> list[Finding]:
    """Les adwares imposent extensions, page d'accueil ou moteur de recherche par strategie."""
    findings = []
    if not system.registry:
        return findings
    for browser, base in BROWSER_POLICIES:
        for hive in ("HKCU", "HKLM"):
            for name, value, _ in system.registry.values(hive, base + r"\ExtensionInstallForcelist"):
                findings.append(Finding(
                    key=f"forcelist:{hive}:{base}:{name}", category="Navigateur",
                    title=f"Extension imposee dans {browser}",
                    detail=f"{value} - impossible a desinstaller depuis le navigateur",
                    severity=SUSPECT, fix_label="Retirer l'obligation (sauvegarde)",
                    action={"type": "reg_delete", "hive": hive,
                            "key": base + r"\ExtensionInstallForcelist", "name": name},
                    needs_admin=hive == "HKLM"))
            for name in HIJACK_VALUES:
                current = system.registry.get(hive, base, name)
                if current:
                    findings.append(Finding(
                        key=f"policy:{hive}:{base}:{name}", category="Navigateur",
                        title=f"{browser} : {name} impose", detail=str(current[0]),
                        severity=SUSPECT, fix_label="Retirer l'obligation (sauvegarde)",
                        action={"type": "reg_delete", "hive": hive, "key": base, "name": name},
                        needs_admin=hive == "HKLM"))
    return findings


DEFENDER = r"SOFTWARE\Policies\Microsoft\Windows Defender"
DEFENDER_SWITCHES = [(DEFENDER, "DisableAntiSpyware"), (DEFENDER, "DisableAntiVirus"),
                     (DEFENDER + r"\Real-Time Protection", "DisableRealtimeMonitoring"),
                     (DEFENDER + r"\Real-Time Protection", "DisableBehaviorMonitoring"),
                     (DEFENDER + r"\Real-Time Protection", "DisableOnAccessProtection"),
                     (DEFENDER + r"\Real-Time Protection", "DisableIOAVProtection")]


def check_defender(system: System, is_malware: MalwareCheck) -> list[Finding]:
    """Beaucoup de malwares desactivent Microsoft Defender ou s'y ajoutent en exclusion."""
    findings = []
    if not system.registry:
        return findings
    for key, name in DEFENDER_SWITCHES:
        current = system.registry.get("HKLM", key, name)
        if current and current[0] == 1:
            findings.append(Finding(
                key=f"defender:{name}", category="Protection",
                title="Microsoft Defender desactive par une strategie", detail=f"{name} = 1",
                severity=DANGER, fix_label="Reactiver Defender (sauvegarde)",
                action={"type": "reg_delete", "hive": "HKLM", "key": key, "name": name},
                needs_admin=True))
    for name, _value, _ in system.registry.values("HKLM", DEFENDER + r"\Exclusions\Paths"):
        findings.append(Finding(
            key=f"defender-exclusion:{name}", category="Protection",
            title="Dossier exclu de Microsoft Defender", detail=name, severity=SUSPECT,
            fix_label="Retirer l'exclusion (sauvegarde)",
            action={"type": "reg_delete", "hive": "HKLM", "key": DEFENDER + r"\Exclusions\Paths",
                    "name": name}, needs_admin=True))
    return findings


TEMP_MIN_AGE = 24 * 3600
TEMP_REPORT_SIZE = 100 * 1024 * 1024


def old_temp_files(directory: Path, now: float | None = None) -> list[Path]:
    now = now or time.time()
    files = []
    for path in directory.rglob("*"):
        try:
            st = path.lstat()
        except OSError:
            continue
        if path.is_file() and not path.is_symlink() and now - st.st_mtime > TEMP_MIN_AGE:
            files.append(path)
    return files


def check_temp_files(system: System, is_malware: MalwareCheck) -> list[Finding]:
    findings = []
    for directory in system.temp_dirs():
        if not directory.is_dir():
            continue
        files = old_temp_files(directory)
        size = 0
        for f in files:
            try:
                size += f.stat().st_size
            except OSError:
                pass
        if size >= TEMP_REPORT_SIZE:
            findings.append(Finding(
                key=f"temp:{directory}", category="Nettoyage",
                title=f"{size // (1024 * 1024)} Mo de fichiers temporaires",
                detail=f"{len(files)} fichiers de plus de 24 h dans {directory}", severity=INFO,
                fix_label="Supprimer les fichiers temporaires",
                action={"type": "clean_temp", "dir": str(directory)}, undoable=False,
                needs_admin="windows" in str(directory).lower()))
    return findings


def check_disk_space(system: System, is_malware: MalwareCheck) -> list[Finding]:
    root = Path(system.environ.get("SystemDrive", "C:") + "\\") if system.is_windows else Path("/")
    try:
        usage = shutil.disk_usage(root)
    except OSError:
        return []
    free_pct = usage.free * 100 / usage.total if usage.total else 100
    if free_pct >= 10 and usage.free >= 5 * 1024 ** 3:
        return []
    return [Finding(key=f"disk:{root}", category="Nettoyage", title="Disque presque plein",
                    detail=f"{usage.free // 1024 ** 3} Go libres sur {usage.total // 1024 ** 3} Go "
                           f"({free_pct:.0f} %) : le PC peut ralentir ou planter",
                    severity=SUSPECT if free_pct < 5 else INFO)]


def windows_tools(system: System, is_malware: MalwareCheck) -> list[Finding]:
    """Outils de reparation integres a Windows, proposes a la demande."""
    if not system.is_windows:
        return []
    return [
        Finding(key="tool:sfc", category="Outils Windows", title="Reparer les fichiers systeme",
                detail="sfc /scannow : verifie et remplace les fichiers Windows abimes (long)",
                severity=TOOL, fix_label="Lancer SFC",
                action={"type": "command", "args": ["sfc", "/scannow"], "timeout": 3600},
                needs_admin=True, undoable=False),
        Finding(key="tool:dism", category="Outils Windows", title="Reparer l'image de Windows",
                detail="DISM /RestoreHealth : a lancer si SFC n'arrive pas a tout reparer (long)",
                severity=TOOL, fix_label="Lancer DISM",
                action={"type": "command", "timeout": 7200,
                        "args": ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"]},
                needs_admin=True, undoable=False),
        Finding(key="tool:flushdns", category="Outils Windows", title="Vider le cache DNS",
                detail="ipconfig /flushdns : utile apres avoir corrige le fichier hosts",
                severity=TOOL, fix_label="Vider le cache",
                action={"type": "command", "args": ["ipconfig", "/flushdns"]}, undoable=False),
    ]


ALL_CHECKS = [check_startup_registry, check_winlogon, check_startup_folders, check_scheduled_tasks,
              check_hosts, check_proxy, check_browser_policies, check_defender,
              check_temp_files, check_disk_space, windows_tools]
