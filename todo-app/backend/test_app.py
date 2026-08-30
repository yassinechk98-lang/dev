import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_lister_taches(client):
    reponse = client.get("/taches")
    assert reponse.status_code == 200

def test_creer_tache(client):
    reponse = client.post("/taches", json={"titre": "Tache de test"})
    assert reponse.status_code == 201
    assert reponse.get_json()["titre"] == "Tache de test"

def test_creer_tache_sans_titre(client):
    reponse = client.post("/taches", json={})
    assert reponse.status_code == 400

def test_supprimer_tache_inexistante(client):
    reponse = client.delete("/taches/999999")
    assert reponse.status_code == 404
