with open("exercices/notes.txt", "w") as f:
    f.write("Maths: 15\n")
    f.write("Francais:12\n")
    f.write("Anglais:17\n")
with open("exercices/notes.txt", "r") as f:
     for ligne in f:
        print(ligne.strip())
try:
    with open("exercices/fichier_inexistant.txt", "r") as f:
        print(f.read())
except FileNotFoundError:
    print("Le fichier n'existe pas")