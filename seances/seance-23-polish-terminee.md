# Séance 23 (Jours 21-22 du plan) — Polish : marquer une tâche terminée + tests manuels

Rappel du tableau CRUD (Jour 12) : il manquait `PUT` (Update). C'est la dernière
pièce naturelle pour un Todo-list complet — pouvoir cocher une tâche comme faite.

## Backend — route PUT

```python
@app.route("/taches/<int:tache_id>", methods=["PUT"])
def modifier_tache(tache_id):
    tache = next((t for t in taches if t["id"] == tache_id), None)
    if tache is None:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    tache["terminee"] = not tache["terminee"]
    sauvegarder_taches(taches)
    return jsonify(tache)
```

- `next((t for t in taches if t["id"] == tache_id), None)` : trouve la première
  tâche avec cet id, ou `None` si aucune ne correspond — équivalent compact d'une
  boucle avec `break`
- `tache["terminee"] = not tache["terminee"]` : inverse le statut (bascule)

## Frontend — cliquer pour basculer

```jsx
const basculerTache = (id) => {
  fetch(`${API_URL}/${id}`, { method: "PUT" })
    .then((reponse) => reponse.json())
    .then((tacheMaj) => {
      setTaches(taches.map((t) => (t.id === id ? tacheMaj : t)));
    });
};
```

- `taches.map((t) => (t.id === id ? tacheMaj : t))` : reconstruit le tableau en
  remplaçant **seulement** la tâche modifiée par sa version à jour, les autres
  restent inchangées — pattern très courant en React pour mettre à jour un élément
  d'une liste dans le state

Dans le JSX, rendre le texte cliquable (au lieu d'un simple span) :
```jsx
<span onClick={() => basculerTache(tache.id)} style={{ cursor: "pointer" }}>
  {tache.titre} {tache.terminee ? "✅" : "❌"}
</span>
```

## Checklist de tests manuels (bout en bout)

Lance backend + frontend, puis dans le navigateur, vérifie un par un :
- [ ] La liste des tâches se charge au démarrage
- [ ] Ajouter une tâche l'affiche immédiatement dans la liste
- [ ] Cliquer sur une tâche bascule ✅ ↔ ❌
- [ ] Supprimer une tâche la fait disparaître
- [ ] Recharger la page (F5) : tout l'état est conservé (persistance JSON)
- [ ] Éteindre le backend, recharger : message d'erreur clair affiché
- [ ] Rallumer le backend, recharger : ça remarche

## Exercice

1. Ajoute la route `PUT` au backend
2. Ajoute `basculerTache` et rends le texte cliquable au frontend
3. Passe la checklist ci-dessus en entier
4. Fais toi-même `git add` + `git commit` + `git push`

## Bilan (Jour 23)

Le projet Todo-list est fonctionnellement complet : CRUD entier (Create, Read,
Update, Delete), persistance, validation, tests automatisés (pytest), interface React
connectée en temps réel. Tu es passé de "Git n'était pas installé" à une application
full-stack qui tourne, en 23 jours. La suite logique (hors plan) serait : SQLite à la
place du JSON, déploiement en ligne, authentification — à voir selon ton envie.
