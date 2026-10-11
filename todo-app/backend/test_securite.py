"""Tests des regles de securite.md (un test au moins par faille corrigee)."""
import base64
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from sqlalchemy import text

import app as module_app
from app import app, engine

MOT_DE_PASSE = "motdepasse-solide-42"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def nouveau_compte(client):
    username = f"test_{uuid.uuid4().hex[:8]}"
    reponse = client.post("/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": MOT_DE_PASSE,
    })
    assert reponse.status_code == 201, reponse.get_json()
    token = reponse.get_json()["token"]
    user_id = jwt.decode(token, options={"verify_signature": False})["user_id"]
    return SimpleNamespace(username=username, token=token, id=user_id)


def entetes(token, ip=None):
    resultat = {"Authorization": f"Bearer {token}"}
    if ip:
        resultat["X-Forwarded-For"] = ip
    return resultat


def ip_au_hasard():
    return f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


# ---------- jetons (JWT-1, JWT-3, JWT-5) ----------

def test_jeton_de_reinitialisation_refuse_comme_session(client):
    compte = nouveau_compte(client)
    jeton_reset = module_app.generer_token_reset(compte.id, 0)
    assert client.get("/taches", headers=entetes(jeton_reset)).status_code == 401


def test_jeton_de_session_refuse_pour_reinitialiser(client):
    compte = nouveau_compte(client)
    reponse = client.post("/reset-password", json={"token": compte.token, "password": "nouveau-mot-de-passe-1"})
    assert reponse.status_code == 400


def test_jeton_signe_avec_une_autre_cle_ou_sans_signature_refuse(client):
    compte = nouveau_compte(client)
    maintenant = datetime.now(timezone.utc)
    charge = {"user_id": compte.id, "type": "access", "ver": 0, "iat": maintenant, "exp": maintenant + timedelta(hours=1)}
    faux = jwt.encode(charge, "une-autre-cle-de-32-octets-minimum!!", algorithm="HS256")
    assert client.get("/taches", headers=entetes(faux)).status_code == 401

    def b64(donnees):
        return base64.urlsafe_b64encode(json.dumps(donnees).encode()).rstrip(b"=").decode()
    sans_signature = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'user_id': compte.id, 'exp': 4102444800})}."
    assert client.get("/taches", headers=entetes(sans_signature)).status_code == 401


