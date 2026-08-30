# Séance 13 (Jour 11 du plan) — HTTP/REST, Flask, Hello World API

Début de la Semaine 3 — le vrai projet Todo-list commence : le backend.

## Théorie — c'est quoi une API / HTTP ?

Jusqu'ici, tes scripts Python s'exécutaient et affichaient un résultat dans le
terminal, puis se terminaient. Une **API web** est différente : c'est un programme qui
**reste allumé en permanence**, à l'écoute, et qui répond quand quelqu'un lui envoie
une requête (par exemple depuis un navigateur, ou plus tard depuis notre interface
React).

**HTTP** est le "langage" utilisé pour ces échanges sur le web. Chaque requête a :
- une **méthode** : ce qu'on veut faire
  - `GET` = récupérer des données ("donne-moi la liste des tâches")
  - `POST` = créer quelque chose ("ajoute cette nouvelle tâche")
  - `PUT`/`PATCH` = modifier quelque chose existant
  - `DELETE` = supprimer quelque chose
- une **URL** : sur quoi on agit (ex: `/taches`, `/taches/3`)
- parfois des **données** envoyées (ex: le titre de la nouvelle tâche à créer)

Une API **REST** est juste une API qui organise ses URLs autour de "ressources" (ici :
les tâches) de façon prévisible — `GET /taches` pour lister, `POST /taches` pour
créer, etc. On construira ça en détail au Jour 12.

## Théorie — Flask

**Flask** est une bibliothèque Python qui permet de créer une API web très simplement.

```python
from flask import Flask

app = Flask(__name__)

@app.route("/")
def accueil():
    return "Hello World !"

if __name__ == "__main__":
    app.run(debug=True)
```

- `app = Flask(__name__)` crée l'application
- `@app.route("/")` est un **décorateur** : il dit "quand quelqu'un visite l'URL `/`,
  exécute la fonction juste en dessous"
- La fonction retourne ce qui doit être affiché/renvoyé au visiteur
- `app.run(debug=True)` démarre le serveur (le "allumage permanent" dont on parlait) ;
  `debug=True` redémarre automatiquement le serveur à chaque modification du code, très
  utile pendant le développement

Une fois lancé, le serveur tourne en général sur `http://127.0.0.1:5000` (ta propre
machine, port 5000) — tu ouvres cette adresse dans ton navigateur pour voir le
résultat, ou tu la testes avec `curl`.

## Exercice du jour

1. Installe Flask (venv activé) : `pip install flask`
2. Crée le dossier `dev/todo-app/backend/` (nouveau dossier, en dehors de `exercices/`
   — c'est ici que vivra tout le code du projet final)
3. Crée `dev/todo-app/backend/app.py` avec le code Flask ci-dessus
4. Ajoute une deuxième route `/taches` qui renvoie simplement le texte
   `"Liste des taches (bientot)"`
5. Lance le serveur : `python todo-app/backend/app.py`
6. Ouvre `http://127.0.0.1:5000/` dans ton navigateur → tu dois voir "Hello World !"
7. Ouvre `http://127.0.0.1:5000/taches` → tu dois voir le texte de l'étape 4
8. Arrête le serveur avec **Ctrl+C** dans le terminal
9. Fais toi-même `git add` + `git commit` + `git push`

## À faire ensuite (séance suivante)

- Jour 12 : Endpoints CRUD (GET/POST/DELETE) pour les tâches, en mémoire
