# Vie privee et securite de FreeAV

## Ce que FreeAV garantit pour vos donnees

- **Rien ne quitte votre ordinateur pendant une analyse.** Le scan lit vos fichiers localement et ne
  fait aucune connexion reseau (verifie par le test `test_scan_never_uses_the_network`). Pas de
  telemetrie, pas de compte, pas d'envoi de fichiers "dans le cloud". Seule exception, si vous
  laissez coche le deuxieme avis Microsoft Defender : Defender applique ses propres reglages
  (protection dans le cloud, envoi d'echantillons), les memes que pour sa protection habituelle.
- **Le reseau ne sert qu'a la mise a jour** : quand vous la lancez (`freeav update` ou le bouton de
  l'interface), ou chaque jour si vous avez active la protection automatique et enregistre une cle
  abuse.ch. Elle telecharge des empreintes publiques et n'envoie rien sur vous. La protection en
  temps reel n'utilise pas le reseau.
- **Verification des nouvelles versions de FreeAV** : a chaque ouverture de FreeAV et dans
  l'entretien quotidien, FreeAV lit un petit fichier public sur github.com. Rien n'est envoye sur
  vous, mais GitHub voit, comme pour toute page web, votre adresse IP et l'heure. Vous pouvez la
  couper (case « Chercher les nouvelles versions » ou `FreeAV.exe app-update --auto-check off`) ;
  la mise a jour reste alors possible a la main.
- **La protection automatique reste chez vous et se retire en un clic** : une tache planifiee
  "FreeAV\\Analyse quotidienne" et une entree "FreeAV" au demarrage de votre session, sans droits
  administrateur, avec une copie de FreeAV dans `%LOCALAPPDATA%\FreeAV`. Le journal
  `~/.freeav/logs/auto.log` n'est lisible que par vous.
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

- **Reparer mon PC ne touche a rien sans votre accord** : le diagnostic est en lecture seule,
  chaque reparation est choisie par vous, sauvegardee et annulable (sauf nettoyage et outils
  Windows, annonces comme definitifs), et le nettoyage refuse tout dossier qui n'est pas temporaire.
- **Un faux journal ne peut rien faire executer** : "Annuler" ne rejoue que les actions inverses
  prevues (registre, fichier sauvegarde, ligne du fichier hosts, tache), jamais une commande, et
  seulement sur les cles de registre que FreeAV repare. Un journal douteux est refuse en entier.
  En administrateur, les sauvegardes vont dans `%ProgramData%\FreeAV`, verrouille pour les seuls
  administrateurs ; un dossier de ce nom cree par quelqu'un d'autre est mis de cote.
- **Le nettoyage ne sort jamais du dossier temporaire** : il n'entre ni dans un lien symbolique ni
  dans une jonction Windows, et verifie le chemin reel de chaque fichier juste avant de le supprimer
  (teste avec une vraie jonction sur Windows).
- **En administrateur, la quarantaine ne restaure que dans votre dossier personnel** : elle est
  modifiable sans droits, une fausse fiche ne doit pas pouvoir ecrire dans `C:\Windows`.
- **En administrateur, ClamAV integre n'est pas lance** : il est installe dans
  `%LOCALAPPDATA%\FreeAV\ClamAV`, modifiable sans droits. Microsoft Defender est alors cherche dans
  les dossiers systeme donnes par Windows, pas dans des variables d'environnement.
- **Limite** : FreeAV installe pour l'utilisateur (sans droits) puis lance en administrateur reste
  expose a un programme malveillant deja actif sous le meme compte, qui aurait pu remplacer
  `FreeAV.exe` lui-meme. Lancez FreeAV normalement, sauf pour une reparation qui le demande.

## Securite du code (GitHub)

- **CodeQL** analyse le code a chaque PR et chaque semaine (`.github/workflows/codeql.yml`).
- **Moteurs externes** : ClamAV integre analyse sur le PC (clamscan) et ne se met a jour qu'aupres
  du miroir officiel `database.clamav.net` ; son paquet vient de la release officielle de Cisco Talos
  (`github.com/Cisco-Talos/clamav`) et il est refuse si son empreinte SHA-256 ne
  correspond pas a celle inscrite dans FreeAV.exe, et son archive ne peut rien ecrire hors de son
  dossier. Microsoft Defender est lance avec `-DisableRemediation` et suit ses propres reglages de
  confidentialite, deja actifs sur le PC.
- **Mises a jour de FreeAV lui-meme** : seulement si vous les acceptez. FreeAV lit `FreeAV.json` dans
  la pre-release GitHub de sa version (HTTPS, github.com et ses serveurs de fichiers uniquement,
  redirections comprises), n'accepte qu'une version plus recente, pour son propre canal, et refuse le
  fichier si son empreinte SHA-256 ou sa taille ne correspondent pas, ou si ce n'est pas un programme
  Windows. L'ancienne version est remise en place si le remplacement echoue. En administrateur,
  la protection en temps reel n'est pas relancee (elle tournerait avec ces droits sur des dossiers
  modifiables sans droits) : la nouvelle version prend le relais a la prochaine session. Limite : l'empreinte vient
  de la meme page GitHub que le programme ; FreeAV fait donc confiance au compte GitHub du projet,
  comme pour le telechargement direct (FreeAV.exe n'est pas signe).
- **Outils de construction figes avec leurs empreintes** : la CI installe `requirements-build.txt`
  avec `pip --require-hashes` (versions choisies dans `requirements-build.in`, y compris yara-python
  et pytest), et les actions GitHub des workflows FreeAV sont figees par commit.
- **Publication seulement depuis main** : les autres branches et les lancements manuels ne
  produisent qu'un artefact de construction. Si Microsoft Defender signale FreeAV.exe, la
  publication est bloquee.
- **Dependabot** propose les mises a jour de securite des dependances et des actions GitHub.
- Les workflows n'ont que les droits en lecture dont ils ont besoin.

## Limites (a lire)

Aucun logiciel ne peut proteger contre toutes les cyberattaques. FreeAV detecte les fichiers deja
connus (empreintes, regles YARA, ClamAV) : un malware tout nouveau ou cible peut passer. Sa protection en
temps reel ne surveille que Telechargements et Bureau, apres l'arrivee des fichiers, et il ne protege pas contre le phishing, les mots de passe voles
ou les failles du systeme. Gardez votre systeme a jour, faites des sauvegardes hors ligne et activez
la double authentification sur vos comptes.

## Signaler une faille

Ouvrez une alerte privee via l'onglet **Security > Report a vulnerability** du depot GitHub plutot
qu'une issue publique.
