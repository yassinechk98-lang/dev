import uuid

import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def token(client):
    suffixe = uuid.uuid4().hex[:8]
    reponse = client.post("/register", json={
        "username": f"test_{suffixe}",
        "email": f"test_{suffixe}@example.com",
        "password": "motdepasse",
    })
    return reponse.get_json()["token"]

@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def test_lister_taches(client, auth_headers):
    reponse = client.get("/taches", headers=auth_headers)
    assert reponse.status_code == 200

def test_creer_tache(client, auth_headers):
    reponse = client.post("/taches", json={"titre": "Tache de test"}, headers=auth_headers)
    assert reponse.status_code == 201
    assert reponse.get_json()["titre"] == "Tache de test"

def test_creer_tache_sans_titre(client, auth_headers):
    reponse = client.post("/taches", json={}, headers=auth_headers)
    assert reponse.status_code == 400

def test_supprimer_tache_inexistante(client, auth_headers):
    reponse = client.delete("/taches/999999", headers=auth_headers)
    assert reponse.status_code == 404

def test_acces_sans_token(client):
    reponse = client.get("/taches")
    assert reponse.status_code == 401
