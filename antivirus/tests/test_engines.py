"""Moteurs complets (Microsoft Defender, ClamAV integre), installation Windows et cles USB."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from freeav import clamav_local, installer, schedule, watcher
from freeav.clamav_local import ClamavError, ClamscanEngine, LocalClamav
from freeav.defender import DefenderEngine, DefenderError, find_mpcmdrun, parse_report
from freeav.quarantine import Quarantine
from freeav.repair.platform import System
from freeav.scanner import Scanner
from freeav.signatures import SignatureDB
from test_repair import FakeRegistry

EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()
WINDOWS = sys.platform.startswith("win")

DEFENDER_OUTPUT = """Scan starting...
Scan finished.
Scanning {dir} found 1 threats.

<===========================LIST OF DETECTED THREATS==========================>
----------------------------- Threat information ------------------------------
Threat                  : Trojan:Win32/Wacatac.B!ml
Resources               : 1 total
    file                : {file}
-------------------------------------------------------------------------------
"""


@pytest.fixture(autouse=True)
def private_stop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, "STOP_FILE", tmp_path / "watch.stop")


def fake_defender(tmp_path, bad: Path):
    calls = []

    def runner(args, timeout):
        calls.append(args)
        target = Path(args[args.index("-File") + 1])
        if target == bad or target in bad.parents:
            return subprocess.CompletedProcess(args, 2, DEFENDER_OUTPUT.format(dir=target, file=bad), "")
        return subprocess.CompletedProcess(args, 0, "Scan starting...\nScan finished.\n", "")
    exe = tmp_path / "MpCmdRun.exe"
    exe.write_bytes(b"MZ")
    return DefenderEngine(exe=exe, runner=runner), calls


def test_parse_defender_report(tmp_path):
    out = DEFENDER_OUTPUT.format(dir="C:\\x", file="C:\\x\\a.exe->(UPX)")
    assert parse_report(out) == {Path("C:\\x\\a.exe"): "Trojan:Win32/Wacatac.B!ml"}


def test_defender_second_opinion_in_a_folder_scan(tmp_path):
    folder = tmp_path / "Telechargements"
    folder.mkdir()
    bad = folder / "outil.exe"
    bad.write_bytes(b"inconnu de FreeAV")
    (folder / "photo.jpg").write_bytes(b"ok")
    engine, calls = fake_defender(tmp_path, bad)
    report = Scanner(SignatureDB(), batch_engines=[engine]).scan([folder])
    assert [(d.path, d.threat, d.engine) for d in report.detections] == \
        [(bad, "Trojan:Win32/Wacatac.B!ml", "defender")]
    assert not report.detections[0].suspect  # menace confirmee : quarantaine possible
    assert len(calls) == 1 and "-DisableRemediation" in calls[0]  # un seul appel par dossier


def test_defender_failure_is_reported_not_fatal(tmp_path):
    exe = tmp_path / "MpCmdRun.exe"
    exe.write_bytes(b"MZ")
    engine = DefenderEngine(exe=exe, runner=lambda a, t: subprocess.CompletedProcess(a, 5, "panne", ""))
    (tmp_path / "f.txt").write_text("x")
    report = Scanner(SignatureDB(), batch_engines=[engine]).scan([tmp_path])
    assert report.detections == [] and "defender" in report.errors[0][1]


def test_defender_not_found_raises(tmp_path, monkeypatch):
    assert find_mpcmdrun({"ProgramData": str(tmp_path), "ProgramFiles": str(tmp_path)}) is None
    monkeypatch.setattr("freeav.defender.find_mpcmdrun", lambda environ=None: None)
    with pytest.raises(DefenderError):
        DefenderEngine()


def make_package(tmp_path, extra=None):
    package = tmp_path / "clamav.zip"
    with zipfile.ZipFile(package, "w") as z:
        z.writestr("clamav-1.4.3.win.x64/clamscan.exe", b"MZ")
        z.writestr("clamav-1.4.3.win.x64/freshclam.exe", b"MZ")
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return package


def fake_clamav_runner(found_line=""):
    calls = []

    def runner(args, timeout):
        calls.append(args)
        if "freshclam" in Path(args[0]).name:
            db = Path(args[1].split("=", 1)[1]).parent / "database"
            (db / "daily.cvd").write_bytes(b"cvd")
            return subprocess.CompletedProcess(args, 0, "daily.cvd updated", "")
        listing = Path(next(a for a in args if a.startswith("--file-list=")).split("=", 1)[1])
        files = listing.read_text(encoding="utf-8").split()
        out = "".join(f"{f}: {found_line} FOUND\n" for f in files if found_line and f.endswith(".exe"))
        return subprocess.CompletedProcess(args, 1 if out else 0, out, "")
    return runner, calls


def test_clamav_install_verifies_hash_then_scans(tmp_path, monkeypatch):
    package = make_package(tmp_path)
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    runner, calls = fake_clamav_runner("Win.Trojan.Agent-1")
    local = LocalClamav(tmp_path / "ClamAV", runner=runner)
    monkeypatch.setattr(clamav_local, "_download",
                        lambda url, dest, sha: (dest.write_bytes(package.read_bytes()),
                                                clamav_local._check_hash(dest, sha)))
    with pytest.raises(ClamavError):
        local.install({"url": "https://x", "sha256": "0" * 64})
    assert not local.installed()
    local.install({"url": "https://x", "sha256": digest})
    assert local.ready()
    assert "DatabaseMirror database.clamav.net" in (local.root / "freshclam.conf").read_text()

    folder = tmp_path / "dossier"
    folder.mkdir()
    (folder / "jeu.exe").write_bytes(b"inconnu")
    (folder / "texte.txt").write_bytes(b"ok")
    report = Scanner(SignatureDB(), batch_engines=[ClamscanEngine(local)]).scan([folder])
    assert [(d.path.name, d.threat, d.engine) for d in report.detections] == \
        [("jeu.exe", "Win.Trojan.Agent-1", "clamav")]


def test_clamav_package_with_path_traversal_is_refused(tmp_path):
    package = make_package(tmp_path, {"../../evil.dll": b"x"})
    local = LocalClamav(tmp_path / "ClamAV", runner=fake_clamav_runner()[0])
    with pytest.raises(ClamavError):
        local.install(package=package)
    assert not (tmp_path / "evil.dll").exists()


def test_manifest_only_accepts_freeav_release_urls(tmp_path, monkeypatch):
    m = tmp_path / "clamav.json"
    monkeypatch.setattr(clamav_local, "MANIFEST", m)
    m.write_text(json.dumps({"url": "https://evil.example/clamav.zip", "sha256": "a" * 64}))
    assert clamav_local.manifest() is None
    m.write_text(json.dumps({"url": clamav_local.FREEAV_TEST_RELEASE + "freeav-test/FreeAV-ClamAV.zip",
                             "sha256": "a" * 64}))
    assert clamav_local.manifest()["sha256"] == "a" * 64


def test_usb_drive_is_scanned_when_plugged_in(tmp_path):
    usb = tmp_path / "E"
    usb.mkdir()
    bad = b"faux malware sur cle usb"
    (usb / "autorun.exe").write_bytes(bad)
    db = SignatureDB()
    db.add(hashlib.sha256(bad).hexdigest(), "Test.USB")
    drives = set()
    seen = []
    watch = watcher.FolderWatcher(Scanner(db), [], Quarantine(tmp_path / "q"),
                                  on_event=seen.append, removable_drives=lambda: drives)
    assert watch.poll() == []
    drives.add(str(usb))  # la cle est branchee
    assert watch.poll() == []  # analysee en arriere-plan : la surveillance continue
    watch.wait_drives(30)
    assert [e.kind for e in seen] == ["quarantaine", "usb"]
    assert not (usb / "autorun.exe").exists()
    watch.poll()
    watch.wait_drives(30)
    assert len(seen) == 2  # deja analysee tant qu'elle reste branchee


def windows_system(tmp_path):
    calls = []

    def runner(args, timeout):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0 if "/query" not in args else 1, "OK\n", "")
    system = System(registry=FakeRegistry(), runner=runner, is_windows=True, is_admin=False,
                    environ={"LOCALAPPDATA": str(tmp_path / "Local")}, home=tmp_path)
    return system, calls


def test_install_and_uninstall_for_the_current_user(tmp_path, monkeypatch):
    system, calls = windows_system(tmp_path)
    source = tmp_path / "Telechargements" / "FreeAV.exe"
    source.parent.mkdir()
    source.write_bytes(b"MZ" * 1000)
    done = installer.install(system, source)
    exe = installer.target_exe(system)
    assert exe.read_bytes() == source.read_bytes() and len(done) == 4
    reg = system.registry
    assert installer.is_installed(system)
    assert reg.get("HKCU", installer.UNINSTALL_KEY, "UninstallString")[0] == f"{exe} uninstall"
    for key in installer.MENU_KEYS:
        assert reg.get("HKCU", key, "")[0] == "Analyser avec FreeAV"
        assert reg.get("HKCU", key + r"\command", "")[0] == f'{exe} gui --scan "%1"'
    assert any("WScript.Shell" in c[-1] for c in calls)  # raccourcis

    # Retirer la protection automatique ne supprime pas FreeAV installe
    schedule.remove(system)
    assert exe.exists()

    done = installer.uninstall(system)
    assert not installer.is_installed(system) and not exe.exists()
    assert all(reg.get("HKCU", k, "") is None for k in installer.MENU_KEYS)
    assert any("donnees" in d for d in done)


@pytest.mark.skipif(not WINDOWS, reason="vrai Windows")
def test_real_defender_detects_eicar(tmp_path):
    exe = find_mpcmdrun()
    if not exe:
        pytest.skip("Microsoft Defender absent")
    sample = tmp_path / "eicar.com"
    try:
        sample.write_bytes(EICAR)
    except OSError:
        pytest.skip("le fichier de test a ete bloque des l'ecriture")
    result = subprocess.run([str(exe), "-Scan", "-ScanType", "3", "-File", str(sample),
                             "-DisableRemediation"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    print(result.returncode, result.stdout[-2000:])  # pour le journal de la CI
    if result.returncode not in (0, 2) or not sample.exists():
        pytest.skip(f"Defender indisponible sur ce serveur (code {result.returncode})")
    found = DefenderEngine(exe).scan_paths([tmp_path])
    assert any(p.name == "eicar.com" and "EICAR" in t.upper() for p, t in found.items()), found


@pytest.mark.skipif(not (WINDOWS and os.environ.get("FREEAV_CLAMAV_ZIP")),
                    reason="paquet ClamAV officiel fourni par la CI Windows")
def test_real_clamav_install_update_and_scan(tmp_path):
    local = LocalClamav(tmp_path / "ClamAV")
    local.install(package=Path(os.environ["FREEAV_CLAMAV_ZIP"]), progress=print)
    assert local.ready()
    sample = tmp_path / "echantillon" / "eicar.com"
    sample.parent.mkdir()
    sample.write_bytes(EICAR)
    if not sample.exists():
        pytest.skip("le fichier de test a ete supprime par l'antivirus du serveur")
    found = local.scan_paths([sample, tmp_path / "echantillon"])
    assert any("Eicar" in t for p, t in found.items()), found


def test_uninstall_of_the_running_installed_copy_deletes_it_afterwards(tmp_path, monkeypatch):
    system, calls = windows_system(tmp_path)
    source = tmp_path / "FreeAV.exe"
    source.write_bytes(b"MZ" * 10)
    installer.install(system, source)
    exe = installer.target_exe(system)
    monkeypatch.setattr(installer, "running_installed_copy", lambda system: True)
    spawned = []
    done = installer.uninstall(system, spawn=spawned.append)
    assert spawned == [exe]  # le chemin passe par l'environnement, pas par une ligne de cmd
    assert "FREEAV_EXE" in installer.SELF_DELETE_SCRIPT and "-LiteralPath" in installer.SELF_DELETE_SCRIPT
    assert any("quelques secondes" in d for d in done)


def test_right_click_on_a_drive_keeps_the_drive_path():
    from freeav.cli import scan_argument
    assert scan_argument('E:"') == "E:\\"
    assert scan_argument(r"C:\Users\moi\fichier.exe") == r"C:\Users\moi\fichier.exe"
    assert scan_argument(None) is None


@pytest.mark.skipif(not WINDOWS, reason="decoupage reel de la ligne de commande Windows")
def test_registered_drive_command_is_split_back_to_the_drive(tmp_path):
    import ctypes
    from ctypes import wintypes
    from freeav.cli import scan_argument
    system, _ = windows_system(tmp_path)
    source = tmp_path / "FreeAV.exe"
    source.write_bytes(b"MZ")
    installer.install(system, source)
    command = system.registry.get("HKCU", r"Software\Classes\Drive\shell\FreeAV\command", "")[0]
    line = command.replace("%1", "E:\\")
    split = ctypes.windll.shell32.CommandLineToArgvW
    split.restype = ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    argv = split(line, ctypes.byref(count))
    args = [argv[i] for i in range(count.value)]
    assert args[1:3] == ["gui", "--scan"]
    assert scan_argument(args[3]) == "E:\\"


def test_integrated_clamav_is_not_run_as_administrator(tmp_path, monkeypatch):
    monkeypatch.setattr("freeav.quarantine._is_elevated", lambda: True)
    local = LocalClamav(tmp_path / "ClamAV")
    with pytest.raises(ClamavError, match="administrateur"):
        local.scan_paths([tmp_path])
    with pytest.raises(ClamavError, match="administrateur"):
        local.update()
    from freeav.cli import batch_engines
    assert batch_engines(clamav=True) == []
