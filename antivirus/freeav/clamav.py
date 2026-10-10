"""Client minimal pour le demon ClamAV (clamd), sans dependance externe.

Utilise le protocole INSTREAM : le fichier est envoye par blocs au demon,
qui repond "stream: OK" ou "stream: <Nom> FOUND".
"""

import ipaddress
import socket
import struct
from pathlib import Path

CHUNK = 64 * 1024


class ClamdError(Exception):
    pass


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class ClamdClient:
    def __init__(self, unix_socket: str | None = None, host: str = "127.0.0.1",
                 port: int = 3310, timeout: float = 30.0, allow_remote: bool = False):
        # Protection de la vie privee : le contenu des fichiers est envoye a clamd,
        # donc on refuse par defaut tout demon qui n'est pas sur cette machine.
        if not unix_socket and not allow_remote and not _is_loopback(host):
            raise ClamdError(f"clamd sur {host} n'est pas local : vos fichiers quitteraient "
                             "l'ordinateur. Utilisez --allow-remote-clamd si c'est voulu.")
        self.unix_socket = unix_socket
        self.host = host
        self.port = port
        self.timeout = timeout

    def _connect(self) -> socket.socket:
        try:
            if self.unix_socket:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect(self.unix_socket)
            else:
                sock = socket.create_connection((self.host, self.port), self.timeout)
            return sock
        except OSError as exc:
            raise ClamdError(f"Impossible de joindre clamd : {exc}") from exc

    def _command(self, sock: socket.socket) -> str:
        data = b""
        while not data.endswith(b"\0"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.rstrip(b"\0").decode("utf-8", "replace").strip()

    def ping(self) -> bool:
        try:
            with self._connect() as sock:
                sock.sendall(b"zPING\0")
                return self._command(sock) == "PONG"
        except (ClamdError, OSError):
            return False

    def scan_file(self, path: Path) -> str | None:
        """Retourne le nom de la menace detectee, ou None si le fichier est sain."""
        with self._connect() as sock, open(path, "rb") as fh:
            sock.sendall(b"zINSTREAM\0")
            while chunk := fh.read(CHUNK):
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = self._command(sock)
        if reply.endswith("FOUND"):
            return reply.split(":", 1)[1].rsplit(" ", 1)[0].strip()
        if reply.endswith("OK"):
            return None
        raise ClamdError(f"Reponse inattendue de clamd : {reply}")
