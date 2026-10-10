"""Mise a jour securisee des signatures depuis des sources publiques.

Source par defaut : MalwareBazaar (abuse.ch), empreintes SHA-256 des malwares
recents (48 dernieres heures), gratuites et sous licence CC0. abuse.ch demande une
cle gratuite (Auth-Key, a creer sur https://auth.abuse.ch). Chaque mise a jour
s'ajoute aux precedentes : lancee regulierement, la base grossit au fil du temps.

C'est la seule partie de FreeAV qui utilise le reseau, et seulement quand
l'utilisateur la lance. Elle ne fait que telecharger : aucune information sur
l'utilisateur ou ses fichiers n'est envoyee.
"""

import json
import os
import re
import ssl
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .paths import APP_DIR, SIGNATURES_DIR, ensure_private_dir

MALWAREBAZAAR_URL = "https://bazaar.abuse.ch/export/txt/sha256/recent/"
MAX_DOWNLOAD = 50 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONFIG_FILE = APP_DIR / "config.json"
AUTH_KEY_ENV = "FREEAV_ABUSECH_AUTH_KEY"


class UpdateError(Exception):
    pass


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Une redirection vers http:// ferait perdre le chiffrement : on la refuse."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise UpdateError(f"Redirection non chiffree refusee : {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_auth_key(config_file: Path = CONFIG_FILE) -> str:
    if key := os.environ.get(AUTH_KEY_ENV, "").strip():
        return key
    try:
        return json.loads(Path(config_file).read_text(encoding="utf-8")).get("abusech_auth_key", "")
    except (OSError, ValueError):
        return ""


def save_auth_key(key: str, config_file: Path = CONFIG_FILE) -> None:
    """Enregistre la cle dans ~/.freeav/config.json, lisible par le seul utilisateur."""
    config_file = Path(config_file)
    ensure_private_dir(config_file.parent)
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    config["abusech_auth_key"] = key.strip()
    fd, tmp = tempfile.mkstemp(dir=config_file.parent, prefix=".config-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(config, fh)
    os.replace(tmp, config_file)


def download(url: str, auth_key: str = "", timeout: float = 60.0) -> bytes:
    if not url.startswith("https://"):
        raise UpdateError("Seules les sources HTTPS sont acceptees")
    context = ssl.create_default_context()  # certificat et nom d'hote verifies
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
                                         _HttpsOnlyRedirects())
    headers = {"User-Agent": "FreeAV-updater"}
    if auth_key:
        headers["Auth-Key"] = auth_key
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
            data = resp.read(MAX_DOWNLOAD + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise UpdateError("abuse.ch refuse l'acces : une cle Auth-Key gratuite est "
                              "necessaire (https://auth.abuse.ch), puis "
                              "freeav update --auth-key VOTRE_CLE") from exc
        raise UpdateError(f"Erreur HTTP {exc.code}") from exc
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


def _existing_hashes(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    return [parts[1] for line in lines
            if len(parts := line.split(":")) == 3 and parts[0] == "sha256"
            and SHA256_RE.match(parts[1])]


def update_malwarebazaar(url: str = MALWAREBAZAAR_URL, directory: Path = SIGNATURES_DIR,
                         auth_key: str | None = None) -> tuple[Path, int, int]:
    """Telecharge les empreintes recentes et les ajoute a la base existante.
    Retourne (fichier, nouvelles empreintes, total)."""
    if auth_key is None:
        auth_key = load_auth_key()
    fresh = parse_sha256_feed(download(url, auth_key))
    known = _existing_hashes(Path(directory) / "malwarebazaar.txt")
    added = len(set(fresh) - set(known))
    merged = known + fresh
    path = write_signatures(merged, "malwarebazaar", "MalwareBazaar.Malware", directory)
    return path, added, len(dict.fromkeys(merged))
