import hashlib
import hmac
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Annotated, Any, Literal, Optional
from urllib.parse import urlsplit

import json

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError, field_validator
from pywebpush import webpush, WebPushException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
# securite.md VAL-4 : taille maximale d'une requete
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
# securite.md AUTH-5 : mis a False par les tests qui n'evaluent pas les limites de debit
app.config["LIMITES_DEBIT_ACTIVES"] = True

FRONTEND_URL = os.environ["FRONTEND_URL"]

def origine(url):
    parties = urlsplit(url.strip())
    return f"{parties.scheme}://{parties.netloc}"

# securite.md CORS-1 : seul le frontend peut appeler l'API depuis un navigateur.
# En local, ajouter par exemple CORS_ORIGINES_SUPPLEMENTAIRES=http://localhost:5173 dans .env
ORIGINES_AUTORISEES = sorted({
    origine(FRONTEND_URL),
    "https://yassine-todo-app.netlify.app",
    *(origine(o) for o in os.environ.get("CORS_ORIGINES_SUPPLEMENTAIRES", "").split(",") if o.strip()),
})
CORS(
    app,
    origins=ORIGINES_AUTORISEES,
    methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    supports_credentials=False,
    max_age=600,
)

@app.after_request
def ajouter_entetes_securite(reponse):
    # securite.md HDR-2
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Referrer-Policy"] = "no-referrer"
    reponse.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    reponse.headers["Cache-Control"] = "no-store"
    return reponse

@app.errorhandler(413)
def requete_trop_grosse(_erreur):
    return jsonify({"erreur": "Requete trop volumineuse"}), 413

