# Règles de sécurité obligatoires

Ce fichier est la référence de sécurité du dépôt. Toute modification qui touche à un
formulaire, à la base de données, à l'authentification, à un webhook ou à un flux de
données vers un service externe doit respecter **toutes** les règles ci-dessous.
« OBLIGATOIRE » et « INTERDIT » ne souffrent aucune exception sans une note écrite
dans ce fichier qui explique pourquoi.

## Périmètre

| Partie | Technologies | Hébergement |
|---|---|---|
| `todo-app/backend/` | Flask 3, SQLAlchemy 2 (`text()`), PostgreSQL (Neon), PyJWT, Werkzeug, Mailjet, Web Push (VAPID), Gemini | Render (`https://dev-tpob.onrender.com`, gunicorn) |
| `todo-app/frontend/` | React 19, Vite, MUI, React Router, PWA (service worker Workbox) | Netlify |
| `site/` (branche `site-vitrine`) | Page HTML statique de FreeAV, sans formulaire | Netlify |
| `.github/workflows/` | Cron `check-reminders`, tests, déploiements | GitHub Actions |

Hors périmètre : `antivirus/` (application de bureau, ses règles sont dans
`antivirus/SECURITE.md`), `exercices/`, `seances/`.

---

## 0. Principes

- **P-1** Toute donnée venant de l'extérieur est non fiable : corps JSON, paramètres d'URL,
  en-têtes, fichiers importés, réponses de services tiers **et arguments produits par l'IA**.
- **P-2** La validation et l'autorisation se font **côté serveur**. Ce que fait le frontend
  (champs `required`, `RouteProtegee`) est du confort, jamais une protection.
- **P-3** Refuser par défaut : listes autorisées (allowlist), jamais listes interdites.
- **P-4** Le moindre privilège partout : routes, rôles de base de données, clés d'API.

## 1. Base de données (PostgreSQL via SQLAlchemy)

- **BD-1 INTERDIT** : le SQL brut construit avec une valeur par f-string, `+`, `%` ou
  `.format()`. OBLIGATOIRE : `text("... WHERE id = :id")` avec paramètres liés, ou
  SQLAlchemy Core/ORM.
- **BD-2** Un nom de table, de colonne ou un sens de tri ne peut pas être un paramètre lié :
  il doit venir d'une allowlist codée en dur (comme `TABLES_ADMIN`) et être vérifié
  (`if nom not in ALLOWLIST: 404`) **avant** d'être inséré dans la requête.
- **BD-3** Toute lecture, modification ou suppression d'une donnée d'utilisateur filtre par
  propriétaire **dans la même requête** (`WHERE id = :id AND user_id = :uid`). Une ressource
  d'un autre utilisateur répond 404, comme une ressource inexistante.
- **BD-4** `user_id` vient **uniquement** du JWT décodé, jamais du corps, de l'URL ou d'un en-tête.
- **BD-5** Colonnes explicites dans chaque `SELECT` (pas de `SELECT *`). `password_hash` ne
  sort jamais de la base ; l'email et les abonnements push d'un utilisateur ne sont
  renvoyés qu'à lui-même ou à l'admin.
- **BD-6** Une opération en plusieurs requêtes (import, tâche récurrente, partage) s'exécute
  dans **une seule transaction** (`with engine.begin() as conn:`).
- **BD-7** Les contraintes métier sont aussi en base : `NOT NULL`, `CHECK (priorite IN (...))`,
  longueurs maximales, `UNIQUE`, `ON DELETE CASCADE` sur les tables filles.
- **BD-8** `DATABASE_URL` vient uniquement des variables d'environnement, avec TLS
  (`sslmode=require` pour Neon).
- **BD-9 INTERDIT** : lancer les tests sur la base de production. La CI utilise une base dédiée
  (branche Neon de test ou service `postgres` dans GitHub Actions).
- **BD-10** Le code de démarrage ne contient que des changements de schéma additifs et
  idempotents (`IF NOT EXISTS`). Aucun `DROP`, `TRUNCATE` ou changement de type destructif
  sans sauvegarde préalable et validation humaine.
- **BD-11** Toute liste renvoyée par l'API a une limite (`LIMIT`) ou une pagination.

## 2. Validation des entrées (formulaires, JSON, fichiers)

