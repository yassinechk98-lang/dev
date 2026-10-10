import hashlib
import json
import os
import pathlib
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


KEY = "cle-de-test-123"


def _csv_row(content: bytes, family: str) -> str:
    return (f'"2026-10-10 10:00:00", "{hashlib.sha256(content).hexdigest()}", '
            f'"{hashlib.md5(content).hexdigest()}", "x", "abuse_ch", "f.exe", "exe", '
            f'"application/x-dosexec", "{family}", "n/a", "n/a", "n/a", "n/a", "n/a"\n')


# Format de l'export CSV de MalwareBazaar (en-tete dans un commentaire).
FEED = ("################################################################\n"
        "# MalwareBazaar recent malware samples (CSV)                   #\n"
        '# "first_seen_utc","sha256_hash","md5_hash","sha1_hash","reporter","file_name",'
        '"file_type_guess","mime_type","signature","clamav","vtpercent","imphash","ssdeep","tlsh"\n'
        + _csv_row(b"malware-a", "AgentTesla") + _csv_row(b"malware-b", "n/a")).encode()


def test_update_writes_private_signature_file_used_by_scanner(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "download", lambda url, key="": FEED)
    sig_dir = tmp_path / "signatures"
    path, added, total = updater.update_malwarebazaar(directory=sig_dir, auth_key=KEY)
    assert (added, total) == (2, 2)
    if os.name == "posix":
        assert stat.S_IMODE(sig_dir.stat().st_mode) == 0o700
    (tmp_path / "x.exe").write_bytes(b"malware-b")
    report = Scanner(load_default(downloaded_dir=sig_dir)).scan([tmp_path / "x.exe"])
    assert report.detections[0].threat == "MalwareBazaar.Malware"
    (tmp_path / "y.exe").write_bytes(b"malware-a")
    report = Scanner(load_default(downloaded_dir=sig_dir)).scan([tmp_path / "y.exe"])
    assert report.detections[0].threat == "MalwareBazaar.AgentTesla"


@pytest.mark.parametrize("feed", [
    b"<html>page piegee</html>\n",
    b"# vide\n",
    FEED + b'"2026-10-10", "pas-une-empreinte", "x"\n',
    "é".encode(),
    b"\xff\xfe",
])
def test_update_rejects_tampered_feed_and_keeps_old_db(tmp_path, monkeypatch, feed):
    sig_dir = tmp_path / "signatures"
    monkeypatch.setattr(updater, "download", lambda url, key="": FEED)
    updater.update_malwarebazaar(directory=sig_dir, auth_key=KEY)
    before = (sig_dir / "malwarebazaar.txt").read_text()
    monkeypatch.setattr(updater, "download", lambda url, key="": feed)
    with pytest.raises(updater.UpdateError):
        updater.update_malwarebazaar(directory=sig_dir, auth_key=KEY)
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


# --- Corrections issues de la validation independante --------------------------------

import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

from freeav import cli  # noqa: E402
from freeav.scanner import iter_files  # noqa: E402
from freeav.yara_engine import YaraScanError  # noqa: E402


class _FakeYara:
    """Moteur YARA factice : signale tout fichier contenant 'motif-suspect'."""

    def __init__(self, error_on: str = ""):
        self.error_on = error_on

    def __len__(self):
        return 1

    def match(self, path):
        if self.error_on and self.error_on in str(path):
            raise YaraScanError("YARA : delai depasse")
        return "YARA.Motif" if b"motif-suspect" in path.read_bytes() else None


def test_yara_suspects_are_never_quarantined_automatically(sample_dir, tmp_path_factory,
                                                           monkeypatch, capsys):
    (sample_dir / "outil.ps1").write_text("motif-suspect")
    monkeypatch.setattr(cli, "build_yara", lambda extra: _FakeYara())
    qdir = tmp_path_factory.mktemp("q")
    assert main(["--quarantine-dir", str(qdir), "scan", str(sample_dir), "--quarantine"]) == 1
    out = capsys.readouterr().out
    assert "SUSPECT" in out and "pas de quarantaine automatique" in out
    assert (sample_dir / "outil.ps1").exists()
    assert not (sample_dir / "sous-dossier" / "eicar.com").exists()  # vraie menace isolee


def test_clean_files_are_not_flagged():
    """Lot de fichiers sains : le code source de FreeAV lui-meme (Python, Markdown, YAML)."""
    root = pathlib.Path(__file__).resolve().parents[1]
    report = Scanner(load_default()).scan([root], exclude={root / "tests"})
    assert report.scanned > 10
    assert report.detections == []


def test_freeav_own_data_is_excluded_from_scan(tmp_path, monkeypatch):
    app = tmp_path / ".freeav"
    yara_dir = app / "yara"
    yara_dir.mkdir(parents=True)
    (yara_dir / "regle.yar").write_text('rule R { strings: $a = "motif-suspect" condition: $a }')
    (tmp_path / "doc.txt").write_text("sain")
    monkeypatch.setattr(cli, "APP_DIR", app)
    monkeypatch.setattr(cli, "YARA_DIR", yara_dir)
    exclude = cli.scan_exclusions(app / "quarantine", [])
    files = [p.name for p in iter_files(tmp_path, exclude)]
    assert files == ["doc.txt"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="tubes nommes Unix")
def test_named_pipe_does_not_block_the_scan(sample_dir):
    os.mkfifo(sample_dir / "piege.fifo")
    result = {}
    thread = threading.Thread(
        target=lambda: result.setdefault("r", Scanner(load_default()).scan([sample_dir])),
        daemon=True)
    thread.start()
    thread.join(timeout=10)
    assert not thread.is_alive(), "l'analyse est bloquee par un tube nomme"
    assert [d.path.name for d in result["r"].detections] == ["eicar.com"]
    report = Scanner(load_default()).scan([sample_dir / "piege.fifo"])
    assert report.scanned == 0