SECRET_KEY = os.environ["SECRET_KEY"]
MAILJET_API_KEY = os.environ["MAILJET_API_KEY"]
MAILJET_SECRET_KEY = os.environ["MAILJET_SECRET_KEY"]
MAIL_FROM = os.environ["MAIL_FROM"]
VAPID_PRIVATE_KEY = os.environ["VAPID_PRIVATE_KEY"]
VAPID_PUBLIC_KEY = os.environ["VAPID_PUBLIC_KEY"]
CRON_SECRET = os.environ["CRON_SECRET"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

def initialiser_schema():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT UNIQUE"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS taches (
                id SERIAL PRIMARY KEY,
                titre TEXT NOT NULL,
                terminee BOOLEAN DEFAULT FALSE
            )
        """))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS date_echeance TIMESTAMP"))
        conn.execute(text("ALTER TABLE taches ALTER COLUMN date_echeance TYPE TIMESTAMP"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS rappel_envoye BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS recurrence TEXT"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS terminee_le TIMESTAMP"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS priorite TEXT"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}'"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_taches_user_id ON taches (user_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sous_taches (
                id SERIAL PRIMARY KEY,
                tache_id INTEGER NOT NULL REFERENCES taches(id) ON DELETE CASCADE,
                titre TEXT NOT NULL,
                terminee BOOLEAN DEFAULT FALSE
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS partages_liste (
                id SERIAL PRIMARY KEY,
                proprietaire_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                invite_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (proprietaire_id, invite_id)
            )
        """))
        # securite.md JWT-5 : incremente a chaque reinitialisation du mot de passe pour
        # invalider les sessions existantes et le lien de reinitialisation deja utilise
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"))
        # securite.md AUTH-6 : le role admin est stocke en base, pas deduit du nom
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
        # Une seule fois : le compte ADMIN_USERNAME existant devient admin s'il n'y en a encore aucun
        conn.execute(
            text("""
                UPDATE users SET is_admin = TRUE
                WHERE username = :admin AND NOT EXISTS (SELECT 1 FROM users WHERE is_admin)
            """),
            {"admin": ADMIN_USERNAME},
        )
        # securite.md AUTH-5 : compteurs des limites de debit (cle hachee, fenetre de temps)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS limites_debit (
                cle TEXT NOT NULL,
                fenetre TIMESTAMP NOT NULL,
                compteur INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (cle, fenetre)
            )
        """))
        conn.commit()

# Neon (base gratuite) peut mettre quelques secondes a "reveiller" la base au
# tout premier appel apres une periode d'inactivite. On retente plusieurs fois
# pour eviter qu'un demarrage lent ne fasse planter tout le deploiement.
for tentative in range(5):
    try:
        initialiser_schema()
        break
    except OperationalError:
        if tentative == 4:
            raise
        time.sleep(3)

# ---------- validation des entrees (securite.md VAL-1 a VAL-6) ----------

def _vide_vers_none(valeur):
    return None if valeur == "" else valeur

def _sans_fuseau(valeur):
    # Les colonnes sont en TIMESTAMP sans fuseau : on garde l'heure telle qu'ecrite
    return valeur.replace(tzinfo=None) if isinstance(valeur, datetime) else valeur

def texte(mini, maxi):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=mini, max_length=maxi)]

NomUtilisateur = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_.-]{3,32}$")]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
MotDePasse = Annotated[str, StringConstraints(min_length=12, max_length=128)]
Tag = texte(1, 30)
DateEcheance = Annotated[Optional[datetime], BeforeValidator(_vide_vers_none)]
Recurrence = Annotated[Optional[Literal["quotidien", "hebdomadaire"]], BeforeValidator(_vide_vers_none)]
Priorite = Annotated[Optional[Literal["haute", "moyenne", "basse"]], BeforeValidator(_vide_vers_none)]
IdPositif = Annotated[int, Field(gt=0)]

class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")

class InscriptionIn(Schema):
    username: NomUtilisateur
    email: Email
    password: MotDePasse

class ConnexionIn(Schema):
    username: texte(1, 128)
    password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]

class MotDePasseOublieIn(Schema):
    email: Email

class ReinitialisationIn(Schema):
    token: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    password: MotDePasse

class TacheIn(Schema):
    titre: texte(1, 200)
    date_echeance: DateEcheance = None
    recurrence: Recurrence = None
    priorite: Priorite = None
    tags: Optional[Annotated[list[Tag], Field(max_length=10)]] = None

    @field_validator("date_echeance")
    @classmethod
    def _date_sans_fuseau(cls, valeur):
        return _sans_fuseau(valeur)

    @field_validator("tags")
    @classmethod
    def _tags_liste(cls, valeur):
        return valeur or []

class SousTacheIn(Schema):
    titre: texte(1, 200)

class SousTacheImport(SousTacheIn):
    terminee: bool = False

class TacheImport(TacheIn):
    terminee: bool = False
    sous_taches: Optional[Annotated[list[SousTacheImport], Field(max_length=50)]] = None

ImportIn = TypeAdapter(Annotated[list[TacheImport], Field(max_length=500)])

class PartageIn(Schema):
    username: texte(1, 128)

# securite.md VAL-7 : le serveur n'envoie des notifications qu'aux services push connus (anti-SSRF)
HOTES_PUSH = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
SUFFIXES_HOTES_PUSH = (".notify.windows.com",)

def endpoint_push_autorise(url):
    try:
        parties = urlsplit(url)
        port = parties.port
    except ValueError:
        return False
    hote = (parties.hostname or "").lower()
    return (
        parties.scheme == "https"
        and port in (None, 443)
        and parties.username is None
        and parties.password is None
        and (hote in HOTES_PUSH or hote.endswith(SUFFIXES_HOTES_PUSH))
    )

class ClesPush(Schema):
    p256dh: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    auth: Annotated[str, StringConstraints(min_length=1, max_length=64)]

class AbonnementPushIn(Schema):
    endpoint: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    keys: ClesPush
    expirationTime: Optional[float] = None

    @field_validator("endpoint")
    @classmethod
    def _endpoint_connu(cls, valeur):
        if not endpoint_push_autorise(valeur):
            raise ValueError("service de notification non reconnu")
        return valeur

class DesabonnementPushIn(Schema):
    endpoint: Annotated[str, StringConstraints(min_length=1, max_length=2048)]

class MessageAssistant(Schema):
    role: Literal["user", "model"]
    parts: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=50)]

class AssistantIn(Schema):
    message: texte(1, 2000)
    historique: Optional[Annotated[list[MessageAssistant], Field(max_length=200)]] = None

class ArgsTacheId(BaseModel):
    tache_id: IdPositif

LIBELLES_CHAMPS = {
    "username": "Le nom d'utilisateur",
    "email": "L'email",
    "password": "Le mot de passe",
    "titre": "Le titre",
    "message": "Le message",
}

def message_validation(erreur):
    """Message lisible (en francais) pour la premiere erreur de validation."""
    detail = erreur.errors()[0]
    chemin = [str(p) for p in detail["loc"]]
    champ = chemin[-1] if chemin else "corps"
    nom = ".".join(chemin) or "corps"
    libelle = LIBELLES_CHAMPS.get(champ, f"Le champ '{nom}'")
    contexte = detail.get("ctx") or {}
    type_erreur = detail["type"]
    if type_erreur == "missing":
        return f"Le champ '{nom}' est requis"
    if type_erreur == "string_too_short":
        return f"{libelle} doit contenir au moins {contexte.get('min_length')} caractere(s)"
    if type_erreur == "string_too_long":
        return f"{libelle} doit contenir au plus {contexte.get('max_length')} caracteres"
    if type_erreur == "too_long":
        return f"{libelle} contient trop d'elements ({contexte.get('max_length')} maximum)"
    if type_erreur == "string_pattern_mismatch" and champ == "username":
        return "Le nom d'utilisateur doit faire 3 a 32 caracteres (lettres, chiffres, _ . -)"
    if type_erreur == "extra_forbidden":
        return f"Champ inattendu : '{nom}'"
    if type_erreur in ("model_type", "list_type", "dict_type") and not chemin:
        return "Corps JSON invalide"
    return f"{libelle} est invalide"

def lire_json(schema):
    """Valide le corps JSON ; renvoie (donnees, None) ou (None, reponse 400)."""
    corps = request.get_json(silent=True)
    try:
        if isinstance(schema, TypeAdapter):
            return schema.validate_python(corps), None
        return schema.model_validate(corps), None
    except ValidationError as erreur:
        champs = [".".join(str(p) for p in d["loc"]) for d in erreur.errors()]
        return None, (jsonify({"erreur": message_validation(erreur), "champs": champs}), 400)

# ---------- limites de debit (securite.md AUTH-5) ----------

def ip_client():
    # Render place l'IP reelle du client en premiere position de X-Forwarded-For
    transmise = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return transmise[:64] or request.remote_addr or "inconnue"

def trop_de_requetes(*regles):
    """Compte une requete pour chaque regle (nom, valeur, maximum, fenetre en secondes).
    Renvoie True si l'une des limites est depassee dans sa fenetre en cours."""
    if not app.config["LIMITES_DEBIT_ACTIVES"]:
        return False
    depasse = False
    maintenant = int(time.time())
    with engine.begin() as conn:
        for nom, valeur, maximum, fenetre in regles:
            # La valeur (IP, email...) est hachee : la table ne garde aucune donnee personnelle
            cle = hashlib.sha256(f"{nom}:{fenetre}:{valeur}".encode()).hexdigest()
            debut = datetime.fromtimestamp(maintenant - maintenant % fenetre, timezone.utc).replace(tzinfo=None)
            compteur = conn.execute(
                text("""
                    INSERT INTO limites_debit (cle, fenetre, compteur) VALUES (:cle, :debut, 1)
                    ON CONFLICT (cle, fenetre) DO UPDATE SET compteur = limites_debit.compteur + 1
                    RETURNING compteur
                """),
                {"cle": cle, "debut": debut},
            ).scalar()
            depasse = depasse or compteur > maximum
    return depasse

