class Tache:
    def __init__(self, titre, priorite="normale", terminee=False):
        self.titre = titre
        self.priorite = priorite
        self.terminee = terminee
    def marquer_terminee(self):
        self.terminee = True
    def changer_priorite(self, nouvelle_priorite):
        self.priorite = nouvelle_priorite
    def afficher(self):
        statut = "faite" if self.terminee else "à faire"
        print(f"[{self.priorite}] {self.titre} ({statut})")
class TacheUrgente(Tache):
    def __init__(self, titre, deadline):
        super().__init__(titre, priorite="urgente")
        self.deadline = deadline
    def afficher(self):
        statut = "faite" if self.terminee else "à faire"
        print(f"[URGENT - deadline {self.deadline}] {self.titre} ({statut})")
taches = [Tache("Acheter du pain"), Tache("Reviser Python"),
TacheUrgente("Rendre le rapport", "demain 18h")]
for t in taches:
    t.afficher()