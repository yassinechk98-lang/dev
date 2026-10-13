# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Connexion locale a la fenetre de FreeAV : pseudo, mot de passe et code a usage unique (OTP).

Tout reste sur ce PC : pas de compte en ligne, rien n'est envoye, aucune connexion reseau.
Le fichier ~/.freeav/login.json (lisible par le seul utilisateur) contient :
  - le pseudo ;
  - l'empreinte scrypt du mot de passe (jamais le mot de passe lui-meme) ;
  - la cle des codes OTP (RFC 6238 : 6 chiffres toutes les 30 secondes, comme Google ou
    Microsoft Authenticator), si l'OTP est active, et le dernier code accepte (un code ne
    sert qu'une fois) ;
  - l'empreinte scrypt des codes de secours, chacun utilisable une seule fois ;
  - le nombre d'essais rates, qui impose une attente croissante.

« Mot de passe oublie » : un code de l'application d'authentification, ou un code de secours,
permet de choisir un nouveau mot de passe.

Limite : c'est un verrou pour la fenetre de FreeAV (contre quelqu'un qui utiliserait votre
session Windows), pas un coffre-fort. La protection en arriere-plan continue sans connexion, et
quelqu'un qui peut modifier vos fichiers peut retirer ce verrou en supprimant login.json.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from .paths import APP_DIR, ensure_private_dir

LOGIN_FILE = APP_DIR / "login.json"
ISSUER = "FreeAV"
NICKNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD, MAX_PASSWORD = 12, 128
SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}          # mot de passe (environ 0,1 s par essai)
SCRYPT_RECOVERY = {"n": 2 ** 14, "r": 8, "p": 1}  # codes de secours (8 a verifier au pire)
RECOVERY_CODES = 8
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I, faciles a recopier
OTP_STEP, OTP_DIGITS = 30, 6
MAX_FAILURES = 5      # ensuite, attente croissante avant chaque nouvel essai
BASE_DELAY = 30       # secondes, doublee a chaque nouvel echec...
MAX_DELAY = 15 * 60   # ... sans depasser 15 minutes
GENERIC_ERROR = "Pseudo ou mot de passe incorrect."
CODE_ERROR = "Code incorrect ou expiré."
COMMON_PASSWORDS = {
    "motdepasse123", "motdepasse1234", "123456789012", "1234567890123", "azertyuiop12",
    "azertyuiop123", "qwertyuiop12", "qwertyuiop123", "password1234", "password12345",
    "administrateur", "freeav123456", "freeavfreeav", "bonjour123456", "soleil123456",
}


class LoginError(Exception):
    """Refus a montrer tel quel a l'utilisateur."""


class CodeRequired(LoginError):
    """Pseudo et mot de passe corrects : il faut maintenant le code OTP."""

    def __init__(self):
        super().__init__("Entrez le code de votre application d'authentification.")


class Locked(LoginError):
    def __init__(self, wait: int):
        self.wait = wait
        super().__init__(f"Trop d'essais. Réessayez dans {_duration(wait)}.")


def _duration(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} secondes"
    return f"{(seconds + 59) // 60} minutes"


@dataclass
class Account:
    nickname: str
    password: dict
    otp_secret: str = ""
    otp_last: int = -1  # dernier pas de 30 secondes accepte : un code ne sert qu'une fois
    recovery: list = field(default_factory=list)
    failures: int = 0
    locked_until: float = 0.0

    @property
    def otp(self) -> bool:
        return bool(self.otp_secret)


@dataclass
class Unlock:
    account: Account
    recovery_used: bool = False

    @property
    def recovery_left(self) -> int:
        return len(self.account.recovery)


# -- mots de passe ----------------------------------------------------------------------

def _normalize(text: str) -> bytes:
    return unicodedata.normalize("NFKC", text).encode("utf-8")


def _scrypt(secret: bytes, salt: bytes, params: dict) -> bytes:
    return hashlib.scrypt(secret, salt=salt, maxmem=128 * 1024 * 1024, dklen=32, **params)


