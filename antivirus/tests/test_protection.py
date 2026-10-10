"""Protection en temps reel et protection automatique planifiee."""

import hashlib
import subprocess

import pytest

from freeav import schedule, watcher
from freeav.quarantine import Quarantine
from freeav.repair.platform import System
from freeav.scanner import Scanner
from freeav.signatures import SignatureDB
from test_repair import FakeRegistry

BAD = b"faux programme malveillant pour les tests"


@pytest.fixture(autouse=True)
def private_stop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, "STOP_FILE", tmp_path / "watch.stop")


@pytest.fixture
def scanner():
    db = SignatureDB()
    db.add(hashlib.sha256(BAD).hexdigest(), "Test.Malware")
    return Scanner(db)


def test_new_file_is_scanned_once_written_and_quarantined(tmp_path, scanner):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "ancien.exe").write_bytes(BAD)  # deja present : laisse a l'analyse complete
    quarantine = Quarantine(tmp_path / "quarantaine")
    seen = []
    watch = watcher.FolderWatcher(scanner, [downloads], quarantine, on_event=seen.append)

    (downloads / "facture.exe").write_bytes(BAD)
    (downloads / "photo.jpg").write_bytes(b"photo")
    assert watch.poll() == []  # premier passage : on attend que l'ecriture soit finie
    events = watch.poll()

    assert [(e.kind, e.path.name) for e in events] == [("quarantaine", "facture.exe")]
    assert seen == events
    assert not (downloads / "facture.exe").exists()
    assert (downloads / "ancien.exe").exists() and (downloads / "photo.jpg").exists()
    assert [i["threat"] for i in quarantine.list()] == ["Test.Malware"]
    assert watch.poll() == []


def test_file_still_growing_waits_and_partial_downloads_are_skipped(tmp_path, scanner):
    watch = watcher.FolderWatcher(scanner, [tmp_path])
    partial = tmp_path / "setup.exe.crdownload"
    partial.write_bytes(BAD)
    target = tmp_path / "gros.exe"
    target.write_bytes(BAD[:10])
    watch.poll()
    target.write_bytes(BAD)  # toujours en cours d'ecriture
    assert watch.poll() == []
    events = watch.poll()
    assert [(e.kind, e.path.name) for e in events] == [("menace", "gros.exe")]
    assert target.exists()  # sans quarantaine demandee, rien n'est deplace


def test_watch_command_needs_an_existing_folder(tmp_path, capsys):
    from freeav.cli import main
    assert main(["watch", str(tmp_path / "absent")]) == 2


class Runner:
    def __init__(self):
        self.calls, self.tasks = [], set()

    def __call__(self, args, timeout):
        self.calls.append(args)
        name = args[args.index("/tn") + 1]
        if "/create" in args:
            self.tasks.add(name)
        elif "/delete" in args:
            self.tasks.discard(name)
        code = 1 if "/query" in args and name not in self.tasks else 0
        return subprocess.CompletedProcess(args, code, "", "")


def windows(tmp_path):
    return System(registry=FakeRegistry(), runner=Runner(), is_windows=True, is_admin=False,
                  environ={"LOCALAPPDATA": str(tmp_path)}, home=tmp_path)


def test_schedule_install_status_and_remove(tmp_path):
    system = windows(tmp_path)
    program = [r"C:\Users\moi\AppData\Local\FreeAV\FreeAV.exe"]
    done = schedule.install(system, program, at="9:05")

    assert len(done) == 2
    create = system.runner.calls[0]
    assert create[:2] == ["schtasks", "/create"] and "09:05" in create
    assert create[-1] == r"C:\Users\moi\AppData\Local\FreeAV\FreeAV.exe auto --notify"
    run_value = system.registry.get("HKCU", schedule.RUN_KEY, "FreeAV")[0]
    assert run_value.endswith("FreeAV.exe watch --quarantine --notify")
    assert schedule.status(system) == {"analyse quotidienne": True, "protection en temps reel": True}

    assert len(schedule.remove(system)) == 2
    assert schedule.status(system) == {"analyse quotidienne": False, "protection en temps reel": False}
    assert schedule.remove(system) == []


def test_schedule_without_realtime_and_bad_input(tmp_path):
    system = windows(tmp_path)
    schedule.install(system, ["FreeAV.exe"], realtime=False)
    assert schedule.status(system)["protection en temps reel"] is False
    with pytest.raises(schedule.ScheduleError):
        schedule.install(system, ["FreeAV.exe"], at="25:00")
    with pytest.raises(schedule.ScheduleError):
        schedule.install(System(registry=FakeRegistry(), runner=Runner(), is_windows=False,
                                is_admin=False, environ={}, home=tmp_path), ["freeav"])


def test_program_path_with_spaces_is_quoted(tmp_path):
    system = windows(tmp_path)
    schedule.install(system, [r"C:\Users\Jean Dupont\AppData\Local\FreeAV\FreeAV.exe"])
    assert system.runner.calls[0][-1].startswith('"C:\\Users\\Jean Dupont')


def test_auto_scans_downloads_and_logs(tmp_path, monkeypatch):
    from freeav import cli, repair
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "x.exe").write_bytes(BAD)
    db = tmp_path / "base.txt"
    db.write_text(f"sha256:{hashlib.sha256(BAD).hexdigest()}:Test.Malware\n")
    monkeypatch.setattr(watcher, "default_folders", lambda home=None: [downloads])
    monkeypatch.setattr(cli, "LOG_FILE", tmp_path / "logs" / "auto.log")
    monkeypatch.setattr(cli.updater, "load_auth_key", lambda: "")
    monkeypatch.setattr(repair, "diagnose", lambda system, check: [])
    monkeypatch.setattr(repair, "System", lambda: None)

    code = cli.main(["--quarantine-dir", str(tmp_path / "q"), "auto", "--db", str(db)])

    assert code == 1
    assert not (downloads / "x.exe").exists()
    log = (tmp_path / "logs" / "auto.log").read_text(encoding="utf-8")
    assert "Test.Malware" in log and "mis en quarantaine" in log and "aucune cle" in log


def test_remove_stops_running_protection_and_deletes_the_copy(tmp_path, scanner):
    import threading
    import time
    system = windows(tmp_path)
    copy = schedule.install_dir(system) / "FreeAV.exe"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(b"MZ")
    schedule.install(system, [str(copy)])
    watch = watcher.FolderWatcher(scanner, [tmp_path / "vide"])
    thread = threading.Thread(target=watch.run, args=(threading.Event(), 0.05, schedule.STOP_FILE))
    thread.start()
    time.sleep(0.1)
    done = schedule.remove(system)
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert not copy.exists() and any("copie de FreeAV supprimee" in d for d in done)


def test_replaced_file_with_same_size_and_date_is_rescanned(tmp_path, scanner):
    import os
    clean = b"x" * len(BAD)
    target = tmp_path / "doc.exe"
    target.write_bytes(clean)
    os.utime(target, ns=(10**18, 10**18))
    watch = watcher.FolderWatcher(scanner, [tmp_path])
    other = tmp_path / "autre.tmp.download"  # nom ignore par la surveillance
    other.write_bytes(BAD)
    os.utime(other, ns=(10**18, 10**18))
    os.replace(other, target)
    watch.poll()
    assert [e.kind for e in watch.poll()] == ["menace"]
