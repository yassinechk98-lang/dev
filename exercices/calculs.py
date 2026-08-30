def additionner(a, b):
    return a + b
def diviser(a, b):
    if b == 0:
        raise ValueError("Division par zero impossible")
    return a / b