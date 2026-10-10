import hashlib
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
