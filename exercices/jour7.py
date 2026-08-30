class Tache:
    def __init__(self, titre, terminee=False):
        self.titre = titre
        self.terminee = terminee

    def marquer_terminee(self):
        self.terminee = True
    def afficher(self):
        statut = "faite" if self.terminee else "à faire"
        print(f"{self.titre} ({statut})")
taches = [Tache("Acheter du pain"), Tache("Reviser Python"), Tache("Faire du sport")]
taches[0].marquer_terminee()
for t in taches: 
    t.afficher()