- **VAL-1 OBLIGATOIRE** : chaque route qui lit `request.get_json()`, `request.args` ou un
  fichier valide la donnée avec un **schéma déclaratif strict** (Pydantic v2 recommandé,
  `model_config = ConfigDict(extra="forbid")`) **avant** toute logique. INTERDIT :
  `data["champ"]` sur le dict brut.
- **VAL-2** Le schéma fixe le type, la longueur et le format de chaque champ :
  - `username` : 3 à 32 caractères, `^[A-Za-z0-9_.-]+$`
  - `email` : format email valide (`EmailStr`), 254 caractères maximum, normalisé en minuscules
  - `password` : 12 à 128 caractères
  - `titre` (tâche, sous-tâche) : 1 à 200 caractères après `strip()`
  - `tags` : 10 au maximum, 1 à 30 caractères chacun
  - `recurrence`, `priorite` : `Literal[...]` des valeurs autorisées
  - dates : ISO 8601 parsées en `datetime`, sinon refus
  - identifiants : entiers strictement positifs
- **VAL-3** Une entrée invalide répond **400** avec la liste des champs en erreur. Une entrée
  invalide ne doit jamais provoquer une erreur 500.
- **VAL-4** Taille maximale des requêtes : `app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024`.
- **VAL-5** Toute liste reçue a une taille maximale : import 500 tâches et 50 sous-tâches par
  tâche, historique de l'assistant 20 messages et 20 Ko.
- **VAL-6** Les arguments des appels de fonction renvoyés par Gemini passent par **le même
  schéma** que les entrées HTTP équivalentes.
- **VAL-7 INTERDIT** : que le serveur appelle une URL fournie par un utilisateur sans contrôle
  (SSRF). L'`endpoint` d'un abonnement push doit être en `https://` et son hôte dans une
  allowlist des services push : `fcm.googleapis.com`, `updates.push.services.mozilla.com`,
  `*.notify.windows.com`, `web.push.apple.com`.
- **VAL-8** Les formulaires React reprennent les mêmes limites (`maxLength`, `type="email"`,
  `required`) pour le confort, sans jamais remplacer VAL-1.

## 3. Mots de passe et authentification

- **AUTH-1 OBLIGATOIRE** : hacher les mots de passe avec `werkzeug.security.generate_password_hash`
  (scrypt par défaut) ou argon2id. INTERDIT : stockage en clair, chiffrement réversible,
  MD5, SHA-1, SHA-256 sans sel ni facteur de coût, mot de passe dans un log ou un email.
- **AUTH-2** Vérifier uniquement avec `check_password_hash` (comparaison en temps constant).
- **AUTH-3** Politique de mot de passe côté serveur : 12 à 128 caractères, pas de règle de
  composition imposée, refus d'un mot de passe identique au nom d'utilisateur ou à l'email.
- **AUTH-4** Messages génériques : la connexion répond « Identifiants invalides » dans tous
  les cas ; « mot de passe oublié » répond le même message **et dans le même délai**, que
  l'email existe ou non (envoi de l'email hors de la requête).
- **AUTH-5 OBLIGATOIRE** : limiter le débit (Flask-Limiter) sur :
  - `/login` : 10 par minute par IP et 5 par minute par nom d'utilisateur
  - `/register` : 5 par heure par IP
  - `/forgot-password` : 3 par heure par IP et par email
  - `/reset-password` : 10 par heure par IP
  - `/assistant` : 20 par minute par utilisateur
- **AUTH-6** Le rôle administrateur est stocké en base (colonne `role` ou `is_admin`).
  INTERDIT : déduire un droit d'un nom d'utilisateur, qu'un inscrit pourrait revendiquer.
- **AUTH-7** Toute route porte `@token_requis` ou `@admin_requis`, sauf ces routes publiques :
  `/login`, `/register`, `/forgot-password`, `/reset-password`, `/vapid-public-key`, et
  `/check-reminders` (protégée par secret, voir section 7). Ajouter une route publique
  impose de l'ajouter à cette liste avec sa justification.
- **AUTH-8** `debug=True` est INTERDIT en production. Render lance `gunicorn app:app` ; le
  mode debug ne s'active que si une variable d'environnement de développement le demande.

## 4. Tokens JWT et sessions

- **JWT-1** Décoder toujours avec `algorithms=["HS256"]` explicite et
  `options={"require": ["exp", "iat", "type"]}`. INTERDIT : `algorithms` absent, `"none"`,
  `verify_signature=False`.
