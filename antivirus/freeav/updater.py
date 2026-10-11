"""Mise a jour securisee des signatures depuis des sources publiques.

Source par defaut : MalwareBazaar (abuse.ch), empreintes SHA-256 des malwares
recents (48 dernieres heures), gratuites et sous licence CC0. abuse.ch demande une
cle gratuite (Auth-Key, a creer sur https://auth.abuse.ch). Chaque mise a jour
s'ajoute aux precedentes : lancee regulierement, la base grossit au fil du temps.

C'est la seule partie de FreeAV qui utilise le reseau, et seulement quand
l'utilisateur la lance. Elle ne fait que telecharger : aucune information sur
l'utilisateur ou ses fichiers n'est envoyee.
"""

import csv
import io
import json
import os
import re
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .paths import APP_DIR, SIGNATURES_DIR, ensure_private_dir

# Adresse documentee sur https://bazaar.abuse.ch/export/ : la cle fait partie du chemin.
MALWAREBAZAAR_URL = "https://mb-api.abuse.ch/v2/files/exports/{key}/recent.csv"
MAX_DOWNLOAD = 50 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
AUTH_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
FAMILY_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DEFAULT_LABEL = "MalwareBazaar.Malware"
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


def check_auth_key(key: str) -> str:
    """La cle est inseree dans l'adresse : on n'accepte que des caracteres sans risque."""
    key = key.strip()
    if not key:
        raise UpdateError("Cle Auth-Key manquante : creez-en une gratuitement sur "
                          "https://auth.abuse.ch puis lancez "
                          "freeav update --auth-key VOTRE_CLE --save-key")
    if not AUTH_KEY_RE.match(key):
        raise UpdateError("Cle Auth-Key invalide (lettres, chiffres, - et _ uniquement)")
    return key


def load_auth_key(config_file: Path = CONFIG_FILE) -> str:
    if key := os.environ.get(AUTH_KEY_ENV, "").strip():
        return key
    try:
        return json.loads(Path(config_file).read_text(encoding="utf-8")).get("abusech_auth_key", "")
    except (OSError, ValueError):
        return ""


def save_auth_key(key: str, config_file: Path = CONFIG_FILE) -> None:
    """Enregistre la cle dans ~/.freeav/config.json, lisible par le seul utilisateur."""
    save_setting("abusech_auth_key", check_auth_key(key), config_file)


def load_setting(name: str, default=None, config_file: Path = CONFIG_FILE):
    try:
        return json.loads(Path(config_file).read_text(encoding="utf-8")).get(name, default)
    except (OSError, ValueError, AttributeError):
        return default


def save_setting(name: str, value, config_file: Path = CONFIG_FILE) -> None:
    """Enregistre un reglage dans ~/.freeav/config.json, lisible par le seul utilisateur."""
    config_file = Path(config_file)
    ensure_private_dir(config_file.parent)
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            config = {}
    except (OSError, ValueError):
        config = {}
    config[name] = value
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
        # Messages rediges a la main : l'adresse (qui contient la cle) n'est jamais affichee.
        if exc.code in (401, 403, 404):
            raise UpdateError("abuse.ch refuse la cle Auth-Key : verifiez-la sur "
                              "https://auth.abuse.ch") from None
        raise UpdateError(f"abuse.ch a repondu par une erreur HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise UpdateError(f"abuse.ch injoignable ({exc.reason})") from None
    if len(data) > MAX_DOWNLOAD:
        raise UpdateError("Fichier de signatures trop volumineux, mise a jour refusee")
    return data


def parse_malwarebazaar_csv(data: bytes) -> dict[str, str]:
    """Lit l'export CSV de MalwareBazaar et retourne {sha256: nom de la menace}.

    Validation stricte : toute ligne sans empreinte SHA-256 valide fait echouer la mise a
    jour, pour qu'une page piegee ou une reponse inattendue ne remplisse jamais la base.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UpdateError("Flux de signatures illisible") from exc
    header: list[str] | None = None
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            # L'en-tete des colonnes est souvent dans un commentaire : # "first_seen_utc","sha256_hash",...
            if "sha256_hash" in stripped:
                header = next(csv.reader([stripped.lstrip("#").strip()]))
            continue
        rows.append(stripped)
    records = list(csv.reader(io.StringIO("\n".join(rows)), skipinitialspace=True))
    if records and "sha256_hash" in [c.strip() for c in records[0]]:
        header = records.pop(0)
    header = [c.strip() for c in header] if header else []
    sha_col = header.index("sha256_hash") if "sha256_hash" in header else 1
    fam_col = header.index("signature") if "signature" in header else None

    signatures: dict[str, str] = {}
    for lineno, record in enumerate(records, 1):
        sha = record[sha_col].strip().lower() if len(record) > sha_col else ""
        if not SHA256_RE.match(sha):
            raise UpdateError(f"Ligne {lineno} invalide dans le flux, mise a jour refusee")
        family = record[fam_col].strip() if fam_col is not None and len(record) > fam_col else ""
        signatures[sha] = f"MalwareBazaar.{family}" if FAMILY_RE.match(family) \
            and family.lower() != "n/a" else DEFAULT_LABEL
    if not signatures:
        raise UpdateError("Le flux ne contient aucune signature")
    return signatures


def write_signatures(signatures: dict[str, str], name: str,
                     directory: Path = SIGNATURES_DIR) -> Path:
    """Ecrit la base de facon atomique : une mise a jour interrompue ne casse rien."""
    ensure_private_dir(directory)
    target = Path(directory) / f"{name}.txt"
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            fh.write(f"# {name} - genere par FreeAV\n")
            fh.writelines(f"sha256:{h}:{label}\n" for h, label in signatures.items())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def _existing_signatures(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    return {parts[1]: parts[2] for line in lines
            if len(parts := line.split(":")) == 3 and parts[0] == "sha256"
            and SHA256_RE.match(parts[1])}


def update_malwarebazaar(url: str = MALWAREBAZAAR_URL, directory: Path = SIGNATURES_DIR,
                         auth_key: str | None = None) -> tuple[Path, int, int]:
    """Telecharge les empreintes des 48 dernieres heures et les ajoute a la base existante.
    abuse.ch regenere cet export toutes les 5 minutes : inutile de le lancer plus souvent.
    Retourne (fichier, nouvelles empreintes, total)."""
    key = check_auth_key(load_auth_key() if auth_key is None else auth_key)
    fresh = parse_malwarebazaar_csv(download(url.format(key=urllib.parse.quote(key, safe="")), key))
    path = Path(directory) / "malwarebazaar.txt"
    known = _existing_signatures(path)
    added = len(fresh.keys() - known.keys())
    merged = {**known, **fresh}
    return write_signatures(merged, "malwarebazaar", directory), added, len(merged)
