def calculer_moyenne(notes):
    return sum(notes) / len(notes)
mes_notes = [12, 15, 9, 18]
moyenne = calculer_moyenne(mes_notes)
print(f"Moyenne :{moyenne}")
etudiant = {
    "nom": "Yassine",
    "ville": "Monastir",
    "notes": mes_notes }

for cle, valeur in etudiant.items():
    print(f"{cle} : {valeur}")