def reponse_trop_de_requetes():
    return jsonify({"erreur": "Trop de tentatives, reessaie dans quelques minutes"}), 429

# ---------- authentification ----------

DUREE_SESSION = timedelta(days=7)
DUREE_RESET = timedelta(minutes=30)
# Les jetons emis avant l'ajout des claims "type" et "ver" (valables 7 jours) restent
# acceptes jusqu'a cette date pour ne deconnecter personne au deploiement. Un jeton de
# reinitialisation a toujours porte "type": "reset" : il ne peut pas passer par ce chemin.
FIN_JETONS_ANCIENS = datetime(2026, 12, 1, tzinfo=timezone.utc)

def _generer(user_id, token_version, type_token, duree):
    maintenant = datetime.now(timezone.utc)
    return jwt.encode(
        {"user_id": user_id, "type": type_token, "ver": token_version, "iat": maintenant, "exp": maintenant + duree},
        SECRET_KEY,
        algorithm="HS256",
    )

def generer_token(user_id, token_version):
    return _generer(user_id, token_version, "access", DUREE_SESSION)

def generer_token_reset(user_id, token_version):
    return _generer(user_id, token_version, "reset", DUREE_RESET)

def decoder_token(token, type_attendu):
    """Decode un jeton et verifie son type (securite.md JWT-1, JWT-3). Leve jwt.InvalidTokenError."""
    donnees = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "user_id"]})
    if not isinstance(donnees["user_id"], int):
        raise jwt.InvalidTokenError("user_id invalide")
    if "type" not in donnees and type_attendu == "access" and datetime.now(timezone.utc) < FIN_JETONS_ANCIENS:
        return donnees
    if donnees.get("type") != type_attendu or "iat" not in donnees or not isinstance(donnees.get("ver"), int):
        raise jwt.InvalidTokenError("type de jeton invalide")
    return donnees

def envoyer_email(destinataire, sujet, html):
    reponse = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        json={
            "Messages": [
                {
                    "From": {"Email": MAIL_FROM, "Name": "Ma Todo-list"},
                    "To": [{"Email": destinataire}],
                    "Subject": sujet,
                    "HTMLPart": html,
                }
            ]
        },
        timeout=10,
    )
    reponse.raise_for_status()

def envoyer_email_en_arriere_plan(destinataire, sujet, html):
    # securite.md AUTH-4 : la reponse ne doit pas attendre l'envoi, sinon son delai
    # revelerait si l'email est inscrit
    def envoyer():
        try:
            envoyer_email(destinataire, sujet, html)
        except requests.RequestException:
            app.logger.exception("Envoi d'email impossible")
    threading.Thread(target=envoyer, daemon=True).start()

