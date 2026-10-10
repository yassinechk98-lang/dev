import hashlib
import json
import os
import stat
import socket
import struct
import threading

import pytest

from freeav.clamav import ClamdClient
from freeav.cli import main
from freeav.quarantine import Quarantine
from freeav.scanner import Scanner
from freeav.signatures import SignatureDB, load_default

# Fichier de test EICAR, assemble a l'execution pour que ce fichier source
# ne soit pas lui-meme signale par un antivirus.
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()


@pytest.fixture
def sample_dir(tmp_path):
    (tmp_path / "sain.txt").write_text("bonjour")
    sub = tmp_path / "sous-dossier"
    sub.mkdir()
    (sub / "eicar.com").write_bytes(EICAR)
    return tmp_path


def test_default_db_matches_eicar_hashes():
    db = load_default()
    assert db.lookup(hashlib.sha256(EICAR).hexdigest(), "") == "EICAR-Test-File"
    assert db.lookup("", hashlib.md5(EICAR).hexdigest()) == "EICAR-Test-File"


def test_scanner_detects_eicar_and_ignores_clean_files(sample_dir):
    report = Scanner(load_default()).scan([sample_dir])
    assert report.scanned == 2
    assert [d.path.name for d in report.detections] == ["eicar.com"]
    assert report.detections[0].engine == "signatures"


def test_loads_clamav_hdb_format(tmp_path):
    content = b"faux malware"
    hdb = tmp_path / "custom.hdb"
    hdb.write_text(f"{hashlib.md5(content).hexdigest()}:{len(content)}:Test.Custom\n")
    db = SignatureDB()
    assert db.load_file(hdb) == 1
    (tmp_path / "x.bin").write_bytes(content)
    report = Scanner(db).scan([tmp_path / "x.bin"])
    assert report.detections[0].threat == "Test.Custom"


def test_quarantine_isolate_and_restore(sample_dir, tmp_path_factory):
    q = Quarantine(tmp_path_factory.mktemp("quarantaine"))
    infected = sample_dir / "sous-dossier" / "eicar.com"
    item_id = q.isolate(infected, "EICAR-Test-File")
    assert not infected.exists()
    assert EICAR not in (q.directory / f"{item_id}.bin").read_bytes()
    assert q.list()[0]["threat"] == "EICAR-Test-File"
    assert q.restore(item_id).read_bytes() == EICAR
    assert q.list() == []


def test_cli_exit_code_and_quarantine(sample_dir, tmp_path_factory, capsys):
    qdir = tmp_path_factory.mktemp("q")
    assert main(["--quarantine-dir", str(qdir), "scan", str(sample_dir), "--quarantine"]) == 1
    assert "EICAR-Test-File" in capsys.readouterr().out
    assert main(["--quarantine-dir", str(qdir), "scan", str(sample_dir)]) == 0


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        assert chunk, "connexion fermee trop tot"
        data += chunk
    return data


def _fake_clamd(server: socket.socket, verdict: bytes):
    conn, _ = server.accept()
    with conn:
        assert _recv_exact(conn, 10) == b"zINSTREAM\0"
        while size := struct.unpack("!L", _recv_exact(conn, 4))[0]:
            _recv_exact(conn, size)
        conn.sendall(verdict)


def test_clamd_client_parses_found_reply(tmp_path):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    thread = threading.Thread(target=_fake_clamd,
                              args=(server, b"stream: Win.Test.Fake FOUND\0"))
    thread.start()
    f = tmp_path / "f.bin"
    f.write_bytes(b"x" * 100_000)
    client = ClamdClient(port=server.getsockname()[1])
    assert client.scan_file(f) == "Win.Test.Fake"
    thread.join()
    server.close()


def test_cli_rejects_missing_path(tmp_path, capsys):
    assert main(["--quarantine-dir", str(tmp_path), "scan", str(tmp_path / "absent")]) == 2
    assert "introuvable" in capsys.readouterr().err


def test_cli_rejects_unknown_quarantine_id(tmp_path, capsys):
    assert main(["--quarantine-dir", str(tmp_path), "quarantine", "--restore", "abc"]) == 2
    assert main(["--quarantine-dir", str(tmp_path), "quarantine", "--delete", "../x"]) == 2


def test_restore_does_not_overwrite_existing_file(sample_dir, tmp_path_factory):
    q = Quarantine(tmp_path_factory.mktemp("q"))
    infected = sample_dir / "sous-dossier" / "eicar.com"
    item_id = q.isolate(infected, "EICAR-Test-File")
    infected.write_text("nouveau fichier")
    with pytest.raises(FileExistsError):
        q.restore(item_id)
    assert infected.read_text() == "nouveau fichier"
    assert q.exists(item_id)


# --- Sources open source : YARA et MalwareBazaar ---------------------------------

from freeav import updater, yara_engine  # noqa: E402
from freeav.clamav import ClamdError  # noqa: E402

requires_yara = pytest.mark.skipif(not yara_engine.available(),
                                   reason="yara-python non installe")