- **JWT-2** `SECRET_KEY` : au moins 32 octets aléatoires
  (`python -c "import secrets; print(secrets.token_urlsafe(64))"`), uniquement dans les
  variables d'environnement (Render, secrets GitHub), différente entre production et tests.
  En cas de fuite : rotation immédiate (toutes les sessions sont alors invalidées).
- **JWT-3 OBLIGATOIRE** : chaque token porte un claim `type` (`"access"`, `"reset"`) et chaque
  décodeur **vérifie le type attendu**. Un token de réinitialisation ne doit jamais ouvrir
  une session, et inversement.
- **JWT-4** Durées maximales : token de session 24 heures ; token de réinitialisation
  30 minutes. Pour des sessions plus longues, un refresh token rotatif stocké haché en base.
- **JWT-5** Révocation : une colonne `token_version` dans `users`, copiée dans le JWT et
  vérifiée par `token_requis`. Elle est incrémentée à chaque changement ou réinitialisation
  du mot de passe, ce qui invalide les anciennes sessions **et rend le lien de
  réinitialisation à usage unique**.
- **JWT-6** Tant que le token est stocké dans `localStorage`, toute faille XSS permet de le
  voler : les règles FE-1 et HDR-1 sont donc obligatoires. Cible à terme : cookie
  `HttpOnly; Secure; SameSite`, ce qui suppose que l'API et le frontend partagent un même
  domaine et qu'une protection CSRF soit ajoutée.
- **JWT-7** Un token n'apparaît jamais dans un log ni dans une URL, sauf le lien de
  réinitialisation. La page de réinitialisation retire le token de la barre d'adresse dès
  sa lecture (`window.history.replaceState`).

## 5. CORS et en-têtes HTTP

- **CORS-1 INTERDIT** : `CORS(app)` sans restriction ou `origins="*"`. OBLIGATOIRE :
  ```python
  CORS(app, origins=[FRONTEND_URL], methods=["GET", "POST", "PUT", "DELETE"],
       allow_headers=["Content-Type", "Authorization"], supports_credentials=False, max_age=600)
  ```
  `http://localhost:5173` n'est ajouté que si une variable d'environnement de développement le
  demande.
- **CORS-2** Les routes appelées par des machines (`/check-reminders`, futurs webhooks) n'ont
  pas besoin de CORS.
- **HDR-1 OBLIGATOIRE** sur les deux sites Netlify, via un fichier `_headers` dans le dossier
  publié (`todo-app/frontend/public/_headers`, `site/_headers`) :
  ```
  /*
    Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://dev-tpob.onrender.com; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
    Strict-Transport-Security: max-age=31536000; includeSubDomains
    X-Content-Type-Options: nosniff
    X-Frame-Options: DENY
    Referrer-Policy: no-referrer
    Permissions-Policy: camera=(), microphone=(), geolocation=()
  ```
  `style-src 'unsafe-inline'` est toléré à cause de MUI/Emotion. Un script inline (comme dans
  `site/index.html`) doit être déplacé dans un fichier `.js` ou autorisé par son empreinte
  `'sha256-...'`, jamais par `'unsafe-inline'`.
- **HDR-2** L'API Flask ajoute dans `@app.after_request` : `X-Content-Type-Options: nosniff`,
  `Cache-Control: no-store` sur les réponses authentifiées, et HSTS.
- **HDR-3** HTTPS partout. Aucune URL `http://` vers l'API ou un service tiers.

## 6. Flux de données, secrets et services tiers

- **SEC-1 INTERDIT** : un secret dans le code, dans `todo-app/frontend/` (tout le bundle est
  public, y compris les `import.meta.env.VITE_*`), dans un log, un message d'erreur ou une
  URL. Seules valeurs publiques côté frontend : l'URL de l'API et la clé VAPID publique.
- **SEC-2** Les secrets vivent dans : variables d'environnement Render, secrets GitHub Actions,
  `.env` local (ignoré par git). Toute fuite entraîne une rotation de la clé concernée.
- **SEC-3** Les clés d'API passent dans un en-tête, jamais dans la query string. Gemini :
  en-tête `x-goog-api-key`.
- **SEC-4** Tout appel sortant (`requests`, `webpush`) a un `timeout`, utilise HTTPS et vise
  un hôte connu (Mailjet, Gemini, services push de VAL-7).
- **SEC-5** Erreurs : le client reçoit un message générique ; le détail va dans les logs
  serveur, sans secret ni donnée personnelle. INTERDIT : renvoyer au client le texte brut
  d'une réponse d'un service tiers.