def utilisateur_connecte():
    """Renvoie (ligne users, None) pour un jeton de session valide, sinon (None, reponse 401)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"erreur": "Authentification requise"}), 401)
    try:
        donnees = decoder_token(auth[7:], "access")
    except jwt.InvalidTokenError:
        return None, (jsonify({"erreur": "Token invalide ou expire"}), 401)
    with engine.connect() as conn:
        ligne = conn.execute(
            text("SELECT id, token_version, is_admin FROM users WHERE id = :id"), {"id": donnees["user_id"]}
        ).fetchone()
    # securite.md JWT-5 : un jeton emis avant la derniere reinitialisation du mot de passe est revoque
    if not ligne or ("ver" in donnees and donnees["ver"] != ligne.token_version):
        return None, (jsonify({"erreur": "Token invalide ou expire"}), 401)
    return ligne, None

def token_requis(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        utilisateur, erreur = utilisateur_connecte()
        if erreur:
            return erreur
        return f(utilisateur.id, *args, **kwargs)
    return wrapper

def admin_requis(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        utilisateur, erreur = utilisateur_connecte()
        if erreur:
            return erreur
        if not utilisateur.is_admin:
            return jsonify({"erreur": "Acces reserve"}), 403
        return f(utilisateur.id, *args, **kwargs)
    return wrapper

def mot_de_passe_trop_proche(password, *valeurs):
    return any(password.strip().lower() == v.strip().lower() for v in valeurs if v)

@app.route("/register", methods=["POST"])
def register():
    if trop_de_requetes(("register-ip", ip_client(), 10, 3600)):
        return reponse_trop_de_requetes()
    data, erreur = lire_json(InscriptionIn)
    if erreur:
        return erreur
    if mot_de_passe_trop_proche(data.password, data.username, data.email):
        return jsonify({"erreur": "Le mot de passe ne doit pas etre ton nom d'utilisateur ou ton email"}), 400

    with engine.connect() as conn:
        existe = conn.execute(
            text("SELECT id FROM users WHERE lower(username) = lower(:u) OR lower(email) = lower(:e)"),
            {"u": data.username, "e": data.email},
        ).fetchone()
        # Le nom ADMIN_USERNAME est reserve : personne ne peut le revendiquer en s'inscrivant
        if existe or data.username.lower() == ADMIN_USERNAME.lower():
            return jsonify({"erreur": "Ce nom d'utilisateur ou cet email existe deja"}), 400

        resultat = conn.execute(
            text("""
                INSERT INTO users (username, email, password_hash)
                VALUES (:u, :e, :p) RETURNING id, token_version
            """),
            {"u": data.username, "e": data.email, "p": generate_password_hash(data.password)},
        )
        conn.commit()
        ligne = resultat.fetchone()

    return jsonify({"token": generer_token(ligne.id, ligne.token_version)}), 201

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data, erreur = lire_json(MotDePasseOublieIn)
    if erreur:
        return erreur
    if trop_de_requetes(("forgot-ip", ip_client(), 3, 3600), ("forgot-email", data.email.lower(), 3, 3600)):
        return reponse_trop_de_requetes()

    with engine.connect() as conn:
        ligne = conn.execute(
            text("SELECT id, email, token_version FROM users WHERE lower(email) = lower(:e)"), {"e": data.email}
        ).fetchone()

    if ligne:
        token = generer_token_reset(ligne.id, ligne.token_version)
        lien = f"{FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        envoyer_email_en_arriere_plan(
            ligne.email,
            "Reinitialisation de mot de passe - Ma Todo-list",
            f'<p>Clique sur ce lien pour choisir un nouveau mot de passe (valable 30 minutes) :</p><p><a href="{lien}">{lien}</a></p>',
        )

    return jsonify({"message": "Si ce compte existe, un email a ete envoye."})

@app.route("/reset-password", methods=["POST"])
def reset_password():
    if trop_de_requetes(("reset-ip", ip_client(), 10, 3600)):
        return reponse_trop_de_requetes()
    data, erreur = lire_json(ReinitialisationIn)
    if erreur:
        return erreur

    try:
        donnees = decoder_token(data.token, "reset")
    except jwt.InvalidTokenError:
        return jsonify({"erreur": "Lien invalide ou expire"}), 400

    with engine.connect() as conn:
        utilisateur = conn.execute(
            text("SELECT username, email FROM users WHERE id = :id"), {"id": donnees["user_id"]}
        ).fetchone()
        if utilisateur and mot_de_passe_trop_proche(data.password, utilisateur.username, utilisateur.email):
            return jsonify({"erreur": "Le mot de passe ne doit pas etre ton nom d'utilisateur ou ton email"}), 400
        # Le lien ne sert qu'une fois : changer token_version l'invalide, ainsi que les sessions ouvertes
        ligne = conn.execute(
            text("""
                UPDATE users SET password_hash = :p, token_version = token_version + 1
                WHERE id = :id AND token_version = :ver
                RETURNING id
            """),
            {"p": generate_password_hash(data.password), "id": donnees["user_id"], "ver": donnees["ver"]},
        ).fetchone()
        conn.commit()

    if not ligne:
        return jsonify({"erreur": "Lien invalide ou expire"}), 400
    return jsonify({"message": "Mot de passe mis a jour"})

@app.route("/login", methods=["POST"])
def login():
    data, erreur = lire_json(ConnexionIn)
    if erreur:
        return erreur
    if trop_de_requetes(("login-ip", ip_client(), 10, 60), ("login-user", data.username.lower(), 5, 60)):
        return reponse_trop_de_requetes()

    with engine.connect() as conn:
        ligne = conn.execute(
            text("SELECT id, password_hash, token_version FROM users WHERE username = :u"),
            {"u": data.username},
        ).fetchone()

    if not ligne or not check_password_hash(ligne.password_hash, data.password):
        return jsonify({"erreur": "Identifiants invalides"}), 401

    return jsonify({"token": generer_token(ligne.id, ligne.token_version)})

# ---------- taches (scopees par utilisateur) ----------

def formater_tache(ligne):
    tache = dict(ligne._mapping)
    if tache.get("date_echeance"):
        tache["date_echeance"] = tache["date_echeance"].isoformat()
    return tache

def lister_taches_db(user_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("SELECT id, titre, terminee, date_echeance, recurrence, priorite, tags FROM taches WHERE user_id = :uid ORDER BY id"),
            {"uid": user_id},
        )
        return [formater_tache(ligne) for ligne in resultat]

def creer_tache_db(user_id, titre, date_echeance, recurrence=None, priorite=None, tags=None):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                INSERT INTO taches (titre, terminee, user_id, date_echeance, recurrence, priorite, tags)
                VALUES (:titre, FALSE, :uid, :date_echeance, :recurrence, :priorite, :tags)
                RETURNING id, titre, terminee, date_echeance, recurrence, priorite, tags
            """),
            {
                "titre": titre, "uid": user_id, "date_echeance": date_echeance,
                "recurrence": recurrence, "priorite": priorite, "tags": tags or [],
            },
        )
        conn.commit()
        return formater_tache(resultat.fetchone())

def _prochaine_echeance(date_echeance, recurrence):
    if date_echeance is None:
        return None
    jours = 7 if recurrence == "hebdomadaire" else 1
    return date_echeance + timedelta(days=jours)

