# Séance 34 (bonus, hors plan initial) — Notifications push + refonte Material UI

## Refonte interface (Material UI v6)

Toute l'interface (LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage,
TodosPage) a ete reconstruite avec `@mui/material` v6 : theme clair/sombre (bascule
persistee dans `localStorage`), champs/boutons/cartes Material Design, onglets de
filtre (Toutes/A faire/Terminees), dialogue de confirmation avant suppression,
notifications "Snackbar" pour les actions, squelettes de chargement.

Les taches ont aussi gagne une **heure** en plus de la date (`datetime-local` cote
formulaire, colonne PostgreSQL passee de `DATE` a `TIMESTAMP`).

## Notifications push — theorie

Une notification push web fonctionne en trois temps :

1. **Abonnement** : le navigateur genere un "abonnement" unique (URL + cles de
   chiffrement) via `PushManager`, qu'on envoie au serveur
2. **Envoi** : le serveur chiffre un message et l'envoie a cette URL via le
   protocole Web Push (bibliotheque `pywebpush` cote Python)
3. **Reception** : meme navigateur ferme, le systeme d'exploitation reveille le
   **service worker** de la PWA, qui affiche la notification

Une paire de cles **VAPID** (asymetriques) identifie le serveur aupres des
navigateurs — generees une fois, jamais renouvelees.

## Le declencheur : gratuit, via GitHub Actions

Pour verifier regulierement quelles taches sont en retard et envoyer les rappels,
il faut un processus qui tourne **peu importe si quelqu'un a l'app ouverte**. Render
gratuit n'offre pas de vraie tache planifiee (cron) gratuite — solution : un
**workflow GitHub Actions planifie** (`.github/workflows/check-reminders.yml`,
`cron: "*/15 * * * *"`, gratuit sur un depot public) qui appelle toutes les 15
minutes une route protegee `/check-reminders` sur le backend.

## Exercice

Deja implemente par l'assistant vu la complexite (cles VAPID, nouvelle table
`push_subscriptions`, service worker personnalise). Reste a tester : activer les
notifications depuis l'app, creer une tache avec une echeance dans le passe, attendre
le prochain declenchement du workflow GitHub Actions (jusqu'a 15 minutes), verifier
la reception de la notification.
