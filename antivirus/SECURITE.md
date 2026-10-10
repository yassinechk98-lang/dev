# Vie privee et securite de FreeAV

## Ce que FreeAV garantit pour vos donnees

- **Rien ne quitte votre ordinateur pendant une analyse.** Le scan lit vos fichiers localement et ne
  fait aucune connexion reseau (verifie par le test `test_scan_never_uses_the_network`). Pas de
  telemetrie, pas de compte, pas d'envoi de fichiers "dans le cloud".
- **Le reseau ne sert qu'a la mise a jour, et seulement quand vous la lancez** (`freeav update` ou le
  bouton de l'interface). Elle telecharge des empreintes publiques et n'envoie rien sur vous.
- **La cle abuse.ch ne sert qu'a abuse.ch** : elle est envoyee uniquement a `mb-api.abuse.ch`
  (dans l'adresse de l'export, comme l'exige leur documentation), en HTTPS, et n'apparait jamais
  dans les messages d'erreur.
- **Mises a jour protegees contre la falsification** : HTTPS obligatoire avec verification du
  certificat (une redirection vers `http://` est refusee), taille limitee, chaque ligne verifiee (une ligne inattendue fait tout refuser),
  ecriture atomique (une mise a jour ratee laisse l'ancienne base intacte).
- **ClamAV reste local** : FreeAV refuse par defaut d'envoyer vos fichiers a un demon `clamd` situe
  sur une autre machine (option explicite `--allow-remote-clamd` sinon).
- **Donnees privees sur le disque** : `~/.freeav` (quarantaine, signatures, cle abuse.ch) est en mode
  `0700` et ses fichiers en `0600` : les autres comptes de l'ordinateur ne peuvent pas les lire.
- **La quarantaine ne peut pas etre detournee contre vos fichiers** :
  - elle refuse les liens symboliques (un piege pointant vers vos photos ne les deplacera pas) ;
  - une restauration n'ecrase jamais un fichier existant et ne suit pas de lien symbolique ;
  - un enregistrement modifie a la main ne peut pas ecrire vers un chemin relatif ou deja occupe ;
  - un fichier qui a change entre l'analyse et la mise en quarantaine est laisse en place ;
  - si l'original ne peut pas etre supprime (fichier verrouille), la copie est retiree : la
    quarantaine ne pretend jamais contenir un fichier qui est encore la ;
  - les detections YARA, moins sures, ne sont jamais mises en quarantaine automatiquement.
- **L'analyse ne peut pas etre bloquee** par un tube nomme ou un fichier special place par un
  malware : seuls les fichiers ordinaires sont lus, et une erreur sur un fichier n'arrete pas le scan.
- **FreeAV n'analyse pas ses propres donnees** (`~/.freeav`, regles YARA), qui contiennent
  forcement des motifs de malwares.

## Securite du code (GitHub)

- **CodeQL** analyse le code a chaque PR et chaque semaine (`.github/workflows/codeql.yml`).
- **Dependabot** propose les mises a jour de securite des dependances et des actions GitHub.
- Les workflows n'ont que les droits en lecture dont ils ont besoin.

## Limites (a lire)

Aucun logiciel ne peut proteger contre toutes les cyberattaques. FreeAV detecte les fichiers deja
connus (empreintes, regles YARA, ClamAV) : un malware tout nouveau ou cible peut passer. Il n'a pas
encore de protection en temps reel, et il ne protege pas contre le phishing, les mots de passe voles
ou les failles du systeme. Gardez votre systeme a jour, faites des sauvegardes hors ligne et activez
la double authentification sur vos comptes.

## Signaler une faille

Ouvrez une alerte privee via l'onglet **Security > Report a vulnerability** du depot GitHub plutot
qu'une issue publique.