def basculer_tache_db(user_id, tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                UPDATE taches SET
                    terminee = NOT terminee,
                    terminee_le = CASE WHEN NOT terminee THEN NOW() ELSE NULL END
                WHERE id = :id AND user_id = :uid
                RETURNING id, titre, terminee, date_echeance, recurrence, priorite, tags
            """),
            {"id": tache_id, "uid": user_id},
        )
        ligne = resultat.fetchone()
        if ligne is None:
            conn.commit()
            return None

        tache = formater_tache(ligne)
        if tache["terminee"] and tache["recurrence"]:
            conn.execute(
                text("""
                    INSERT INTO taches (titre, terminee, user_id, date_echeance, recurrence, priorite, tags)
                    VALUES (:titre, FALSE, :uid, :date_echeance, :recurrence, :priorite, :tags)
                """),
                {
                    "titre": tache["titre"],
                    "uid": user_id,
                    "date_echeance": _prochaine_echeance(ligne.date_echeance, tache["recurrence"]),
                    "recurrence": tache["recurrence"],
                    "priorite": tache["priorite"],
                    "tags": tache["tags"],
                },
            )
        conn.commit()
        return tache

def supprimer_tache_db(user_id, tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("DELETE FROM taches WHERE id = :id AND user_id = :uid"),
            {"id": tache_id, "uid": user_id},
        )
        conn.commit()
        return resultat.rowcount > 0

@app.route("/taches", methods=["GET"])
@token_requis
def lister_taches(user_id):
    return jsonify(lister_taches_db(user_id))

@app.route("/taches", methods=["POST"])
@token_requis
def creer_tache(user_id):
    data, erreur = lire_json(TacheIn)
    if erreur:
        return erreur

    nouvelle_tache = creer_tache_db(
        user_id, data.titre, data.date_echeance, data.recurrence, data.priorite, data.tags
    )
    return jsonify(nouvelle_tache), 201

@app.route("/taches/<int:tache_id>", methods=["PUT"])
@token_requis
def modifier_tache(user_id, tache_id):
    tache = basculer_tache_db(user_id, tache_id)
    if tache is None:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    return jsonify(tache)

@app.route("/taches/<int:tache_id>", methods=["DELETE"])
@token_requis
def supprimer_tache(user_id, tache_id):
    supprime = supprimer_tache_db(user_id, tache_id)
    if not supprime:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    return "", 204

# ---------- sous-taches (scopees via la tache parente) ----------

def lister_sous_taches_db(user_id, tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                SELECT st.id, st.titre, st.terminee
                FROM sous_taches st
                JOIN taches t ON t.id = st.tache_id
                WHERE st.tache_id = :tid AND t.user_id = :uid
                ORDER BY st.id
            """),
            {"tid": tache_id, "uid": user_id},
        )
        return [dict(ligne._mapping) for ligne in resultat]

def creer_sous_tache_db(user_id, tache_id, titre):
    with engine.connect() as conn:
        tache = conn.execute(
            text("SELECT id FROM taches WHERE id = :tid AND user_id = :uid"),
            {"tid": tache_id, "uid": user_id},
        ).fetchone()
        if not tache:
            return None
        resultat = conn.execute(
            text("""
                INSERT INTO sous_taches (tache_id, titre)
                VALUES (:tid, :titre)
                RETURNING id, titre, terminee
            """),
            {"tid": tache_id, "titre": titre},
        )
        conn.commit()
        return dict(resultat.fetchone()._mapping)

def basculer_sous_tache_db(user_id, sous_tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                UPDATE sous_taches SET terminee = NOT terminee
                WHERE id = :id AND tache_id IN (SELECT id FROM taches WHERE user_id = :uid)
                RETURNING id, titre, terminee
            """),
            {"id": sous_tache_id, "uid": user_id},
        )
        conn.commit()
        ligne = resultat.fetchone()
        return dict(ligne._mapping) if ligne else None

def supprimer_sous_tache_db(user_id, sous_tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                DELETE FROM sous_taches
                WHERE id = :id AND tache_id IN (SELECT id FROM taches WHERE user_id = :uid)
            """),
            {"id": sous_tache_id, "uid": user_id},
        )
        conn.commit()
        return resultat.rowcount > 0

@app.route("/taches/<int:tache_id>/sous-taches", methods=["GET"])
@token_requis
def lister_sous_taches(user_id, tache_id):
    return jsonify(lister_sous_taches_db(user_id, tache_id))

@app.route("/taches/<int:tache_id>/sous-taches", methods=["POST"])
@token_requis
def creer_sous_tache(user_id, tache_id):
    data, erreur = lire_json(SousTacheIn)
    if erreur:
        return erreur

    sous_tache = creer_sous_tache_db(user_id, tache_id, data.titre)
    if sous_tache is None:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404
    return jsonify(sous_tache), 201

@app.route("/sous-taches/<int:sous_tache_id>", methods=["PUT"])
@token_requis
def modifier_sous_tache(user_id, sous_tache_id):
    sous_tache = basculer_sous_tache_db(user_id, sous_tache_id)
    if sous_tache is None:
        return jsonify({"erreur": f"Aucune sous-tache avec l'id {sous_tache_id}"}), 404
    return jsonify(sous_tache)

@app.route("/sous-taches/<int:sous_tache_id>", methods=["DELETE"])
@token_requis
def supprimer_sous_tache(user_id, sous_tache_id):
    supprime = supprimer_sous_tache_db(user_id, sous_tache_id)
    if not supprime:
        return jsonify({"erreur": f"Aucune sous-tache avec l'id {sous_tache_id}"}), 404
    return "", 204

# ---------- partage de liste (lecture seule) ----------

def creer_partage_db(proprietaire_id, username_invite):
    with engine.connect() as conn:
        invite = conn.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": username_invite}
        ).fetchone()
        if not invite:
            return None, "Utilisateur introuvable"
        if invite.id == proprietaire_id:
            return None, "Impossible de partager avec toi-meme"
        existe = conn.execute(
            text("SELECT id FROM partages_liste WHERE proprietaire_id = :p AND invite_id = :i"),
            {"p": proprietaire_id, "i": invite.id},
        ).fetchone()
        if existe:
            return None, "Deja partage avec cet utilisateur"
        conn.execute(
            text("INSERT INTO partages_liste (proprietaire_id, invite_id) VALUES (:p, :i)"),
            {"p": proprietaire_id, "i": invite.id},
        )
        conn.commit()
        return {"username": username_invite}, None

def lister_partages_db(user_id):
    with engine.connect() as conn:
        mes_partages = conn.execute(
            text("""
                SELECT pl.id, u.username FROM partages_liste pl
                JOIN users u ON u.id = pl.invite_id
                WHERE pl.proprietaire_id = :uid
            """),
            {"uid": user_id},
        ).fetchall()
        partages_avec_moi = conn.execute(
            text("""
                SELECT pl.id, u.id AS proprietaire_id, u.username FROM partages_liste pl
                JOIN users u ON u.id = pl.proprietaire_id
                WHERE pl.invite_id = :uid
            """),
            {"uid": user_id},
        ).fetchall()
    return {
        "mes_partages": [dict(r._mapping) for r in mes_partages],
        "partages_avec_moi": [dict(r._mapping) for r in partages_avec_moi],
    }