def test_yara_error_on_one_file_does_not_stop_the_scan(sample_dir):
    (sample_dir / "lent.bin").write_bytes(b"x")
    report = Scanner(load_default(), yara=_FakeYara(error_on="lent.bin")).scan([sample_dir])
    assert [d.path.name for d in report.detections] == ["eicar.com"]
    assert [p.name for p, _ in report.errors] == ["lent.bin"]


def test_failed_quarantine_leaves_no_fake_entry_and_continues(sample_dir, tmp_path_factory,
                                                              monkeypatch, capsys):
    second = sample_dir / "eicar2.com"
    second.write_bytes(EICAR)
    locked = sample_dir / "sous-dossier" / "eicar.com"
    real_unlink = pathlib.Path.unlink

    def unlink(self, *args, **kwargs):
        if self == locked.resolve():
            raise PermissionError("fichier verrouille")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "unlink", unlink)
    qdir = tmp_path_factory.mktemp("q")
    assert main(["--quarantine-dir", str(qdir), "scan", str(sample_dir), "--quarantine"]) == 1
    assert "quarantaine impossible" in capsys.readouterr().out
    assert locked.exists() and not second.exists()
    items = Quarantine(qdir).list()
    assert [pathlib.Path(i["original_path"]).name for i in items] == ["eicar2.com"]
    assert len(list(qdir.iterdir())) == 2  # un seul .bin + .json


def test_quarantine_refuses_file_changed_since_scan(sample_dir, tmp_path_factory):
    q = Quarantine(tmp_path_factory.mktemp("q"))
    target = sample_dir / "sain.txt"
    with pytest.raises(OSError):
        q.isolate(target, "EICAR-Test-File", hashlib.sha256(EICAR).hexdigest())
    assert target.exists() and q.list() == []


@pytest.mark.skipif(os.name != "posix", reason="droits Unix")
def test_restore_keeps_original_permissions(tmp_path):
    script = tmp_path / "script.sh"
    script.write_bytes(EICAR)
    script.chmod(0o755)
    q = Quarantine(tmp_path / "q")
    restored = q.restore(q.isolate(script, "EICAR-Test-File"))
    assert stat.S_IMODE(restored.stat().st_mode) == 0o755


def test_update_refuses_redirect_to_plain_http():
    handler = updater._HttpsOnlyRedirects()
    req = urllib.request.Request("https://bazaar.abuse.ch/export/txt/sha256/recent/")
    with pytest.raises(updater.UpdateError):
        handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example/feed")
    assert handler.redirect_request(req, None, 302, "Found", {},
                                    "https://bazaar.abuse.ch/autre/") is not None


class _FakeOpener:
    def __init__(self, status=200):
        self.status, self.request = status, None

    def open(self, request, timeout):
        self.request = request
        if self.status != 200:
            raise urllib.error.HTTPError(request.full_url, self.status, "Forbidden", {}, None)
        import io
        return io.BytesIO(FEED)


def test_update_sends_auth_key_and_explains_missing_key(monkeypatch):
    opener = _FakeOpener()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: opener)
    monkeypatch.delenv(updater.AUTH_KEY_ENV, raising=False)
    _path, added, _total = updater.update_malwarebazaar(directory=_tmp_sig_dir(), auth_key=KEY)
    # Adresse documentee par abuse.ch : la cle dans le chemin de l'export v2.
    assert opener.request.full_url == f"https://mb-api.abuse.ch/v2/files/exports/{KEY}/recent.csv"
    assert added == 2
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _FakeOpener(401))
    with pytest.raises(updater.UpdateError, match="Auth-Key") as err:
        updater.update_malwarebazaar(directory=_tmp_sig_dir(), auth_key=KEY)
    assert KEY not in str(err.value)  # la cle n'apparait jamais dans les messages


def _tmp_sig_dir():
    import tempfile
    return pathlib.Path(tempfile.mkdtemp()) / "signatures"


@pytest.mark.parametrize("key", ["", "a/../../autre", "cle avec espace", "x" * 200])
def test_update_rejects_missing_or_unsafe_key(key, monkeypatch):
    monkeypatch.setattr(updater, "download", lambda url, key="": pytest.fail("aucun appel"))
    with pytest.raises(updater.UpdateError):
        updater.update_malwarebazaar(directory=_tmp_sig_dir(), auth_key=key)


def test_updates_accumulate_instead_of_replacing(tmp_path, monkeypatch):
    sig_dir = tmp_path / "signatures"
    monkeypatch.setattr(updater, "download", lambda url, key="": FEED)
    updater.update_malwarebazaar(directory=sig_dir, auth_key=KEY)
    newer = _csv_row(b"malware-c", "Emotet").encode()
    monkeypatch.setattr(updater, "download", lambda url, key="": newer)
    _path, added, total = updater.update_malwarebazaar(directory=sig_dir, auth_key=KEY)
    assert (added, total) == (1, 3)


@pytest.mark.skipif(os.name != "posix", reason="droits Unix")
def test_auth_key_is_saved_privately(tmp_path, monkeypatch):
    monkeypatch.delenv(updater.AUTH_KEY_ENV, raising=False)
    config = tmp_path / "app" / "config.json"
    updater.save_auth_key(" cle-secrete-42 ", config)
    assert updater.load_auth_key(config) == "cle-secrete-42"
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
