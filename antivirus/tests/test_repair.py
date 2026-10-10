"""Tests du module "Reparer mon PC", avec un faux Windows (registre et commandes simules)."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from freeav import repair
from freeav.cli import main
from freeav.repair import checks
from freeav.repair.checks import DANGER, INFO, REG_DWORD, REG_SZ, SUSPECT
from freeav.repair.platform import RegistryError, System


class FakeRegistry:
    def __init__(self, data=None, read_only=()):
        self.data = {k: dict(v) for k, v in (data or {}).items()}
        self.read_only = set(read_only)

    def values(self, hive, key):
        return [(n, v, t) for n, (v, t) in self.data.get((hive, key), {}).items()]

    def get(self, hive, key, name):
        return self.data.get((hive, key), {}).get(name)

    def set(self, hive, key, name, value, kind):
        if hive in self.read_only:
            raise RegistryError("droits administrateur necessaires")
        self.data.setdefault((hive, key), {})[name] = (value, kind)

    def delete(self, hive, key, name):
        if hive in self.read_only:
            raise RegistryError("droits administrateur necessaires")
        self.data.get((hive, key), {}).pop(name, None)


class FakeRunner:
    def __init__(self, outputs=None):
        self.outputs = outputs or {}
        self.calls = []

    def __call__(self, args, timeout):
        self.calls.append(args)
        if "CommonApplicationData" in args[-1]:  # dossier de sauvegarde administrateur
            if not hasattr(self, "programdata"):
                self.programdata = Path(tempfile.mkdtemp()) / "ProgramData" / "FreeAV"
            return subprocess.CompletedProcess(args, 0, f"OK {self.programdata}\n", "")
        out, code = self.outputs.get(args[0].lower(), ("", 0))
        return subprocess.CompletedProcess(args, code, out, "")


RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()


@pytest.fixture
def pc(tmp_path):
    """Un faux PC Windows infecte de facon realiste."""
    malware = tmp_path / "AppData" / "Roaming" / "updater.exe"
    malware.parent.mkdir(parents=True)
    malware.write_bytes(EICAR)
    legit = tmp_path / "Program Files" / "OneDrive" / "OneDrive.exe"
    legit.parent.mkdir(parents=True)
    legit.write_bytes(b"MZ programme legitime")
    startup = tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / \
        "Programs" / "Startup"
    startup.mkdir(parents=True)
    (startup / "OneDrive.lnk").write_bytes(b"raccourci")
    (startup / "svchost.vbs").write_text("CreateObject(\"WScript.Shell\").Run \"evil\"")
    hosts = tmp_path / "hosts"
    hosts.write_text("# fichier hosts\r\n127.0.0.1 localhost\r\n0.0.0.0 pub.example.com\r\n"
                     "192.168.1.10 nas\r\n45.67.89.10 www.mabanque.fr\r\n"
                     "127.0.0.1 update.microsoft.com\r\n")
    temp = tmp_path / "Temp"
    temp.mkdir()
    registry = FakeRegistry({
        ("HKCU", RUN): {"OneDrive": (f'"{legit}" /background', REG_SZ),
                        "Updater": (f'"{malware}"', REG_SZ),
                        "Ancien": (f'"{tmp_path / "desinstalle" / "old.exe"}"', REG_SZ),
                        "Loader": ("powershell -w hidden -enc SQBFAFgA", REG_SZ)},
        ("HKLM", checks.WINLOGON): {"Shell": ("explorer.exe, C:\\Users\\Public\\x.exe", REG_SZ),
                                    "Userinit": ("C:\\Windows\\system32\\userinit.exe,", REG_SZ)},
        ("HKCU", checks.INTERNET_SETTINGS): {"ProxyEnable": (1, REG_DWORD),
                                             "ProxyServer": ("45.67.89.11:8080", REG_SZ)},
        ("HKLM", r"SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"): {
            "1": ("abcdefghijklmnopabcdefghijklmnop;https://evil.example/crx", REG_SZ)},
        ("HKCU", r"SOFTWARE\Policies\Microsoft\Edge"): {
            "HomepageLocation": ("https://search-hijack.example", REG_SZ)},
        ("HKLM", checks.DEFENDER + r"\Real-Time Protection"): {
            "DisableRealtimeMonitoring": (1, REG_DWORD)},
        ("HKLM", checks.DEFENDER + r"\Exclusions\Paths"): {"C:\\Users\\Public": (0, REG_DWORD)},
    })
    tasks = ('[{"Name":"GoogleUpdate","Path":"\\\\","Actions":"C:\\\\Program Files\\\\Google\\\\update.exe /ua"},'
             '{"Name":"SysHelper","Path":"\\\\","Actions":"C:\\\\Users\\\\bob\\\\AppData\\\\Local\\\\Temp\\\\h.exe"}]')
    runner = FakeRunner({"powershell": (tasks, 0),
                         "netsh": ("Current WinHTTP proxy settings:\n  Direct access (no proxy server).", 0)})
    system = System(registry=registry, runner=runner, hosts_path=hosts, is_windows=True,
                    is_admin=True, home=tmp_path,
                    environ={"APPDATA": str(tmp_path / "AppData" / "Roaming"),
                             "TEMP": str(temp), "SystemRoot": "C:\\Windows"})
    return system, malware


def is_malware(path):
    return "EICAR-Test-File" if path.read_bytes() == EICAR else None


def by_title(findings):
    return {f.title: f for f in findings}


def test_diagnosis_finds_what_malware_leaves_behind(pc):
    system, _ = pc
    found = by_title(repair.diagnose(system, is_malware))
    assert found["Programme au demarrage : Updater"].severity == DANGER
    assert found["Programme au demarrage : Loader"].severity == SUSPECT
    assert found["Programme au demarrage : Ancien"].severity == INFO
    assert "Programme au demarrage : OneDrive" not in found  # programme legitime
    assert found["Ouverture de session detournee (Shell)"].severity == DANGER
    assert "Ouverture de session detournee (Userinit)" not in found
    assert found["Fichier de demarrage : svchost.vbs"].severity == SUSPECT
    assert "Fichier de demarrage : OneDrive.lnk" not in found
    assert found["Tache planifiee : SysHelper"].severity == SUSPECT
    assert "Tache planifiee : GoogleUpdate" not in found
    assert found["Proxy Internet active"].severity == SUSPECT
    assert "Proxy systeme (WinHTTP) configure" not in found
    assert found["Extension imposee dans Google Chrome"].severity == SUSPECT
    assert found["Microsoft Edge : HomepageLocation impose"].severity == SUSPECT
    assert found["Microsoft Defender desactive par une strategie"].severity == DANGER
    assert found["Dossier exclu de Microsoft Defender"].severity == SUSPECT
    hosts = [f for f in found.values() if f.category == "Reseau" and "hosts" in f.title]
    hosts_details = sorted(f.detail for f in repair.diagnose(system, is_malware)
                           if f.title == "Redirection dans le fichier hosts")
    assert hosts and len(hosts_details) == 2  # banque redirigee + Windows Update bloque
    assert any("www.mabanque.fr" in d for d in hosts_details)
    assert any("update.microsoft.com bloque" in d for d in hosts_details)


def test_diagnosis_changes_nothing(pc):
    system, _ = pc
    before = ({k: dict(v) for k, v in system.registry.data.items()}, system.hosts_path.read_bytes())
    repair.diagnose(system, is_malware)
    assert (system.registry.data, system.hosts_path.read_bytes()) == before
    assert all(call[0].lower() in ("powershell", "netsh") for call in system.runner.calls)


def test_fix_then_undo_restores_everything(pc, tmp_path):
    system, _ = pc
    backups = tmp_path / "backups"
    findings = [f for f in repair.diagnose(system, is_malware)
                if f.fixable and f.undoable and f.category != "Taches planifiees"]
    registry_before = {k: dict(v) for k, v in system.registry.data.items()}
    hosts_before = system.hosts_path.read_bytes()
    results, journal = repair.apply_fixes(findings, system, backup_root=backups)
    assert all(r.ok for r in results), [(r.finding.title, r.message) for r in results]
    assert repair.diagnose(system, is_malware) == [f for f in repair.diagnose(system, is_malware)
                                                    if f.category == "Taches planifiees"
                                                    or not f.undoable or f.severity == "outil"]
    reg = system.registry
    assert reg.get("HKCU", RUN, "Updater") is None
    assert reg.get("HKLM", checks.WINLOGON, "Shell")[0] == "explorer.exe"
    assert reg.get("HKCU", checks.INTERNET_SETTINGS, "ProxyEnable")[0] == 0
    hosts = system.hosts_path.read_text()
    assert "# FreeAV a desactive : 45.67.89.10 www.mabanque.fr" in hosts
    assert "0.0.0.0 pub.example.com" in hosts and "192.168.1.10 nas" in hosts  # laisses tels quels

    report = repair.undo(journal, system, backup_root=backups)
    assert all(ok for _, ok, _ in report), report
    assert system.registry.data == registry_before
    assert system.hosts_path.read_bytes() == hosts_before
    startup = tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / \
        "Programs" / "Startup"
    assert (startup / "svchost.vbs").exists()
    assert repair.list_backups(backups) == []


def test_scheduled_task_is_disabled_and_reenabled(pc, tmp_path):
    system, _ = pc
    task = by_title(repair.diagnose(system, is_malware))["Tache planifiee : SysHelper"]
    results, journal = repair.apply_fixes([task], system, backup_root=tmp_path / "b")
    assert results[0].ok
    assert system.runner.calls[-1] == ["schtasks", "/change", "/tn", "\\SysHelper", "/disable"]
    repair.undo(journal, system, backup_root=tmp_path / "b")
    assert system.runner.calls[-1][-1] == "/enable"


def test_admin_fixes_refused_without_admin_rights(pc, tmp_path):
    system, _ = pc
    system.is_admin = False
    found = by_title(repair.diagnose(system, is_malware))
    defender = found["Microsoft Defender desactive par une strategie"]
    user_entry = found["Programme au demarrage : Updater"]
    results, _ = repair.apply_fixes([defender, user_entry], system, backup_root=tmp_path / "b")
    assert not results[0].ok and "administrateur" in results[0].message
    assert results[1].ok  # une cle HKCU se repare sans droits admin
    assert system.registry.get("HKLM", checks.DEFENDER + r"\Real-Time Protection",
                               "DisableRealtimeMonitoring") == (1, REG_DWORD)


def test_failed_fix_is_reported_and_others_continue(pc, tmp_path):
    system, _ = pc
    found = by_title(repair.diagnose(system, is_malware))
    system.registry.read_only = {"HKLM"}
    results, journal = repair.apply_fixes(
        [found["Ouverture de session detournee (Shell)"], found["Programme au demarrage : Updater"]],
        system, backup_root=tmp_path / "b")
    assert [r.ok for r in results] == [False, True]
    assert len(__import__("json").loads(journal.read_text())["steps"]) == 1


def test_temp_cleanup_only_removes_old_files(pc):
    system, _ = pc
    temp = pc[0].temp_dirs()[0]
    old, recent = temp / "vieux.tmp", temp / "recent.tmp"
    old.write_bytes(b"x" * 1000)
    recent.write_bytes(b"y")
    import os
    os.utime(old, (0, 0))
    finding = checks.Finding(key="t", category="Nettoyage", title="t", detail="", severity=INFO,
                             action={"type": "clean_temp", "dir": str(temp)}, undoable=False)
    results, journal = repair.apply_fixes([finding], system)
    assert results[0].ok and journal is None
    assert not old.exists() and recent.exists()


def test_temp_cleanup_refuses_non_temp_folder(tmp_path):
    folder = tmp_path / "Documents"
    folder.mkdir()
    finding = checks.Finding(key="t", category="Nettoyage", title="t", detail="", severity=INFO,
                             action={"type": "clean_temp", "dir": str(folder)}, undoable=False)
    results, _ = repair.apply_fixes([finding], System(is_windows=False, is_admin=True))
    assert not results[0].ok


def test_hosts_rules_on_ordinary_files(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n127.0.1.1 monpc\n::1 ip6-localhost\n"
                     "0.0.0.0 ads.example.com tracker.example.net\n10.0.0.5 imprimante\n")
    system = System(registry=FakeRegistry(), runner=FakeRunner(), hosts_path=hosts,
                    is_windows=False, is_admin=True, home=tmp_path, environ={})
    assert checks.check_hosts(system, is_malware) == []


def test_linux_autostart_entry_from_tmp_is_suspect(tmp_path):
    autostart = tmp_path / ".config" / "autostart"
    autostart.mkdir(parents=True)
    (autostart / "miner.desktop").write_text("[Desktop Entry]\nExec=/tmp/.x/miner --quiet\n")
    (autostart / "nextcloud.desktop").write_text("[Desktop Entry]\nExec=/usr/bin/nextcloud\n")
    system = System(registry=None, runner=FakeRunner(), hosts_path=tmp_path / "absent",
                    is_windows=False, is_admin=False, home=tmp_path, environ={})
    found = checks.check_startup_folders(system, is_malware)
    assert [f.title for f in found] == ["Fichier de demarrage : miner.desktop"]


def test_windows_tools_run_the_real_commands(pc, tmp_path):
    system, _ = pc
    tools = {f.title: f for f in repair.diagnose(system, is_malware) if f.severity == "outil"}
    results, _ = repair.apply_fixes([tools["Vider le cache DNS"]], system, backup_root=tmp_path)
    assert results[0].ok and system.runner.calls[-1] == ["ipconfig", "/flushdns"]


def test_cli_repair_lists_and_fixes_by_id(pc, monkeypatch, capsys, tmp_path):
    system, _ = pc
    monkeypatch.setattr(repair, "System", lambda: system)
    monkeypatch.setattr(repair, "BACKUP_DIR", tmp_path / "b")
    monkeypatch.setattr("freeav.cli.malware_checker", lambda scanner=None: is_malware)
    assert main(["repair"]) == 1
    out = capsys.readouterr().out
    assert "DANGER" in out and "Updater" in out
    updater_id = by_title(repair.diagnose(system, is_malware))["Programme au demarrage : Updater"].id
    monkeypatch.setattr(repair.apply_fixes, "__defaults__", (None, tmp_path / "b"))
    assert main(["repair", "--fix", updater_id]) == 0
    assert system.registry.get("HKCU", RUN, "Updater") is None
    assert main(["repair", "--fix", "inconnu0"]) == 2


def test_cli_requires_confirmation_for_irreversible_actions(pc, monkeypatch, capsys, tmp_path):
    system, _ = pc
    monkeypatch.setattr(repair, "System", lambda: system)
    monkeypatch.setattr("freeav.cli.malware_checker", lambda scanner=None: is_malware)
    dns = {f.title: f for f in repair.diagnose(system, is_malware)}["Vider le cache DNS"]
    assert main(["repair", "--fix", dns.id]) == 2
    assert "DEFINITIVES" in capsys.readouterr().err
    assert ["ipconfig", "/flushdns"] not in system.runner.calls
    assert main(["repair", "--fix", dns.id, "--yes"]) == 0
    assert system.runner.calls[-1] == ["ipconfig", "/flushdns"]


def test_missing_program_in_temp_folder_is_still_suspect(tmp_path):
    gone = tmp_path / "AppData" / "Local" / "Temp" / "h.exe"  # efface, la tache reste
    system = System(registry=FakeRegistry(), runner=FakeRunner(), hosts_path=tmp_path / "x",
                    is_windows=True, is_admin=True, home=tmp_path, environ={})
    verdict = checks._judge_command(f'"{gone}"'.replace("/", "\\"), system, is_malware)
    assert verdict[0] == SUSPECT


def _forged_journal(backups, steps):
    import json
    backups.mkdir(parents=True, exist_ok=True)
    journal = backups / "20990101-000000-dead.json"
    journal.write_text(json.dumps({"date": 0, "steps": steps}), encoding="utf-8")
    return journal


@pytest.mark.parametrize("action", [
    {"type": "command", "args": ["cmd", "/c", "net", "user", "pirate", "/add"]},
    {"type": "clean_temp", "dir": "C:\\Temp"},
    {"type": "reg_set", "hive": "HKLM", "key": r"SYSTEM\CurrentControlSet\Services\Mal",
     "name": "ImagePath", "value": "C:\\mal.exe", "kind": REG_SZ},
    {"type": "reg_set", "hive": "HKLM", "key": checks.WINLOGON + "Evil", "name": "Shell",
     "value": "mal.exe", "kind": REG_SZ},
    {"type": "file_restore", "from": "C:\\Users\\bob\\Downloads\\mal.dll",
     "to": "C:\\Windows\\System32\\mal.dll"},
])
def test_forged_undo_journal_is_refused_without_running_anything(pc, tmp_path, action):
    """Un programme qui ecrit un faux journal ne doit rien pouvoir faire executer a FreeAV."""
    system, _ = pc
    backups = tmp_path / "b"
    legit = {"type": "reg_delete", "hive": "HKCU", "key": RUN, "name": "Updater"}
    journal = _forged_journal(backups, [{"title": "ok", "action": legit},
                                        {"title": "piege", "action": action}])
    registry_before = {k: dict(v) for k, v in system.registry.data.items()}
    calls_before = len(system.runner.calls)
    with pytest.raises(repair.UnsafeBackupError):
        repair.undo(journal, system, backup_root=backups)
    assert system.registry.data == registry_before  # tout ou rien : meme l'etape valide n'est pas jouee
    assert len(system.runner.calls) == calls_before
    with pytest.raises(repair.UnsafeBackupError):
        repair.undo(None, system, backup_root=backups)  # "Annuler la derniere reparation"


def test_journal_outside_the_backup_folder_is_refused(pc, tmp_path):
    system, _ = pc
    journal = _forged_journal(tmp_path / "ailleurs", [])
    with pytest.raises(repair.UnsafeBackupError):
        repair.undo(journal, system, backup_root=tmp_path / "b")


def test_admin_backups_go_to_the_protected_folder(pc, tmp_path):
    system, _ = pc  # faux Windows lance en administrateur
    assert system.is_admin and system.is_windows
    entry = by_title(repair.diagnose(system, is_malware))["Programme au demarrage : Updater"]
    results, journal = repair.apply_fixes([entry], system)
    assert results[0].ok
    assert journal.parent == system.runner.programdata / "repair-backups"
    assert repair.list_backups(system=system) == [journal]
    assert all(ok for _, ok, _ in repair.undo(system=system))


def test_admin_repairs_stop_if_the_protected_folder_is_not_safe(pc):
    system, _ = pc
    system.runner = lambda args, timeout: subprocess.CompletedProcess(
        args, 3, "ERREUR proprietaire\n", "") if "CommonApplicationData" in args[-1] \
        else subprocess.CompletedProcess(args, 0, "", "")
    entry = by_title(repair.diagnose(system, is_malware))["Programme au demarrage : Updater"]
    with pytest.raises(repair.UnsafeBackupError):
        repair.apply_fixes([entry], system)
    assert system.registry.get("HKCU", RUN, "Updater") is not None  # rien n'a ete modifie


def _old(path, data=b"x"):
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (0, 0))
    return path


def _clean(temp):
    finding = checks.Finding(key="t", category="Nettoyage", title="t", detail="", severity=INFO,
                             action={"type": "clean_temp", "dir": str(temp)}, undoable=False)
    return repair.apply_fixes([finding], System(is_windows=False, is_admin=False),
                              backup_root=temp.parent / "b")


def test_temp_cleanup_never_follows_a_symlink_out_of_temp(tmp_path):
    temp = tmp_path / "Temp"
    precious = _old(tmp_path / "Documents" / "these.docx")
    junk = _old(temp / "vieux.tmp")
    try:
        (temp / "lien").symlink_to(precious.parent, target_is_directory=True)
        (temp / "fichier-lien.tmp").symlink_to(precious)
    except OSError:
        pytest.skip("liens symboliques non autorises sur ce systeme")
    assert checks.old_temp_files(temp) == [junk]
    results, _ = _clean(temp)
    assert results[0].ok and precious.exists() and not junk.exists()


@pytest.mark.skipif(not __import__("sys").platform.startswith("win"), reason="jonctions Windows")
def test_temp_cleanup_never_follows_a_windows_junction(tmp_path):
    temp = tmp_path / "Temp"
    precious = _old(tmp_path / "Documents" / "these.docx")
    junk = _old(temp / "vieux.tmp")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(temp / "jonction"), str(precious.parent)],
                   check=True, capture_output=True)
    assert (temp / "jonction" / "these.docx").exists()  # la jonction fonctionne bien
    naive = [p for p in temp.rglob("*") if p.name == "these.docx"]
    print(f"Path.rglob suit la jonction : {bool(naive)}")  # ancien comportement, pour le rapport
    assert checks.old_temp_files(temp) == [junk]
    results, _ = _clean(temp)
    assert results[0].ok and precious.exists() and not junk.exists()


def test_elevated_quarantine_restores_only_into_the_home_folder(tmp_path):
    import json
    from freeav.quarantine import Quarantine
    q = Quarantine(tmp_path / "q", elevated=True)
    sample = Path.home() / f".freeav-test-{tmp_path.name}.bin"
    sample.write_bytes(b"donnees")
    item = q.isolate(sample, "Test")
    meta = tmp_path / "q" / f"{item}.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["original_path"] = str(tmp_path.anchor + "freeav-hors-profil.dll")
    meta.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PermissionError):
        q.restore(item)
    data["original_path"] = str(sample)
    meta.write_text(json.dumps(data), encoding="utf-8")
    assert q.restore(item) == sample
    sample.unlink()


@pytest.mark.skipif(not __import__("sys").platform.startswith("win"), reason="vrai Windows")
def test_real_windows_protected_backup_folder():
    """Sur un vrai Windows en administrateur : dossier verrouille, et un dossier depose par
    quelqu'un d'autre (avec un faux journal) est mis de cote au lieu d'etre utilise."""
    system = System()
    if not system.is_admin:
        pytest.skip("necessite les droits administrateur")
    root = repair.admin_backup_root(system)
    folder = root.parent
    assert folder.is_dir()
    acl = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"([IO.DirectoryInfo]::new('{folder}')).GetAccessControl().GetAccessRules("
                          "$true, $true, [Security.Principal.SecurityIdentifier]) | "
                          "ForEach-Object { $_.IdentityReference.Value }"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert set(acl) <= {"S-1-5-32-544", "S-1-5-18"}, acl

    root.mkdir(exist_ok=True)
    (root / "20990101-000000-dead.json").write_text('{"steps": []}', encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"$d = [IO.DirectoryInfo]::new('{folder}'); $a = $d.GetAccessControl(); "
                    "$a.SetOwner([Security.Principal.WindowsIdentity]::GetCurrent().User); "
                    "$d.SetAccessControl($a)"], check=True)
    root2 = repair.admin_backup_root(system)
    assert root2 == root
    assert not (root / "20990101-000000-dead.json").exists()
    assert list(folder.parent.glob("FreeAV.non-sur-*"))
