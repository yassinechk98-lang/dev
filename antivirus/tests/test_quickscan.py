"""Analyse rapide des endroits a risque."""

import hashlib
import subprocess

from freeav import cli, quickscan
from freeav.repair.platform import System
from test_repair import FakeRegistry


def windows(tmp_path):
    for d in ("home/Downloads", "home/Desktop", "Temp", "Public/Desktop",
              "Roaming/Microsoft/Windows/Start Menu/Programs/Startup", "Windows/Temp", "Programs"):
        (tmp_path / d).mkdir(parents=True)
    tool = tmp_path / "Programs" / "outil.exe"
    tool.write_bytes(b"MZ")
    reg = FakeRegistry()
    reg.set("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Outil", f'"{tool}" /fond', 1)
    reg.set("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Ancien",
            str(tmp_path / "disparu.exe"), 1)
    env = {"TEMP": str(tmp_path / "Temp"), "APPDATA": str(tmp_path / "Roaming"),
           "PUBLIC": str(tmp_path / "Public"), "SystemRoot": str(tmp_path / "Windows")}
    system = System(registry=reg, runner=lambda a, t: subprocess.CompletedProcess(a, 0, "", ""),
                    is_windows=True, is_admin=False, environ=env, home=tmp_path / "home")
    return system, tool


def test_quick_scan_covers_the_risky_places(tmp_path):
    system, tool = windows(tmp_path)
    targets = quickscan.quick_targets(system)
    assert targets == [tmp_path / "home/Downloads", tmp_path / "home/Desktop",
                       tmp_path / "Public/Desktop", tmp_path / "Temp",
                       tmp_path / "Roaming/Microsoft/Windows/Start Menu/Programs/Startup", tool]
    assert tmp_path / "Windows/Temp" not in targets  # dossier partage de Windows : pas ici


def test_cli_quick_scan_finds_a_threat_in_downloads(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "Downloads" / "facture.exe"
    bad.parent.mkdir()
    bad.write_bytes(b"faux malware telecharge")
    db = tmp_path / "base.txt"
    db.write_text(f"sha256:{hashlib.sha256(bad.read_bytes()).hexdigest()}:Test.Rapide\n")
    monkeypatch.setattr(quickscan, "quick_targets", lambda system=None: [bad.parent])
    assert cli.main(["scan", "--quick", "--db", str(db), "--no-clamav"]) == 1
    assert "Test.Rapide" in capsys.readouterr().out


def test_scan_needs_a_path_or_quick(capsys):
    assert cli.main(["scan", "--no-clamav"]) == 2