- **SEC-6** Emails : toute donnée dynamique insérée dans le HTML est échappée
  (`markupsafe.escape`) ; les liens sont construits à partir de `FRONTEND_URL`, jamais de
  l'en-tête `Host` de la requête.
- **SEC-7** Assistant IA : l'historique envoyé par le client est non fiable (rôles limités à
  `user` et `model`, taille limitée par VAL-5) ; les fonctions exposées à l'IA agissent
  toujours avec le `user_id` du JWT ; aucune fonction d'administration n'est exposée à l'IA.
- **SEC-8** Dépendances : versions épinglées (`requirements.txt`, `package-lock.json` avec
  `npm ci`). Dependabot couvre `/todo-app/backend` (pip) et `/todo-app/frontend` (npm).
  `pip-audit` et `npm audit --omit=dev` tournent en CI.
- **SEC-9** Données personnelles : ne collecter que le nécessaire (nom d'utilisateur, email,
  abonnements push) ; la suppression d'un compte supprime toutes ses données.

## 7. Webhooks et routes appelées par des machines

Aujourd'hui : `/check-reminders`, appelée toutes les 15 minutes par GitHub Actions avec
l'en-tête `X-Cron-Secret`.

- **WH-1 OBLIGATOIRE** : authentifier chaque appel. Secret partagé : au moins 32 octets
  aléatoires, envoyé dans un en-tête, comparé avec `hmac.compare_digest` (temps constant).
  INTERDIT : comparer un secret avec `==` ou `!=`.
- **WH-2** Webhook d'un service tiers (paiement, GitHub, Mailjet...) : vérifier la **signature
  HMAC du corps brut** (`request.get_data()`) avec la méthode officielle du fournisseur,
  **avant** de parser le JSON.
- **WH-3** Anti-rejeu : refuser un horodatage de plus de 5 minutes et enregistrer
  l'identifiant d'événement pour ne jamais le traiter deux fois (idempotence).
- **WH-4** `POST` uniquement, pas de CORS, réponse minimale sans donnée d'utilisateur.
- **WH-5** Le traitement est borné (lots avec `LIMIT`) pour qu'un appel ne puisse pas
  saturer le serveur ou la base.

## 8. Frontend React et site vitrine

- **FE-1 INTERDIT** : `dangerouslySetInnerHTML`, `innerHTML`, `outerHTML`, `document.write`,
  `eval`, `new Function` avec une donnée dynamique. L'affichage passe par `{valeur}` de React,
  qui échappe le HTML.
- **FE-2** Un lien construit à partir d'une donnée n'accepte que `https:` ou `mailto:`
  (jamais `javascript:`). Tout `target="_blank"` porte `rel="noopener noreferrer"`.
- **FE-3** Aucun script ou style chargé depuis un CDN sans attribut `integrity` (SRI).
- **FE-4** Le service worker ne met jamais en cache les réponses authentifiées de l'API ;
  `notificationclick` n'ouvre que des chemins du même site.

---

## Checklist avant chaque modification

À vérifier (et à copier dans la description de la PR) pour tout changement qui touche un
formulaire, la base, l'authentification ou un webhook :

- [ ] Les entrées sont validées par un schéma strict (VAL-1, VAL-2, VAL-6)
- [ ] Les requêtes SQL sont paramétrées ; les identifiants viennent d'une allowlist (BD-1, BD-2)
- [ ] Chaque accès est filtré par propriétaire, `user_id` vient du JWT (BD-3, BD-4)
- [ ] La route a un décorateur d'authentification, ou figure dans la liste publique (AUTH-7)
- [ ] Les tokens sont vérifiés avec algorithme, expiration et type (JWT-1, JWT-3)
- [ ] Aucun secret dans le code, le frontend, les logs ou les URLs (SEC-1, SEC-3)
- [ ] Les erreurs renvoyées sont génériques (SEC-5)
- [ ] Les routes sensibles ont une limite de débit (AUTH-5)
- [ ] Au moins un test négatif par nouvelle route : sans token, avec la ressource d'un autre
      utilisateur, avec une entrée invalide
- [ ] Ce fichier est mis à jour si une route publique, un service tiers ou un webhook est ajouté

---

## Annexe : écarts relevés dans le code le 11 octobre 2026