def hash_password(password: str, salt: bytes | None = None, params: dict | None = None) -> dict:
    params = dict(params or SCRYPT)
    salt = salt or secrets.token_bytes(16)
    digest = _scrypt(_normalize(password), salt, params)
    return {"alg": "scrypt", **params, "salt": salt.hex(), "hash": digest.hex()}


def check_password(password: str, stored: dict) -> bool:
    try:
        params = {k: int(stored[k]) for k in ("n", "r", "p")}
        expected = bytes.fromhex(stored["hash"])
        salt = bytes.fromhex(stored["salt"])
        if stored.get("alg") != "scrypt" or not 2 ** 10 <= params["n"] <= 2 ** 20:
            return False
        candidate = _scrypt(_normalize(password), salt, params)
    except (KeyError, ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(candidate, expected)


def password_problem(password: str, nickname: str = "") -> str | None:
    """Pourquoi ce mot de passe est refuse, ou None."""
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        return f"Le mot de passe doit faire de {MIN_PASSWORD} à {MAX_PASSWORD} caractères."
    lowered = password.strip().lower()
    if nickname and lowered == nickname.strip().lower():
        return "Le mot de passe ne doit pas être votre pseudo."
    if len(set(password)) <= 2 or lowered in COMMON_PASSWORDS:
        return "Ce mot de passe est trop facile à deviner."
    return None


def strength(password: str, nickname: str = "") -> int:
    """Solidite estimee, de 0 (refuse) a 4 (excellent), pour la jauge de l'interface."""
    if password_problem(password, nickname):
        return 0
    pool = sum(size for test, size in (
        (str.islower, 26), (str.isupper, 26), (str.isdigit, 10),
        (lambda c: not c.isalnum(), 33)) if any(test(c) for c in password))
    bits = len(password) * max(pool, 10).bit_length()
    if len(set(password)) < len(password) / 2:
        bits *= 0.6  # beaucoup de caracteres repetes
    if nickname and nickname.lower() in password.lower():
        bits *= 0.6
    return 1 if bits < 60 else 2 if bits < 75 else 3 if bits < 95 else 4


# -- codes OTP (TOTP, RFC 6238) ---------------------------------------------------------

def new_otp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def totp(secret: str, at: float | None = None, digits: int = OTP_DIGITS) -> str:
    counter = int((time.time() if at is None else at) // OTP_STEP)
    return _hotp(secret, counter, digits)


def _hotp(secret: str, counter: int, digits: int = OTP_DIGITS) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** digits).zfill(digits)


def _clean_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code or "").upper()


def totp_counter(secret: str, code: str, at: float | None = None) -> int | None:
    """Pas de temps du code s'il est valide (une periode de tolerance de chaque cote, pour une
    horloge de telephone un peu decalee), sinon None."""
    code = _clean_code(code)
    if not re.fullmatch(r"\d{%d}" % OTP_DIGITS, code):
        return None
    now = int((time.time() if at is None else at) // OTP_STEP)
    found = None
    for counter in (now - 1, now, now + 1):
        if hmac.compare_digest(_hotp(secret, counter), code):
            found = counter
    return found


def check_totp(secret: str, code: str, at: float | None = None) -> bool:
    return totp_counter(secret, code, at) is not None


def otp_uri(secret: str, nickname: str) -> str:
    """Adresse otpauth:// a mettre dans le QR code (ou a saisir a la main)."""
    label = quote(f"{ISSUER}:{nickname}", safe=":")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}"
            f"&algorithm=SHA1&digits={OTP_DIGITS}&period={OTP_STEP}")


def format_secret(secret: str) -> str:
    """Cle lisible a recopier a la main : groupes de 4 caracteres."""
    return " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))


# -- codes de secours -------------------------------------------------------------------

def new_recovery_codes() -> list[str]:
    return ["-".join("".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(4))
                     for _ in range(2)) for _ in range(RECOVERY_CODES)]