def test_ancien_jeton_sans_type_accepte_jusqu_a_la_date_limite(client, monkeypatch):
    compte = nouveau_compte(client)
    ancien = jwt.encode(
        {"user_id": compte.id, "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        module_app.SECRET_KEY,
        algorithm="HS256",
    )
    monkeypatch.setattr(module_app, "FIN_JETONS_ANCIENS", datetime.now(timezone.utc) + timedelta(days=1))
    assert client.get("/taches", headers=entetes(ancien)).status_code == 200
    monkeypatch.setattr(module_app, "FIN_JETONS_ANCIENS", datetime.now(timezone.utc) - timedelta(days=1))
    assert client.get("/taches", headers=entetes(ancien)).status_code == 401


def test_reinitialisation_revoque_les_sessions_et_ne_sert_qu_une_fois(client):
    compte = nouveau_compte(client)
    jeton_reset = module_app.generer_token_reset(compte.id, 0)
    nouveau = "nouveau-mot-de-passe-1"

    assert client.post("/reset-password", json={"token": jeton_reset, "password": nouveau}).status_code == 200
    assert client.get("/taches", headers=entetes(compte.token)).status_code == 401
    assert client.post("/reset-password", json={"token": jeton_reset, "password": "encore-un-autre-1"}).status_code == 400

    connexion = client.post("/login", json={"username": compte.username, "password": nouveau})
    assert connexion.status_code == 200
    assert client.get("/taches", headers=entetes(connexion.get_json()["token"])).status_code == 200


# ---------- mots de passe et comptes (AUTH-3, AUTH-6) ----------

def test_mot_de_passe_trop_court_refuse(client):
    reponse = client.post("/register", json={
        "username": f"test_{uuid.uuid4().hex[:8]}", "email": "court@example.com", "password": "court",
    })
    assert reponse.status_code == 400
    assert "12" in reponse.get_json()["erreur"]


def test_mot_de_passe_egal_au_nom_refuse(client):
    username = f"test_{uuid.uuid4().hex[:12]}"
    reponse = client.post("/register", json={
        "username": username, "email": f"{username}@example.com", "password": username,
    })
    assert reponse.status_code == 400


def test_nom_d_utilisateur_invalide_refuse(client):
    reponse = client.post("/register", json={
        "username": "<script>", "email": "x@example.com", "password": MOT_DE_PASSE,
    })
    assert reponse.status_code == 400


def test_nom_admin_reserve(client):
    for nom in (module_app.ADMIN_USERNAME, module_app.ADMIN_USERNAME.upper()):
        reponse = client.post("/register", json={
            "username": nom, "email": f"{uuid.uuid4().hex[:8]}@example.com", "password": MOT_DE_PASSE,
        })
        assert reponse.status_code == 400


def test_admin_reconnu_par_son_role(client):
    compte = nouveau_compte(client)
    assert client.get("/admin/tables", headers=entetes(compte.token)).status_code == 403
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_admin = TRUE WHERE id = :id"), {"id": compte.id})
    assert client.get("/admin/tables", headers=entetes(compte.token)).status_code == 200


# ---------- validation des entrees (VAL-1 a VAL-5) ----------

@pytest.mark.parametrize("corps", [
    {"titre": 123},
    {"titre": "   "},
    {"titre": "x" * 201},
    {"titre": "ok", "champ_inconnu": 1},
    {"titre": "ok", "tags": [f"t{i}" for i in range(11)]},
    {"titre": "ok", "tags": [1, 2]},
    {"titre": "ok", "date_echeance": "pas une date"},
    {"titre": "ok", "recurrence": "annuel"},
    {"titre": "ok", "priorite": "urgente"},
    ["pas", "un", "objet"],
])
def test_tache_invalide_refusee_sans_erreur_500(client, corps):
    compte = nouveau_compte(client)
    reponse = client.post("/taches", json=corps, headers=entetes(compte.token))
    assert reponse.status_code == 400
    assert reponse.get_json()["erreur"]


def test_corps_non_json_refuse(client):
    compte = nouveau_compte(client)
    reponse = client.post("/taches", data="titre=ok", headers=entetes(compte.token))
    assert reponse.status_code == 400


def test_tache_envoyee_par_le_frontend_acceptee(client):
    compte = nouveau_compte(client)
    sans_date = {"titre": "Courses", "date_echeance": "", "recurrence": None, "priorite": None, "tags": []}
    assert client.post("/taches", json=sans_date, headers=entetes(compte.token)).status_code == 201

    complete = {"titre": " Dentiste ", "date_echeance": "2026-10-12T14:00", "recurrence": "hebdomadaire",
                "priorite": "haute", "tags": ["sante"]}
    reponse = client.post("/taches", json=complete, headers=entetes(compte.token))
    assert reponse.status_code == 201
    tache = reponse.get_json()
    assert tache["titre"] == "Dentiste"
    assert tache["date_echeance"] == "2026-10-12T14:00:00"
    assert tache["tags"] == ["sante"]


def test_export_puis_import(client):
    compte = nouveau_compte(client)
    client.post("/taches", json={"titre": "A", "date_echeance": "2026-10-12T14:00", "tags": ["x"]},
                headers=entetes(compte.token))
    export = client.get("/export", headers=entetes(compte.token)).get_json()

    autre = nouveau_compte(client)
    reponse = client.post("/import", json=export, headers=entetes(autre.token))
    assert reponse.status_code == 201
    assert reponse.get_json()["taches_importees"] == 1

    assert client.post("/import", json=[{"titre": 5}], headers=entetes(autre.token)).status_code == 400
    trop = [{"titre": "t"}] * 501
    assert client.post("/import", json=trop, headers=entetes(autre.token)).status_code == 400


def test_requete_trop_volumineuse(client):
    compte = nouveau_compte(client)
    reponse = client.post("/import", data="x" * (1024 * 1024 + 1), content_type="application/json",
                          headers=entetes(compte.token))
    assert reponse.status_code == 413
    assert reponse.get_json()["erreur"]


def test_tronquer_historique_garde_la_fin_et_commence_par_l_utilisateur():
    historique = []
    for i in range(20):
        historique.append({"role": "user", "parts": [{"text": f"question {i}"}]})
        historique.append({"role": "model", "parts": [{"functionCall": {"name": "lister_taches", "args": {}}}]})
        historique.append({"role": "user", "parts": [{"functionResponse": {"name": "lister_taches", "response": {}}}]})
        historique.append({"role": "model", "parts": [{"text": f"reponse {i}"}]})
    resultat = module_app.tronquer_historique(historique)
    assert len(resultat) <= module_app.MAX_HISTORIQUE_MESSAGES
    assert resultat[0]["role"] == "user" and "text" in resultat[0]["parts"][0]
    assert resultat[-1] == historique[-1]


def test_arguments_de_l_ia_valides(client):
    compte = nouveau_compte(client)
    resultat = module_app.executer_fonction_assistant(compte.id, "creer_tache", {"titre": 123})
    assert "erreur" in resultat
    resultat = module_app.executer_fonction_assistant(compte.id, "supprimer_tache", {"tache_id": "abc"})
    assert "erreur" in resultat
    assert client.get("/taches", headers=entetes(compte.token)).get_json() == []


def test_cle_gemini_dans_un_en_tete_et_erreur_masquee(client, monkeypatch):
    compte = nouveau_compte(client)
    appels = []

    def faux_post(url, **kwargs):
        appels.append((url, kwargs))
        return SimpleNamespace(ok=False, status_code=500, text="detail interne du service")

    monkeypatch.setattr(module_app.requests, "post", faux_post)
    reponse = client.post("/assistant", json={"message": "bonjour"}, headers=entetes(compte.token))
    assert reponse.status_code == 502
    assert "detail interne" not in reponse.get_data(as_text=True)
    url, kwargs = appels[0]
    assert "key=" not in url
    assert kwargs["headers"]["x-goog-api-key"] == module_app.GEMINI_API_KEY


# ---------- notifications push : SSRF (VAL-7) ----------

@pytest.mark.parametrize("endpoint", [
    "http://169.254.169.254/latest/meta-data",
    "https://127.0.0.1/push",
    "https://evil.example.com/push",
    "https://fcm.googleapis.com.evil.example.com/push",
    "http://fcm.googleapis.com/fcm/send/abc",
    "https://fcm.googleapis.com:8443/fcm/send/abc",
    "https://user:pass@fcm.googleapis.com/fcm/send/abc",
])
def test_abonnement_push_vers_une_adresse_inconnue_refuse(client, endpoint):
    compte = nouveau_compte(client)
    corps = {"endpoint": endpoint, "expirationTime": None, "keys": {"p256dh": "cle", "auth": "auth"}}
    assert client.post("/push-subscribe", json=corps, headers=entetes(compte.token)).status_code == 400


def test_abonnement_push_d_un_navigateur_accepte(client):
    compte = nouveau_compte(client)
    endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"
    corps = {"endpoint": endpoint, "expirationTime": None, "keys": {"p256dh": "cle", "auth": "auth"}}
    assert client.post("/push-subscribe", json=corps, headers=entetes(compte.token)).status_code == 201
    assert client.post("/push-unsubscribe", json={"endpoint": endpoint}, headers=entetes(compte.token)).status_code == 204


def test_notification_jamais_envoyee_a_une_adresse_inconnue(monkeypatch):
    appels = []
    monkeypatch.setattr(module_app, "webpush", lambda **kwargs: appels.append(kwargs))

    interne = SimpleNamespace(endpoint="http://10.0.0.1:5432/", p256dh="cle", auth="auth")
    assert module_app.envoyer_notification(interne, "titre", "corps") is False
    assert appels == []

    connu = SimpleNamespace(endpoint="https://updates.push.services.mozilla.com/wpush/v2/abc", p256dh="cle", auth="auth")
    assert module_app.envoyer_notification(connu, "titre", "corps") is True
    assert appels[0]["timeout"] == 10


# ---------- CORS et en-tetes (CORS-1, HDR-2) ----------

def test_cors_limite_au_frontend(client):
    reponse = client.get("/vapid-public-key", headers={"Origin": "https://evil.example.com"})
    assert "Access-Control-Allow-Origin" not in reponse.headers

    frontend = module_app.origine(module_app.FRONTEND_URL)
    reponse = client.get("/vapid-public-key", headers={"Origin": frontend})
    assert reponse.headers["Access-Control-Allow-Origin"] == frontend


def test_entetes_de_securite(client):
    reponse = client.get("/vapid-public-key")
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"
    assert reponse.headers["Cache-Control"] == "no-store"
    assert "max-age" in reponse.headers["Strict-Transport-Security"]


# ---------- route appelee par le cron (WH-1) ----------

def test_check_reminders_exige_le_secret(client, monkeypatch):
    monkeypatch.setattr(module_app, "webpush", lambda **kwargs: None)
    assert client.post("/check-reminders").status_code == 401
    assert client.post("/check-reminders", headers={"X-Cron-Secret": "mauvais"}).status_code == 401
    assert client.post("/check-reminders", headers={"X-Cron-Secret": "é"}).status_code == 401
    reponse = client.post("/check-reminders", headers={"X-Cron-Secret": module_app.CRON_SECRET})
    assert reponse.status_code == 200


# ---------- limites de debit (AUTH-4, AUTH-5) ----------

@pytest.fixture
def limites_actives(monkeypatch):
    monkeypatch.setitem(app.config, "LIMITES_DEBIT_ACTIVES", True)
    # Heure figee : toutes les requetes du test tombent dans la meme fenetre de comptage
    instant = time.time()
    monkeypatch.setattr(module_app, "time", SimpleNamespace(time=lambda: instant))


def test_limite_par_compte_sur_la_connexion(client, limites_actives):
    username = f"cible_{uuid.uuid4().hex[:8]}"
    statuts = [
        client.post("/login", json={"username": username, "password": "mauvais"},
                    headers={"X-Forwarded-For": ip_au_hasard()}).status_code
        for _ in range(6)
    ]
    assert statuts == [401] * 5 + [429]


def test_limite_par_ip_sur_la_connexion(client, limites_actives):
    ip = ip_au_hasard()
    statuts = [
        client.post("/login", json={"username": f"x_{uuid.uuid4().hex[:8]}", "password": "mauvais"},
                    headers={"X-Forwarded-For": ip}).status_code
        for _ in range(11)
    ]
    assert statuts == [401] * 10 + [429]


def test_mot_de_passe_oublie_meme_reponse_et_limite(client, monkeypatch, limites_actives):
    envois = []
    monkeypatch.setattr(module_app, "envoyer_email_en_arriere_plan", lambda *args: envois.append(args))

    compte = nouveau_compte(client)
    connu = client.post("/forgot-password", json={"email": f"{compte.username}@example.com"},
                        headers={"X-Forwarded-For": ip_au_hasard()})
    inconnu = client.post("/forgot-password", json={"email": f"{uuid.uuid4().hex}@example.com"},
                          headers={"X-Forwarded-For": ip_au_hasard()})
    assert connu.status_code == inconnu.status_code == 200
    assert connu.get_json() == inconnu.get_json()
    assert len(envois) == 1

    email = f"{uuid.uuid4().hex}@example.com"
    statuts = [
        client.post("/forgot-password", json={"email": email}, headers={"X-Forwarded-For": ip_au_hasard()}).status_code
        for _ in range(4)
    ]
    assert statuts == [200, 200, 200, 429]
