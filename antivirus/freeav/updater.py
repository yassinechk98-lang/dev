"""Mise a jour securisee des signatures depuis des sources publiques.

Source par defaut : MalwareBazaar (abuse.ch), empreintes SHA-256 des malwares
recents, gratuites et sous licence CC0.

C'est la seule partie de FreeAV qui utilise le reseau, et seulement quand
l'utilisateur la lance. Elle ne fait que telecharger : aucune information sur
l'utilisateur ou ses fichiers n'est envoyee.
"""

import os
import re
import ssl
import tempfile
import urllib.request
from pathlib import Path

from .paths import SIGNATURES_DIR, ensure_private_dir

MALWAREBAZAAR_URL = "https://bazaar.abuse.ch/export/txt/sha256/recent/"
MAX_DOWNLOAD = 50 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UpdateError(Exception):
    pass


def download(url: str, timeout: float = 60.0) -> bytes:
    if not url.startswith("https://"):
        raise UpdateError("Seules les sources HTTPS sont acceptees")
    context = ssl.create_default_context()  # certificat et nom d'hote verifies
    request = urllib.request.Request(url, headers={"User-Agent": "FreeAV-updater"})
    with urllib.request.urlopen(request, timeout=timeout, context=context) as resp:
        data = resp.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise UpdateError("Fichier de signatures trop volumineux, mise a jour refusee")
    return data


def parse_sha256_feed(data: bytes) -> list[str]:
    """Valide strictement le flux : toute ligne inattendue fait echouer la mise a jour."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise UpdateError("Flux de signatures illisible") from exc
    hashes = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().strip('"').lower()
        if not line or line.startswith("#"):
            continue
        if not SHA256_RE.match(line):
            raise UpdateError(f"Ligne {lineno} invalide dans le flux, mise a jour refusee")
        hashes.append(line)
    if not hashes:
        raise UpdateError("Le flux ne contient aucune signature")
    return hashes


def write_signatures(hashes: list[str], name: str, label: str,
                     directory: Path = SIGNATURES_DIR) -> Path:
    """Ecrit la base de facon atomique : une mise a jour interrompue ne casse rien."""
    ensure_private_dir(directory)
    target = Path(directory) / f"{name}.txt"
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            fh.write(f"# {label} - genere par FreeAV\n")
            fh.writelines(f"sha256:{h}:{label}\n" for h in dict.fromkeys(hashes))
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def update_malwarebazaar(url: str = MALWAREBAZAAR_URL,
                         directory: Path = SIGNATURES_DIR) -> tuple[Path, int]:
    hashes = parse_sha256_feed(download(url))
    return write_signatures(hashes, "malwarebazaar", "MalwareBazaar.Malware", directory), len(hashes)
