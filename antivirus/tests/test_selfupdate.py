"""Mise a jour de FreeAV lui-meme."""

import hashlib
import json
import subprocess
import sys
import time

import pytest

from freeav import installer, schedule, selfupdate
from freeav.selfupdate import Release, SelfUpdateError
from test_engines import windows_system

WINDOWS = sys.platform.startswith("win")
EXE_URL = selfupdate.FREEAV_TEST_RELEASE + "freeav-test/FreeAV.exe"
NEW = b"MZ nouvelle version de FreeAV"


def manifest(**changes) -> bytes:
    data = {"build": 12, "sha256": hashlib.sha256(NEW).hexdigest(), "size": len(NEW),
            "url": EXE_URL, "commit": "abc"}
    data.update(changes)
    return json.dumps(data).encode()


def test_newer_version_is_offered_only_when_more_recent():
    seen = []

    def fetcher(url, limit):
        seen.append(url)
        return manifest()
    assert selfupdate.check(fetcher, {"build": 11, "canal": "freeav-test"}).build == 12
    assert seen == [selfupdate.FREEAV_TEST_RELEASE + "freeav-test/FreeAV.json"]
    assert selfupdate.check(fetcher, {"build": 12, "canal": "freeav-test"}) is None
    assert selfupdate.check(fetcher, {"build": 30, "canal": "freeav-test"}) is None  # pas de retour arriere


def test_source_copy_never_updates_itself():
    assert selfupdate.current_build() is None  # lance depuis le code source
    assert selfupdate.check(lambda url, limit: pytest.fail("aucun acces reseau")) is None


@pytest.mark.parametrize("bad", [
    {"url": "https://evil.example/FreeAV.exe"},
    {"url": selfupdate.FREEAV_TEST_RELEASE + "freeav-apercu/FreeAV.exe"},  # autre canal
    {"sha256": "1234"},
    {"size": 10 ** 9},
    {"build": "13"},
])
def test_invalid_manifest_is_refused(bad):
    with pytest.raises(SelfUpdateError):
        selfupdate.parse_manifest(manifest(**bad), "freeav-test")


def test_only_https_github_addresses_are_followed():
    selfupdate._check_url(EXE_URL)
    selfupdate._check_url("https://release-assets.githubusercontent.com/github-production/x")
    for url in ("http://github.com/x", "https://github.com.evil.example/x", "file:///C:/x.exe",
                "https://evil.example/FreeAV.exe"):
        with pytest.raises(SelfUpdateError):
            selfupdate._check_url(url)


def test_wrong_file_is_refused_and_nothing_is_replaced(tmp_path):
    exe = tmp_path / "FreeAV.exe"
    exe.write_bytes(b"MZ ancienne version")
    release = selfupdate.parse_manifest(manifest(), "freeav-test")
    with pytest.raises(SelfUpdateError, match="ne correspond pas"):
        selfupdate.download(release, tmp_path,
                            lambda url, limit, dest: dest.write_bytes(b"MZ version piegee"))
    assert exe.read_bytes() == b"MZ ancienne version"
    assert not (tmp_path / "FreeAV.new.exe").exists()
    not_a_program = Release(12, hashlib.sha256(b"hello").hexdigest(), 5, EXE_URL)
    with pytest.raises(SelfUpdateError):
        selfupdate.download(not_a_program, tmp_path, lambda url, limit, dest: dest.write_bytes(b"hello"))


def test_update_replaces_the_installed_copy_and_restarts_protection(tmp_path):
    system, _ = windows_system(tmp_path)
    source = tmp_path / "FreeAV.exe"
    source.write_bytes(b"MZ ancienne version")
    installer.install(system, source)
    exe = installer.target_exe(system)
    system.registry.set("HKCU", schedule.RUN_KEY, schedule.RUN_VALUE,
                        subprocess.list2cmdline([str(exe)] + schedule.WATCH_ARGS), 1)
    launched = []
    release = selfupdate.parse_manifest(manifest(), "freeav-test")
    done = selfupdate.apply(release, system, fetcher=lambda url, limit, dest: dest.write_bytes(NEW),
                            launcher=launched.append, running=source)
    assert exe.read_bytes() == NEW
    assert (exe.parent / "FreeAV.old.exe").read_bytes() == b"MZ ancienne version"
    assert launched == [[str(exe)] + schedule.WATCH_ARGS]
    assert "build 12" in system.registry.get("HKCU", installer.UNINSTALL_KEY, "DisplayVersion")[0]
    assert len(done) == 2
    selfupdate.cleanup_old(exe)
    assert sorted(p.name for p in exe.parent.iterdir()) == ["FreeAV.exe"]


def test_failed_replacement_puts_the_old_version_back(tmp_path, monkeypatch):
    exe = tmp_path / "FreeAV.exe"
    exe.write_bytes(b"MZ ancienne")
    new = tmp_path / "FreeAV.new.exe"
    new.write_bytes(NEW)
    real_replace = selfupdate.os.replace

    def flaky(src, dst):
        if src == new:
            raise PermissionError("bloque")
        real_replace(src, dst)
    monkeypatch.setattr(selfupdate.os, "replace", flaky)
    with pytest.raises(SelfUpdateError, match="ancienne version gardee"):
        selfupdate.replace(exe, new)
    assert exe.read_bytes() == b"MZ ancienne"


@pytest.mark.skipif(not WINDOWS, reason="vrai Windows")
def test_running_program_can_be_replaced_on_windows(tmp_path):
    exe = tmp_path / "FreeAV.exe"
    exe.write_bytes(open(r"C:\Windows\System32\cmd.exe", "rb").read())
    proc = subprocess.Popen([str(exe), "/c", "ping -n 20 127.0.0.1 >nul"])
    try:
        time.sleep(1)
        new = tmp_path / "FreeAV.new.exe"
        new.write_bytes(NEW)
        old = selfupdate.replace(exe, new)
        assert exe.read_bytes() == NEW and old.exists()
        selfupdate.cleanup_old(exe)  # encore utilise : garde sans erreur
    finally:
        proc.kill()
        proc.wait()
