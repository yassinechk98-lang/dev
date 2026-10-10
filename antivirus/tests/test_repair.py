"""Tests du module "Reparer mon PC", avec un faux Windows (registre et commandes simules)."""

import subprocess

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