def supprimer_partage_db(user_id, partage_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("DELETE FROM partages_liste WHERE id = :id AND proprietaire_id = :uid"),
            {"id": partage_id, "uid": user_id},
        )
        conn.commit()
        return resultat.rowcount > 0

@app.route("/partages", methods=["POST"])
@token_requis
def creer_partage(user_id):
    data, erreur = lire_json(PartageIn)
    if erreur:
        return erreur

    resultat, erreur = creer_partage_db(user_id, data.username)
    if erreur:
        return jsonify({"erreur": erreur}), 404 if erreur == "Utilisateur introuvable" else 400
    return jsonify(resultat), 201

@app.route("/partages", methods=["GET"])
@token_requis
def lister_partages(user_id):
    return jsonify(lister_partages_db(user_id))

@app.route("/partages/<int:partage_id>", methods=["DELETE"])
@token_requis
def supprimer_partage(user_id, partage_id):
    if not supprimer_partage_db(user_id, partage_id):
        return jsonify({"erreur": "Partage introuvable"}), 404
    return "", 204

@app.route("/taches/partages/<int:proprietaire_id>", methods=["GET"])
@token_requis
def lister_taches_partagees(user_id, proprietaire_id):
    with engine.connect() as conn:
        autorise = conn.execute(
            text("SELECT id FROM partages_liste WHERE proprietaire_id = :p AND invite_id = :i"),
            {"p": proprietaire_id, "i": user_id},
        ).fetchone()
    if not autorise:
        return jsonify({"erreur": "Acces non autorise"}), 403
    return jsonify(lister_taches_db(proprietaire_id))

# ---------- export / import ----------

def exporter_taches_db(user_id):
    with engine.connect() as conn:
        taches = conn.execute(
            text("SELECT id, titre, terminee, date_echeance, recurrence, priorite, tags FROM taches WHERE user_id = :uid ORDER BY id"),
            {"uid": user_id},
        ).fetchall()

        resultat = []
        for t in taches:
            sous_taches = conn.execute(
                text("SELECT titre, terminee FROM sous_taches WHERE tache_id = :tid ORDER BY id"),
                {"tid": t.id},
            ).fetchall()
            resultat.append({
                "titre": t.titre,
                "terminee": t.terminee,
                "date_echeance": t.date_echeance.isoformat() if t.date_echeance else None,
                "recurrence": t.recurrence,
                "priorite": t.priorite,
                "tags": t.tags,
                "sous_taches": [{"titre": s.titre, "terminee": s.terminee} for s in sous_taches],
            })
        return resultat

def importer_taches_db(user_id, items):
    compteur = 0
    with engine.connect() as conn:
        for item in items:
            resultat = conn.execute(
                text("""
                    INSERT INTO taches (titre, terminee, user_id, date_echeance, recurrence, priorite, tags)
                    VALUES (:titre, :terminee, :uid, :date_echeance, :recurrence, :priorite, :tags)
                    RETURNING id
                """),
                {
                    "titre": item.titre,
                    "terminee": item.terminee,
                    "uid": user_id,
                    "date_echeance": item.date_echeance,
                    "recurrence": item.recurrence,
                    "priorite": item.priorite,
                    "tags": item.tags,
                },
            )
            tache_id = resultat.fetchone()[0]
            for sous in item.sous_taches or []:
                conn.execute(
                    text("INSERT INTO sous_taches (tache_id, titre, terminee) VALUES (:tid, :titre, :terminee)"),
                    {"tid": tache_id, "titre": sous.titre, "terminee": sous.terminee},
                )
            compteur += 1
        conn.commit()
    return compteur

@app.route("/export", methods=["GET"])
@token_requis
def export_taches(user_id):
    return jsonify(exporter_taches_db(user_id))

@app.route("/import", methods=["POST"])
@token_requis
def import_taches(user_id):
    data, erreur = lire_json(ImportIn)
    if erreur:
        return erreur

    total = importer_taches_db(user_id, data)
    return jsonify({"taches_importees": total}), 201

# ---------- statistiques ----------