def _hash_recovery(code: str) -> dict:
    salt = secrets.token_bytes(16)
    digest = _scrypt(_clean_code(code).encode("ascii"), salt, SCRYPT_RECOVERY)
    return {"salt": salt.hex(), "hash": digest.hex()}


def _find_recovery(account: Account, code: str) -> dict | None:
    clean = _clean_code(code)
    if not re.fullmatch(r"[A-Z0-9]{8}", clean):
        return None
    found = None
    for entry in account.recovery:  # toutes les empreintes sont calculees : meme duree
        try:
            digest = _scrypt(clean.encode("ascii"), bytes.fromhex(entry["salt"]), SCRYPT_RECOVERY)
            if hmac.compare_digest(digest, bytes.fromhex(entry["hash"])):
                found = entry
        except (KeyError, ValueError, TypeError):
            continue
    return found


# -- stockage ---------------------------------------------------------------------------

def _path(path) -> Path:
    return Path(path or LOGIN_FILE)


def load(path: Path | None = None) -> Account | None:
    try:
        data = json.loads(_path(path).read_text(encoding="utf-8"))
        return Account(nickname=str(data["nickname"]), password=dict(data["password"]),
                       otp_secret=str(data.get("otp_secret") or ""),
                       otp_last=int(data.get("otp_last", -1)),
                       recovery=[dict(e) for e in data.get("recovery") or []],
                       failures=int(data.get("failures", 0)),
                       locked_until=float(data.get("locked_until", 0)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def enabled(path: Path | None = None) -> bool:
    return load(path) is not None


def save(account: Account, path: Path | None = None) -> None:
    path = _path(path)
    ensure_private_dir(path.parent)
    data = {"version": 1, "nickname": account.nickname, "password": account.password,
            "otp_secret": account.otp_secret, "otp_last": account.otp_last,
            "recovery": account.recovery, "failures": account.failures,
            "locked_until": account.locked_until}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".login-")  # fichier en 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def disable(path: Path | None = None) -> None:
    """Retire la connexion : FreeAV s'ouvre de nouveau sans mot de passe."""
    _path(path).unlink(missing_ok=True)


def nickname_problem(nickname: str) -> str | None:
    if not NICKNAME_RE.match(nickname.strip()):
        return "Le pseudo doit faire 3 à 32 caractères : lettres, chiffres, point, tiret ou _."
    return None


def create(nickname: str, password: str, otp_secret: str = "", otp_code: str = "",
           path: Path | None = None, now: float | None = None) -> list[str]:
    """Active la connexion. Si une cle OTP est donnee, le code de l'application doit
    correspondre. Retourne les codes de secours, a montrer une seule fois."""
    nickname = nickname.strip()
    if problem := nickname_problem(nickname) or password_problem(password, nickname):
        raise LoginError(problem)
    account = Account(nickname, hash_password(password))
    if otp_secret:
        counter = totp_counter(otp_secret, otp_code, now)
        if counter is None:
            raise LoginError("Code incorrect. Vérifiez que l'heure du téléphone est juste.")
        account.otp_secret, account.otp_last = otp_secret, counter
    codes = new_recovery_codes()
    account.recovery = [_hash_recovery(c) for c in codes]
    save(account, path)
    return codes


# -- connexion --------------------------------------------------------------------------

def wait_time(account: Account, now: float | None = None) -> int:
    """Secondes a attendre avant un nouvel essai (0 si on peut essayer)."""
    now = time.time() if now is None else now
    return max(0, int(account.locked_until - now + 0.999))


def _guard(path, now: float) -> Account:
    account = load(path)
    if account is None:
        raise LoginError("La connexion n'est pas activée.")
    if wait := wait_time(account, now):
        raise Locked(wait)
    return account


def _failed(account: Account, path, now: float, message: str) -> None:
    account.failures += 1
    if account.failures >= MAX_FAILURES:
        delay = min(BASE_DELAY * 2 ** (account.failures - MAX_FAILURES), MAX_DELAY)
        account.locked_until = now + delay
    save(account, path)
    if account.locked_until > now:
        raise Locked(wait_time(account, now))
    raise LoginError(message)


def _succeeded(account: Account, path, recovery: dict | None = None,
               counter: int | None = None) -> Unlock:
    account.failures, account.locked_until = 0, 0.0
    if counter is not None:
        account.otp_last = counter
    if recovery is not None:
        account.recovery.remove(recovery)
    save(account, path)
    return Unlock(account, recovery_used=recovery is not None)


def _second_factor(account: Account, code: str, now: float):
    """(pas OTP, code de secours) correspondant au code, ou (None, None)."""
    if account.otp:
        counter = totp_counter(account.otp_secret, code, now)
        if counter is not None and counter > account.otp_last:
            return counter, None
    return None, _find_recovery(account, code)


def verify(nickname: str, password: str, code: str | None = None,
           path: Path | None = None, now: float | None = None) -> Unlock:
    """Verifie pseudo et mot de passe, puis le code OTP (ou un code de secours) si l'OTP est
    active. Leve CodeRequired s'il manque le code, LoginError sinon."""
    now = time.time() if now is None else now
    account = _guard(path, now)
    ok_password = check_password(password, account.password)  # calcule meme si le pseudo est faux
    ok_nickname = hmac.compare_digest(nickname.strip().lower().encode(),
                                      account.nickname.lower().encode())
    if not (ok_nickname and ok_password):
        _failed(account, path, now, GENERIC_ERROR)
    if not account.otp:
        return _succeeded(account, path)
    if not code:
        raise CodeRequired()
    counter, recovery = _second_factor(account, code, now)
    if counter is None and recovery is None:
        _failed(account, path, now, CODE_ERROR)
    return _succeeded(account, path, recovery, counter)


def reset_password(nickname: str, code: str, new_password: str,
                   path: Path | None = None, now: float | None = None) -> Unlock:
    """Mot de passe oublie : un code OTP ou un code de secours (qui est alors consomme)."""
    now = time.time() if now is None else now
    account = _guard(path, now)
    if problem := password_problem(new_password, nickname or account.nickname):
        raise LoginError(problem)
    ok_nickname = hmac.compare_digest(nickname.strip().lower().encode(),
                                      account.nickname.lower().encode())
    counter, recovery = _second_factor(account, code, now)
    if not ok_nickname or (counter is None and recovery is None):
        _failed(account, path, now, "Pseudo ou code incorrect.")
    account.password = hash_password(new_password)
    return _succeeded(account, path, recovery, counter)


# -- reglages (apres une nouvelle verification du mot de passe dans l'interface) ----------

def _require(path) -> Account:
    account = load(path)
    if account is None:
        raise LoginError("La connexion n'est pas activée.")
    return account


def change_password(new_password: str, path: Path | None = None) -> None:
    account = _require(path)
    if problem := password_problem(new_password, account.nickname):
        raise LoginError(problem)
    account.password = hash_password(new_password)
    save(account, path)


def enable_otp(secret: str, code: str, path: Path | None = None,
               now: float | None = None) -> None:
    account = _require(path)
    counter = totp_counter(secret, code, now)
    if counter is None:
        raise LoginError("Code incorrect. Vérifiez que l'heure du téléphone est juste.")
    account.otp_secret, account.otp_last = secret, counter
    save(account, path)


def disable_otp(path: Path | None = None) -> None:
    account = _require(path)
    account.otp_secret, account.otp_last = "", -1
    save(account, path)


def renew_recovery_codes(path: Path | None = None) -> list[str]:
    """Nouveaux codes de secours ; les anciens ne marchent plus."""
    account = _require(path)
    codes = new_recovery_codes()
    account.recovery = [_hash_recovery(c) for c in codes]
    save(account, path)
    return codes
