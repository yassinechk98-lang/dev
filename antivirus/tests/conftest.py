import pytest


@pytest.fixture(autouse=True)
def not_elevated(monkeypatch):
    """La CI Windows tourne en administrateur : les tests de quarantaine se placent dans le cas
    courant d'un utilisateur sans droits (le cas administrateur a son propre test)."""
    monkeypatch.setattr("freeav.quarantine._is_elevated", lambda: False)
