# Séance 33 (bonus, hors plan initial) — Débogage : Render bloqué

## Le symptôme

Après plusieurs commits (Mailjet, date d'échéance, PWA...), le backend en ligne sur
Render continuait à se comporter comme une **très ancienne version** du code, alors
que GitHub Actions (tests + déploiement frontend) passait au vert à chaque fois.

## La cause racine

En supprimant deux anciennes variables d'environnement devenues inutiles
(`GMAIL_USER`, `GMAIL_APP_PASSWORD`) sur Render, la variable `SECRET_KEY` a été
supprimée par erreur en même temps. Résultat : chaque nouveau déploiement plantait
immédiatement au démarrage avec `KeyError: 'SECRET_KEY'` (le code fait
`os.environ["SECRET_KEY"]`, qui lève une erreur si la clé n'existe pas).

Render, quand un déploiement échoue, **continue de servir la dernière version qui
fonctionnait** plutôt que de couper le service — ce qui a caché le problème pendant
longtemps : le site avait l'air "en ligne et fonctionnel", juste figé sur une version
plusieurs jours en arrière.

## Méthode de diagnostic utilisée

1. Comparer le comportement de l'API en ligne avec le code sur GitHub (une
   fonctionnalité récente absente = suspicion de déploiement bloqué)
2. Vérifier l'onglet **Events** de Render : historique des déploiements
   réussis/échoués, avec le commit exact de la dernière version "Live"
3. Chercher `Traceback` dans les **Logs** Render pour trouver la vraie erreur Python
4. Ajouter temporairement une route `/version` qui renvoie un marqueur unique,
   pour vérifier à coup sûr (sans ambiguïté) si le nouveau code tourne réellement

## Leçon

- Toujours vérifier deux fois avant de supprimer une variable d'environnement —
  une suppression accidentelle peut casser le démarrage sans message d'erreur
  visible côté utilisateur (le site continue de "marcher", juste sur du code
  périmé)
- Un `KeyError` sur une variable d'environnement manquante est silencieux du point
  de vue de l'utilisateur final, mais fatal côté serveur — d'où l'intérêt de garder
  une trace des variables nécessaires (ex: dans ce dossier `seances/`)
- Face à un comportement "figé"/incohérent après un déploiement, une route de debug
  temporaire (marqueur de version) est le moyen le plus fiable de confirmer si le
  nouveau code tourne vraiment, sans ambiguïté possible
