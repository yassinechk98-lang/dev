# Séance 16 (Jour 14 du plan) — Validation et gestion d'erreurs API

## Théorie — pourquoi valider les données ?

Actuellement, `creer_tache()` fait confiance aveuglément à ce qu'on lui envoie :
```python
data = request.get_json()
nouvelle_tache = {"id": prochain_id, "titre": data["titre"], "terminee": False}
```
Si quelqu'un envoie `{}` (sans `"titre"`), `data["titre"]` plante avec une erreur
`KeyError`, et Flask renvoie une page d'erreur brute peu claire (code `500` — erreur
serveur). Un vrai client de l'API (comme notre futur frontend React) a besoin d'un
message d'erreur clair pour savoir ce qui s'est mal passé, pas un plantage.

## Théorie — les codes de statut HTTP d'erreur courants

| Code | Signification | Exemple d'usage |
|---|---|---|
| `200` | OK | requête réussie (GET, DELETE...) |
| `201` | Créé | une nouvelle ressource a été créée (POST) |
| `400` | Bad Request | la requête du client est mal formée (titre manquant...) |
| `404` | Not Found | la ressource demandée n'existe pas (tâche id inconnu) |
| `500` | Internal Server Error | une erreur inattendue côté serveur (à éviter, prévenir avant) |

**Règle générale** : les erreurs `4xx` sont "la faute du client" (mauvaise requête),
les `5xx` sont "la faute du serveur". On vise à ne quasiment jamais renvoyer un `500`
en anticipant les cas d'erreur avec des `4xx` clairs.

## Théorie — valider et renvoyer une erreur propre

```python
@app.route("/taches", methods=["POST"])
def creer_tache():
    global prochain_id
    data = request.get_json()

    if not data or "titre" not in data or not data["titre"].strip():
        return jsonify({"erreur": "Le champ 'titre' est requis"}), 400

    nouvelle_tache = {"id": prochain_id, "titre": data["titre"], "terminee": False}
    taches.append(nouvelle_tache)
    prochain_id += 1
    sauvegarder_taches(taches)
    return jsonify(nouvelle_tache), 201
```

- `if not data` : si le client n'a envoyé aucun JSON du tout
- `"titre" not in data` : si le JSON existe mais n'a pas de clé `"titre"`
- `not data["titre"].strip()` : si `"titre"` existe mais est vide ou juste des espaces
- `jsonify({"erreur": "..."}), 400` : renvoie un JSON avec un message clair, et le
  code `400` pour dire au client "ta requête est invalide"

Pour `DELETE`, il faut vérifier que la tâche existe avant de dire "supprimé" :

```python
@app.route("/taches/<int:tache_id>", methods=["DELETE"])
def supprimer_tache(tache_id):
    global taches
    if not any(t["id"] == tache_id for t in taches):
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    taches = [t for t in taches if t["id"] != tache_id]
    sauvegarder_taches(taches)
    return "", 204
```

- `any(t["id"] == tache_id for t in taches)` : `True` si au moins une tâche a cet id
  (sinon `False`) — évite de dire "supprimé" pour quelque chose qui n'existait pas

## Exercice du jour

1. Modifie `creer_tache()` pour ajouter la validation du `titre` (code ci-dessus)
2. Modifie `supprimer_tache()` pour vérifier que l'id existe avant de supprimer
3. Lance le serveur, teste les cas d'erreur avec `curl` :
   ```
   curl -X POST http://localhost:5000/taches -H "Content-Type: application/json" -d '{}'
   curl -X DELETE http://localhost:5000/taches/999
   ```
   Les deux doivent renvoyer un message d'erreur clair (pas un plantage)
4. Vérifie aussi que le cas normal marche toujours (créer une vraie tâche, la
   supprimer)
5. Fais toi-même `git add` + `git commit` + `git push`

## À faire ensuite (séance suivante)

- Jour 15 : Tests de l'API, commit/push réguliers, récap de la semaine (dernier jour
  de la Semaine 3 !)
