import pytest

from app import app


@pytest.fixture(autouse=True)
def sans_limites_de_debit(monkeypatch):
    # Les tests creent beaucoup de comptes depuis la meme IP : les limites de debit
    # ne sont activees que dans les tests qui les verifient.
    monkeypatch.setitem(app.config, "LIMITES_DEBIT_ACTIVES", False)
