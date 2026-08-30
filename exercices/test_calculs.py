import pytest
from calculs import additionner, diviser
def test_additionner():
    assert additionner(2, 3) == 5
    assert additionner(-1, 1) == 0
def test_diviser():
    assert diviser(10, 2) == 5
def test_diviser_par_zero():
    with pytest.raises(ValueError):
        diviser(10, 0)