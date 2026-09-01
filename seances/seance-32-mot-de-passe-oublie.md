# Séance 32 (bonus, hors plan initial) — Mot de passe oublié (email)

Note : apres blocage sur Gmail SMTP (bloque par Render) et Brevo/Resend
(verification telephone), migre vers l'API Mailjet (HTTP, sans SMTP).

## Théorie — le flux "mot de passe oublié"

1. L'utilisateur indique son email sur une page dédiée
2. Le serveur génère un **lien de réinitialisation** contenant un jeton temporaire
   (valable 30 minutes), et l'envoie par email
3. L'utilisateur clique sur le lien, arrive sur une page où il choisit un nouveau
   mot de passe
4. Le serveur vérifie le jeton (valide ? pas expiré ?) et met à jour le mot de passe

Le jeton est un JWT, comme celui de connexion (Séance 27), mais avec un rôle
différent (`type: "reset"`) et une durée de vie courte — s'il est intercepté, la
fenêtre d'exploitation est limitée.

## Théorie — envoyer un email depuis Flask (Brevo)

Un serveur ne peut pas "juste" envoyer un email comme un client Gmail — il faut un
service dédié (**Brevo**, ex-Sendinblue) qui gère la délivrabilité (éviter les
spams, etc.) via une simple requête API :

```python
import requests

def envoyer_email(destinataire, sujet, html):
    requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json={
            "sender": {"email": MAIL_FROM},
            "to": [{"email": destinataire}],
            "subject": sujet,
            "htmlContent": html,
        },
    )
```

- `requests.post(...)` : envoie une requête HTTP à l'API de Brevo, comme un `fetch`
  côté Python
- Le `sender.email` doit être une adresse **vérifiée** dans le compte Brevo (par
  défaut, l'email utilisé à l'inscription du compte)

## Sécurité importante

La réponse de `/forgot-password` est **identique** que l'email existe en base ou
non ("Si ce compte existe, un email a été envoyé"). Sinon, on révèle quels emails
sont enregistrés — une faille classique.

## Exercice

**Backend**
1. Ajouter une colonne `email` à `users` (inscription mise à jour pour la demander)
2. Créer un compte Brevo, récupérer une clé API
3. Route `POST /forgot-password` : génère un token JWT court, envoie l'email
4. Route `POST /reset-password` : vérifie le token, met à jour le mot de passe

**Frontend**
5. `RegisterPage` : ajouter le champ email
6. `LoginPage` : lien "Mot de passe oublié ?"
7. Nouvelle page `ForgotPasswordPage` : formulaire email
8. Nouvelle page `ResetPasswordPage` : lit le token dans l'URL, formulaire nouveau
   mot de passe

**Test**
9. Inscription avec email → demande de reset → vérifier réception de l'email →
   cliquer le lien → nouveau mot de passe → connexion avec le nouveau mot de passe