@requires_yara
def test_yara_rules_detect_and_bad_rules_are_isolated(tmp_path):
    rules = tmp_path / "regles"
    rules.mkdir()
    (rules / "bon.yar").write_text(
        'rule Faux_Rancongiciel { strings: $a = "VOS FICHIERS SONT CHIFFRES" condition: $a }')
    (rules / "casse.yar").write_text("rule { ceci n'est pas du yara")
    engine = yara_engine.YaraEngine([rules])
    assert len(engine) == 1 and len(engine.rejected) == 1
    (tmp_path / "note.txt").write_text("Bonjour, VOS FICHIERS SONT CHIFFRES, payez.")
    (tmp_path / "sain.txt").write_text("rien a signaler")
    report = Scanner(SignatureDB(), yara=engine).scan([tmp_path / "note.txt", tmp_path / "sain.txt"])
    assert [(d.threat, d.engine) for d in report.detections] == [
        ("YARA.Faux_Rancongiciel", "yara")]


FEED = ("# MalwareBazaar recent malware samples (SHA256 hashes)\n"
        "#\n" + hashlib.sha256(b"malware-a").hexdigest() + "\n"
        + hashlib.sha256(b"malware-b").hexdigest() + "\n").encode()


def test_update_writes_private_signature_file_used_by_scanner(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "download", lambda url: FEED)
    sig_dir = tmp_path / "signatures"
    path, count = updater.update_malwarebazaar(directory=sig_dir)
    assert count == 2
    if os.name == "posix":
        assert stat.S_IMODE(sig_dir.stat().st_mode) == 0o700
    (tmp_path / "x.exe").write_bytes(b"malware-b")
    report = Scanner(load_default(downloaded_dir=sig_dir)).scan([tmp_path / "x.exe"])
    assert report.detections[0].threat == "MalwareBazaar.Malware"


@pytest.mark.parametrize("feed", [
    b"<html>page piegee</html>\n",
    b"# vide\n",
    FEED + b"sha256:abc:Injection\n",
    "é".encode(),
])
def test_update_rejects_tampered_feed_and_keeps_old_db(tmp_path, monkeypatch, feed):
    sig_dir = tmp_path / "signatures"
    monkeypatch.setattr(updater, "download", lambda url: FEED)
    updater.update_malwarebazaar(directory=sig_dir)
    before = (sig_dir / "malwarebazaar.txt").read_text()
    monkeypatch.setattr(updater, "download", lambda url: feed)
    with pytest.raises(updater.UpdateError):
        updater.update_malwarebazaar(directory=sig_dir)
    assert (sig_dir / "malwarebazaar.txt").read_text() == before
    assert [p.name for p in sig_dir.iterdir()] == ["malwarebazaar.txt"]


def test_update_refuses_plain_http():
    with pytest.raises(updater.UpdateError):
        updater.download("http://bazaar.abuse.ch/export/txt/sha256/recent/")


# --- Vie privee et protection des donnees ------------------------------------------

def test_scan_never_uses_the_network(sample_dir, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("FreeAV a tente une connexion reseau pendant l'analyse")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    report = Scanner(load_default()).scan([sample_dir])
    assert len(report.detections) == 1


def test_clamd_on_another_machine_is_refused_by_default():
    with pytest.raises(ClamdError):
        ClamdClient(host="203.0.113.5")
    ClamdClient(host="203.0.113.5", allow_remote=True)
    ClamdClient(host="::1")


@pytest.mark.skipif(os.name != "posix", reason="droits Unix")
def test_quarantine_files_are_private(sample_dir, tmp_path_factory):
    q = Quarantine(tmp_path_factory.mktemp("q") / "quarantaine")
    item_id = q.isolate(sample_dir / "sous-dossier" / "eicar.com", "EICAR-Test-File")
    assert stat.S_IMODE(q.directory.stat().st_mode) == 0o700
    for suffix in (".bin", ".json"):
        assert stat.S_IMODE((q.directory / f"{item_id}{suffix}").stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="liens symboliques Unix")
def test_quarantine_refuses_symlink_to_personal_file(tmp_path):
    personal = tmp_path / "photos_perso.jpg"
    personal.write_bytes(b"photo")
    link = tmp_path / "piege.com"
    link.symlink_to(personal)
    q = Quarantine(tmp_path / "q")
    with pytest.raises(OSError):
        q.isolate(link, "Faux")
    assert personal.read_bytes() == b"photo"


def test_tampered_quarantine_record_cannot_write_elsewhere(sample_dir, tmp_path_factory):
    q = Quarantine(tmp_path_factory.mktemp("q"))
    item_id = q.isolate(sample_dir / "sous-dossier" / "eicar.com", "EICAR-Test-File")
    victim = sample_dir / "sain.txt"
    meta_file = q.directory / f"{item_id}.json"
    meta = json.loads(meta_file.read_text())
    meta["original_path"] = str(victim)  # tente d'ecraser un fichier existant
    meta_file.write_text(json.dumps(meta))
    with pytest.raises(FileExistsError):
        q.restore(item_id)
    assert victim.read_text() == "bonjour"
    meta["original_path"] = "relatif/vers/ailleurs"
    meta_file.write_text(json.dumps(meta))
    with pytest.raises(OSError):
        q.restore(item_id)