Constat de l'analyse initiale. Cocher chaque ligne une fois corrigée.

**Priorité haute**

- [ ] **JWT-3** `token_requis` ne vérifie pas le claim `type` : le token du lien de
      réinitialisation (30 minutes) est accepté comme token de session par toute l'API.
      `todo-app/backend/app.py:145`
- [ ] **VAL-7** L'`endpoint` d'un abonnement push n'est pas contrôlé : un utilisateur peut faire
      envoyer par le serveur des requêtes `POST` vers n'importe quelle URL (SSRF), à chaque
      rappel. `todo-app/backend/app.py:837-858` et `app.py:885`
- [ ] **AUTH-5** Aucune limite de débit : essais de mots de passe illimités sur `/login`,
      envoi d'emails illimité via `/forgot-password`, appels Gemini illimités via `/assistant`.
- [ ] **BD-9** Les tests backend tournent avec le secret `DATABASE_URL` et créent de vrais
      comptes à chaque exécution. Si ce secret pointe vers la base de production (probable,
      à vérifier), les tests écrivent en production. `.github/workflows/backend-tests.yml:23-25`
- [ ] **CORS-1** `CORS(app)` autorise toutes les origines. `todo-app/backend/app.py:21`

**Priorité moyenne**

- [ ] **AUTH-6** L'admin est reconnu par son nom (`ADMIN_USERNAME`) : si ce compte n'existe pas
      ou est supprimé, n'importe qui peut s'inscrire sous ce nom et devenir admin.
      `todo-app/backend/app.py:165`
- [ ] **AUTH-3** Aucune politique de mot de passe (un seul caractère est accepté).
      `todo-app/backend/app.py:173`
- [ ] **JWT-4, JWT-5** Sessions de 7 jours sans révocation : changer son mot de passe ou se
      déconnecter n'invalide pas les tokens existants, et le lien de réinitialisation reste
      réutilisable pendant 30 minutes. `todo-app/backend/app.py:104`, `app.py:231-236`
- [ ] **VAL-1, VAL-3** Validation manuelle : un `titre` non textuel, des `keys` push absentes ou
      une date mal formée provoquent une erreur 500 ; aucune longueur maximale ; pas de format
      d'email vérifié. `todo-app/backend/app.py:173`, `app.py:350`, `app.py:366`, `app.py:855`
- [ ] **VAL-4, VAL-5** Pas de `MAX_CONTENT_LENGTH` ; l'historique de l'assistant n'a pas de
      limite de taille. `todo-app/backend/app.py:786`
- [ ] **SEC-3, SEC-5** Clé Gemini dans l'URL, et texte brut de l'erreur Gemini renvoyé au
      client. `todo-app/backend/app.py:799`, `app.py:808`
- [ ] **WH-1** `CRON_SECRET` comparé avec `!=`. `todo-app/backend/app.py:906`
- [ ] **HDR-1, JWT-6** Aucun en-tête de sécurité sur les deux sites Netlify (pas de `_headers`
      ni de `netlify.toml`) alors que le token est dans `localStorage`.
      `todo-app/frontend/public/`, `todo-app/frontend/src/App.jsx:26`
- [ ] **JWT-7** Le token de réinitialisation reste dans la barre d'adresse.
      `todo-app/frontend/src/pages/ResetPasswordPage.jsx:10`

**Priorité basse**

- [ ] **VAL-6** Les arguments de fonction renvoyés par Gemini ne sont pas validés avant
      d'écrire en base. `todo-app/backend/app.py:767`
- [ ] **SEC-8** Dependabot ne surveille que `/antivirus` ; `todo-app/backend` et
      `todo-app/frontend` ne sont pas couverts. `.github/dependabot.yml`
- [ ] **AUTH-4** `/forgot-password` envoie l'email pendant la requête : le délai de réponse
      révèle si l'email est inscrit. `todo-app/backend/app.py:207-214`
- [ ] **AUTH-8** `app.run(debug=True)` en dur (sans effet sur Render, qui lance gunicorn).
      `todo-app/backend/app.py:976`

Points déjà conformes : requêtes SQL paramétrées partout, noms de tables admin issus d'une
allowlist, filtrage par `user_id` sur les tâches, sous-tâches et partages, hachage Werkzeug (scrypt),
`algorithms=["HS256"]` imposé au décodage, messages génériques sur la connexion et le mot de
passe oublié, `timeout` sur les appels sortants, `.env` ignoré par git.