def obtenir_stats_db(user_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                SELECT DATE(terminee_le) AS jour, COUNT(*) AS total
                FROM taches
                WHERE user_id = :uid AND terminee_le >= NOW() - INTERVAL '14 days'
                GROUP BY DATE(terminee_le)
                ORDER BY jour
            """),
            {"uid": user_id},
        )
        par_jour = {row.jour.isoformat(): row.total for row in resultat}

        dates_completees = {
            row.jour
            for row in conn.execute(
                text("SELECT DISTINCT DATE(terminee_le) AS jour FROM taches WHERE user_id = :uid AND terminee_le IS NOT NULL"),
                {"uid": user_id},
            )
        }

        taches_actives = conn.execute(
            text("SELECT COUNT(*) FROM taches WHERE user_id = :uid AND terminee = FALSE"),
            {"uid": user_id},
        ).scalar()
        taches_terminees = conn.execute(
            text("SELECT COUNT(*) FROM taches WHERE user_id = :uid AND terminee = TRUE"),
            {"uid": user_id},
        ).scalar()

    serie = 0
    jour_courant = datetime.now(timezone.utc).date()
    if jour_courant not in dates_completees:
        jour_courant -= timedelta(days=1)
    while jour_courant in dates_completees:
        serie += 1
        jour_courant -= timedelta(days=1)

    return {
        "par_jour": [{"date": d, "total": t} for d, t in sorted(par_jour.items())],
        "serie_en_cours": serie,
        "taches_actives": taches_actives,
        "taches_terminees": taches_terminees,
    }

@app.route("/stats", methods=["GET"])
@token_requis
def stats(user_id):
    return jsonify(obtenir_stats_db(user_id))

# ---------- assistant ia ----------

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"

FONCTIONS_ASSISTANT = [
    {
        "name": "lister_taches",
        "description": "Liste toutes les taches de l'utilisateur, avec leur id, titre, statut (terminee) et date d'echeance.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "creer_tache",
        "description": "Cree une nouvelle tache pour l'utilisateur.",
        "parameters": {
            "type": "object",
            "properties": {
                "titre": {"type": "string", "description": "Le titre de la tache"},
                "date_echeance": {
                    "type": "string",
                    "description": "Date et heure d'echeance au format ISO 8601 (ex: 2026-09-03T14:00:00). Omettre si aucune echeance n'est demandee.",
                },
                "recurrence": {
                    "type": "string",
                    "enum": ["quotidien", "hebdomadaire"],
                    "description": "Si la tache doit se repeter automatiquement chaque jour ou chaque semaine. Omettre si la tache ne se repete pas.",
                },
                "priorite": {
                    "type": "string",
                    "enum": ["haute", "moyenne", "basse"],
                    "description": "Niveau de priorite de la tache. Omettre si non precise.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste de mots-cles/categories pour la tache (ex: ['travail', 'urgent']). Omettre si non precise.",
                },
            },
            "required": ["titre"],
        },
    },
    {
        "name": "basculer_tache",
        "description": "Inverse le statut d'une tache (termine une tache en cours, ou reouvre une tache terminee). Appelle lister_taches avant si tu ne connais pas deja l'id.",
        "parameters": {
            "type": "object",
            "properties": {"tache_id": {"type": "integer", "description": "L'id de la tache"}},
            "required": ["tache_id"],
        },
    },
    {
        "name": "supprimer_tache",
        "description": "Supprime definitivement une tache. Appelle lister_taches avant si tu ne connais pas deja l'id.",
        "parameters": {
            "type": "object",
            "properties": {"tache_id": {"type": "integer", "description": "L'id de la tache"}},
            "required": ["tache_id"],
        },
    },
]

def executer_fonction_assistant(user_id, nom, args):
    # securite.md VAL-6 : les arguments produits par l'IA passent par les memes schemas
    try:
        if nom == "lister_taches":
            return {"taches": lister_taches_db(user_id)}
        if nom == "creer_tache":
            donnees = TacheIn.model_validate(args)
            tache = creer_tache_db(
                user_id, donnees.titre, donnees.date_echeance, donnees.recurrence, donnees.priorite, donnees.tags
            )
            return {"tache": tache}
        if nom == "basculer_tache":
            tache = basculer_tache_db(user_id, ArgsTacheId.model_validate(args).tache_id)
            return {"tache": tache} if tache else {"erreur": "tache introuvable"}
        if nom == "supprimer_tache":
            return {"succes": supprimer_tache_db(user_id, ArgsTacheId.model_validate(args).tache_id)}
    except ValidationError as erreur:
        return {"erreur": f"arguments invalides : {message_validation(erreur)}"}
    return {"erreur": "fonction inconnue"}

MAX_HISTORIQUE_MESSAGES = 30
MAX_HISTORIQUE_OCTETS = 64 * 1024

def tronquer_historique(historique):
    """Garde la fin de l'historique dans les limites (securite.md VAL-5), en repartant
    toujours d'un message texte de l'utilisateur pour ne pas couper un appel de fonction."""
    def trop_long(h):
        return len(h) > MAX_HISTORIQUE_MESSAGES or len(json.dumps(h)) > MAX_HISTORIQUE_OCTETS

    while historique and trop_long(historique):
        historique = historique[1:]
        while historique and not (
            historique[0]["role"] == "user" and any("text" in part for part in historique[0]["parts"])
        ):
            historique = historique[1:]
    return historique

@app.route("/assistant", methods=["POST"])
@token_requis
def assistant(user_id):
    if trop_de_requetes(("assistant-user", user_id, 20, 60)):
        return reponse_trop_de_requetes()
    data, erreur = lire_json(AssistantIn)
    if erreur:
        return erreur

    historique = tronquer_historique([m.model_dump() for m in data.historique or []])
    historique.append({"role": "user", "parts": [{"text": data.message}]})

    instruction_systeme = (
        "Tu es un assistant qui aide l'utilisateur a gerer sa todo-list en francais. "
        "Utilise les fonctions disponibles pour lister, creer, terminer/reouvrir ou supprimer des taches. "
        f"La date et l'heure actuelles sont : {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} ({datetime.now().strftime('%A')}). "
        "Quand l'utilisateur donne une date relative (demain, ce soir, lundi prochain...), calcule la date exacte. "
        "Reponds toujours de maniere breve et naturelle en francais apres avoir effectue les actions necessaires."
    )

    for _ in range(5):
        reponse = requests.post(
            GEMINI_URL,
            # securite.md SEC-3 : la cle passe dans un en-tete, jamais dans l'URL
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={
                "contents": historique,
                "system_instruction": {"parts": [{"text": instruction_systeme}]},
                "tools": [{"functionDeclarations": FONCTIONS_ASSISTANT}],
            },
            timeout=30,
        )
        if not reponse.ok:
            # securite.md SEC-5 : le detail reste dans les logs du serveur
            app.logger.warning("Erreur Gemini %s : %s", reponse.status_code, reponse.text[:500])
            return jsonify({"erreur": "L'assistant IA est indisponible pour le moment"}), 502
        candidat = reponse.json()["candidates"][0]
        parts = candidat["content"]["parts"]
        historique.append({"role": "model", "parts": parts})

        appels = [p for p in parts if "functionCall" in p]
        if not appels:
            texte = "".join(p.get("text", "") for p in parts)
            return jsonify({"reponse": texte, "historique": historique})

        parts_reponse = []
        for appel in appels:
            fc = appel["functionCall"]
            resultat_fonction = executer_fonction_assistant(user_id, fc["name"], fc.get("args", {}))
            part_reponse = {"functionResponse": {"name": fc["name"], "response": resultat_fonction}}
            if "id" in fc:
                part_reponse["functionResponse"]["id"] = fc["id"]
            parts_reponse.append(part_reponse)

        historique.append({"role": "user", "parts": parts_reponse})

    return jsonify({"erreur": "L'assistant n'a pas pu terminer la demande"}), 500

# ---------- notifications push ----------

@app.route("/vapid-public-key", methods=["GET"])
def vapid_public_key():
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})

@app.route("/push-subscribe", methods=["POST"])
@token_requis
def push_subscribe(user_id):
    data, erreur = lire_json(AbonnementPushIn)
    if erreur:
        return erreur

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
                VALUES (:uid, :endpoint, :p256dh, :auth)
                ON CONFLICT (endpoint) DO UPDATE
                SET user_id = :uid, p256dh = :p256dh, auth = :auth
            """),
            {
                "uid": user_id,
                "endpoint": data.endpoint,
                "p256dh": data.keys.p256dh,
                "auth": data.keys.auth,
            },
        )
        conn.commit()

    return jsonify({"message": "Abonnement enregistre"}), 201

@app.route("/push-unsubscribe", methods=["POST"])
@token_requis
def push_unsubscribe(user_id):
    data, erreur = lire_json(DesabonnementPushIn)
    if erreur:
        return erreur

    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM push_subscriptions WHERE endpoint = :endpoint AND user_id = :uid"),
            {"endpoint": data.endpoint, "uid": user_id},
        )
        conn.commit()

    return "", 204

def envoyer_notification(subscription, titre, corps):
    # securite.md VAL-7 : aussi verifie a l'envoi, pour les abonnements enregistres avant ce controle
    if not endpoint_push_autorise(subscription.endpoint):
        return False
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": titre, "body": corps}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{MAIL_FROM}"},
            timeout=10,
        )
        return True
    except WebPushException as e:
        statut = e.response.status_code if e.response is not None else None
        if statut in (404, 410):
            # abonnement expire ou desinstalle : on le supprime
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM push_subscriptions WHERE endpoint = :endpoint"),
                    {"endpoint": subscription.endpoint},
                )
                conn.commit()
        return False

@app.route("/check-reminders", methods=["POST"])
def check_reminders():
    # securite.md WH-1 : comparaison en temps constant
    secret_recu = request.headers.get("X-Cron-Secret", "")
    if not hmac.compare_digest(secret_recu.encode(), CRON_SECRET.encode()):
        return jsonify({"erreur": "non autorise"}), 401

    with engine.connect() as conn:
        # Menage des compteurs de limites de debit (fenetres d'une heure au plus)
        conn.execute(text("DELETE FROM limites_debit WHERE fenetre < NOW() - INTERVAL '1 day'"))
        conn.commit()

        # securite.md WH-5 : traitement borne, le reste passera au prochain appel
        taches_a_notifier = conn.execute(text("""
            SELECT id, user_id, titre FROM taches
            WHERE date_echeance IS NOT NULL
              AND date_echeance <= NOW()
              AND terminee = FALSE
              AND rappel_envoye = FALSE
            ORDER BY date_echeance
            LIMIT 500
        """)).fetchall()

        notifiees = 0
        for tache in taches_a_notifier:
            abonnements = conn.execute(
                text("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = :uid"),
                {"uid": tache.user_id},
            ).fetchall()

            for abonnement in abonnements:
                if envoyer_notification(abonnement, "Tache en retard", tache.titre):
                    notifiees += 1

            conn.execute(
                text("UPDATE taches SET rappel_envoye = TRUE WHERE id = :id"),
                {"id": tache.id},
            )
            conn.commit()

    return jsonify({"taches_verifiees": len(taches_a_notifier), "notifications_envoyees": notifiees})

# ---------- admin (reserve aux comptes is_admin) ----------

TABLES_ADMIN = {
    "users": ["id", "username", "email"],
    "taches": ["id", "titre", "terminee", "user_id", "date_echeance", "recurrence", "priorite", "tags", "terminee_le", "rappel_envoye"],
    "sous_taches": ["id", "tache_id", "titre", "terminee"],
    "push_subscriptions": ["id", "user_id", "endpoint"],
}

@app.route("/admin/tables", methods=["GET"])
@admin_requis
def admin_lister_tables(user_id):
    with engine.connect() as conn:
        infos = [
            {"nom": nom, "total": conn.execute(text(f"SELECT COUNT(*) FROM {nom}")).scalar()}
            for nom in TABLES_ADMIN
        ]
    return jsonify(infos)

@app.route("/admin/tables/<nom_table>", methods=["GET"])
@admin_requis
def admin_lister_lignes(user_id, nom_table):
    if nom_table not in TABLES_ADMIN:
        return jsonify({"erreur": "table inconnue"}), 404

    colonnes = TABLES_ADMIN[nom_table]
    colonnes_sql = ", ".join(colonnes)
    with engine.connect() as conn:
        resultat = conn.execute(text(f"SELECT {colonnes_sql} FROM {nom_table} ORDER BY id DESC LIMIT 200"))
        lignes = [dict(ligne._mapping) for ligne in resultat]

    for ligne in lignes:
        for cle, valeur in ligne.items():
            if hasattr(valeur, "isoformat"):
                ligne[cle] = valeur.isoformat()

    return jsonify({"colonnes": colonnes, "lignes": lignes})

if __name__ == "__main__":
    # securite.md AUTH-8 : jamais de mode debug en production
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
