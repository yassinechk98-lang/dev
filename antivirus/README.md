# FreeAV : prototype d'antivirus gratuit

Scanner de fichiers en Python. Il fonctionne avec la seule bibliotheque standard ; le moteur YARA
est optionnel (`pip install -r requirements-optional.txt`). Python 3.10 ou plus recent.
FreeAV.exe contient le moteur YARA (yara-python, version figee dans `requirements-build.txt`).

## Fonctionnalites

- **Detection par signatures** : empreintes SHA-256 et MD5 des fichiers comparees a une base locale
  (`freeav/data/signatures.txt`). Les bases de hachage ClamAV (`.hdb`, `.hsb`) se chargent avec `--db`.
- **Moteur ClamAV optionnel** : si le demon `clamd` tourne, FreeAV lui envoie chaque fichier
  (protocole INSTREAM) et profite de ses millions de signatures.
- **Pieges courants reperes sans signature** (heuristiques) : double extension qui cache un
  programme (`facture.pdf.exe`), raccourci `.lnk` qui lance PowerShell cache ou mshta, script
  Windows telecharge (`.js`, `.vbs`, `.hta`...) qui telecharge et execute autre chose, document
  Office telecharge dont la macro se lance a l'ouverture. Les scripts et documents ne sont
  examines que s'ils portent la marque Internet de Windows. Ces resultats sont "suspects" :
  signales, jamais mis en quarantaine automatiquement.
- **Regles YARA open source** : FreeAV applique les regles de la communaute. Nous conseillons le
  paquet **core** de [YARA Forge](https://github.com/YARAHQ/yara-forge), filtre pour limiter les faux
  positifs (0 fausse alerte sur 954 fichiers sains lors de nos essais). Les detections YARA sont
  affichees comme **suspectes** et ne sont jamais mises en quarantaine automatiquement.
  Evitez les grandes collections brutes comme Yara-Rules/rules : leurs regles "utilitaires"
  signalent presque tous les fichiers sains.
- **Base publique MalwareBazaar** : `python -m freeav update` telecharge les empreintes des malwares
  des 48 dernieres heures publiees par [abuse.ch](https://bazaar.abuse.ch) (CC0), en HTTPS, avec
  verification stricte. Chaque mise a jour s'ajoute aux precedentes. abuse.ch demande une cle
  gratuite (Auth-Key) a creer sur https://auth.abuse.ch.
- **Quarantaine** : les fichiers infectes sont deplaces dans `~/.freeav/quarantine`, encodes pour ne
  plus etre executables, et peuvent etre restaures ou supprimes.
- **Protection en temps reel** : `python -m freeav watch --quarantine` (ou la case dans l'interface)
  surveille Telechargements et Bureau et analyse chaque nouveau fichier des qu'il est entierement
  ecrit. Les menaces confirmees sont mises en quarantaine aussitot ; un fichier suspect est
  seulement signale.
- **Protection automatique** (Windows, sans droits administrateur) :
  `python -m freeav schedule --at 12:00` (ou le bouton **Protection automatique...**) installe une
  analyse quotidienne (mise a jour des signatures si une cle abuse.ch est enregistree, analyse de
  Telechargements et Bureau, controle des points sensibles du PC, alerte en cas de probleme ;
  journal dans `~/.freeav/logs/auto.log`) et lance la protection en temps reel a chaque ouverture de
  session. `freeav schedule --remove` retire tout, `--status` montre ce qui est actif.
- **Moteurs antivirus complets** en plus des signatures FreeAV :
  - **ClamAV integre** (Windows) : un clic sur **Installer ClamAV** (ou `freeav clamav --install`)
    telecharge la version officielle de ClamAV directement depuis la release de Cisco Talos sur
    GitHub et l'installe dans `%LOCALAPPDATA%\FreeAV\ClamAV`, sans droits administrateur, avec ses
    signatures officielles (environ 300 Mo, mises a jour par `freeav clamav --update`). Elle est
    ensuite utilisee a chaque analyse. Le paquet est verifie par son empreinte SHA-256, inscrite dans
    FreeAV.exe. Le module RAR de ClamAV (`libclamunrar`), dont la licence n'est pas libre, n'est pas
    installe : l'interieur des archives RAR n'est pas analyse par ClamAV.
  - **Deuxieme avis Microsoft Defender** (case cochee par defaut sous Windows, `--defender` en ligne
    de commande) : FreeAV demande a Defender d'analyser les memes dossiers sans rien supprimer, puis
    met lui-meme les menaces en quarantaine.
- **Installation comme un vrai logiciel** (Windows, sans droits administrateur) : le bouton
  **Installer FreeAV sur ce PC** (ou `FreeAV.exe install`) ajoute FreeAV au menu Demarrer et au Bureau,
  ajoute **Analyser avec FreeAV** au clic droit de l'Explorateur (fichiers, dossiers, lecteurs), et
  l'inscrit dans Parametres > Applications, d'ou il se desinstalle (`FreeAV.exe uninstall`).
- **Cles USB** : quand la protection en temps reel est active, chaque cle USB ou carte memoire
  branchee est analysee entierement et ses menaces mises en quarantaine.
- **Mises a jour de FreeAV** : au demarrage, FreeAV regarde si une version plus recente est publiee
  (et l'entretien quotidien previent). Le bouton **Mettre a jour FreeAV** (ou `FreeAV.exe app-update`)
  la telecharge depuis GitHub, verifie son empreinte SHA-256, remplace l'ancienne version, relance la
  protection en temps reel et redemarre FreeAV. Rien ne change sans votre accord. La verification
  contacte github.com ; elle se coupe avec la case « Chercher les nouvelles versions » ou
  `FreeAV.exe app-update --auto-check off`.
- **Analyse rapide** (bouton **Analyse rapide**, ou `freeav scan --quick`) : Telechargements, Bureau,
  dossier temporaire, dossiers Demarrage et programmes lances a l'ouverture de session, la ou les
  malwares arrivent ou s'installent le plus souvent, en quelques minutes.
- **Ligne de commande** et **interface graphique** (Tkinter), avec un bandeau qui dit en un coup
  d'oeil si le PC est protege.

## Reparer mon PC

`python -m freeav repair` (ou le bouton **Reparer mon PC...**) diagnostique les problemes courants,
surtout ceux que laissent les malwares, **sans rien modifier** :

| Domaine | Ce qui est verifie | Reparation proposee |
|---|---|---|
| Demarrage | cles Run/RunOnce, dossier Demarrage, Winlogon (Shell, Userinit) | retrait de l'entree, valeur Windows d'origine |
| Taches planifiees | taches lancees depuis Temp/Telechargements ou avec une commande cachee | desactivation de la tache |
| Reseau | fichier hosts (sites de securite bloques, banque redirigee), proxy Internet et WinHTTP | desactivation de la ligne, du proxy |
| Navigateur | extensions, page d'accueil ou moteur de recherche imposes (Chrome, Edge) | retrait de l'obligation |
| Protection | Microsoft Defender desactive ou dossiers exclus par une strategie | reactivation |
| Nettoyage | fichiers temporaires de plus de 24 h, disque presque plein | suppression des fichiers temporaires |
| Outils Windows | SFC, DISM, cache DNS | lancement de l'outil |

Les programmes lances au demarrage sont aussi analyses avec les signatures de FreeAV.

```bash
python -m freeav repair                      # diagnostic
python -m freeav repair --fix 3fa2c1d0       # reparer un probleme (identifiant affiche)
python -m freeav repair --fix-dangers        # reparer tout ce qui est marque DANGER
python -m freeav repair --undo               # annuler la derniere reparation
```

Les modifications du registre, du fichier hosts, du dossier Demarrage et des taches planifiees sont
sauvegardees dans `~/.freeav/repair-backups` (dans `%ProgramData%\FreeAV`, reserve aux
administrateurs, quand FreeAV est lance en administrateur) et peuvent etre annulees.

**Attention : deux types d'actions sont definitifs et ne peuvent pas etre annules** : le nettoyage des
fichiers temporaires (les fichiers sont supprimes) et les outils Windows SFC, DISM et vidage du cache
DNS. FreeAV les signale "DEFINITIF" et demande une confirmation (`--yes` en ligne de commande). Sous Windows, un
point de restauration systeme est cree avant de reparer si FreeAV est lance en administrateur,
ce qui est necessaire pour les reglages communs a tout le PC (HKLM, hosts, Defender, SFC).

## Utilisation

```bash
cd antivirus

# Analyser un dossier (code de sortie 1 si une menace est trouvee)
python -m freeav scan ~/Downloads

# Mettre automatiquement les menaces en quarantaine, avec ClamAV en plus
python -m freeav scan ~/Downloads --quarantine --clamav

# Mettre a jour les signatures (MalwareBazaar), la premiere fois avec votre cle
python -m freeav update --auth-key VOTRE_CLE --save-key
python -m freeav update

# Ajouter les regles YARA de YARA Forge (paquet core)
#   telecharger yara-forge-rules-core.zip depuis
#   https://github.com/YARAHQ/yara-forge/releases/latest
#   puis copier yara-rules-core.yar dans ~/.freeav/yara/
python -m freeav scan ~/Downloads

# Gerer la quarantaine
python -m freeav quarantine
python -m freeav quarantine --restore <ID>

# Interface graphique
python -m freeav gui
```

Pour tester sans risque, utilisez le [fichier de test EICAR](https://www.eicar.org/download-anti-malware-testfile/) :
il est inoffensif mais reconnu comme une menace par tous les antivirus, y compris FreeAV.

### Activer ClamAV (recommande)

- Linux : `sudo apt install clamav-daemon && sudo freshclam && sudo systemctl start clamav-daemon`
  puis `--clamav --clamd-socket /var/run/clamav/clamd.ctl`
- Windows / macOS : installer ClamAV depuis https://www.clamav.net, lancer `clamd` (port TCP 3310).

## Vie privee et securite

Voir [SECURITE.md](SECURITE.md) : ce que FreeAV garantit pour vos donnees, et ses limites.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Limites du prototype

Les fichiers de plus de 200 Mo ne sont pas analyses (ils sont comptes comme "ignores").
La protection en temps reel verifie les fichiers apres leur arrivee dans les dossiers surveilles
(toutes les 2 secondes) : elle ne bloque pas l'ouverture d'un fichier comme le pilote d'un antivirus
commercial, et ne surveille pas tout le disque. Aucun antivirus,
gratuit ou payant, ne detecte toutes les menaces : FreeAV complete les bonnes pratiques
(mises a jour du systeme, sauvegardes, prudence avec les pieces jointes), il ne les remplace pas.

## Politique de signature du code (Code signing policy)

Code signing policy / Politique de signature du code :
https://freeav-antivirus-gratuit.netlify.app/signature.html (ce qui est signe, par qui, comment
FreeAV.exe est construit). Confidentialite : https://freeav-antivirus-gratuit.netlify.app/confidentialite.html,
resumee par FreeAV a sa premiere ouverture, avec deux choix : chercher les nouvelles versions
(github.com) et le 2e avis Microsoft Defender. FreeAV ne se connecte a rien avant ce choix.

## Licence

Copyright (C) 2026 Yassine.

FreeAV est un logiciel libre : vous pouvez le redistribuer et/ou le modifier selon les termes de la
GNU General Public License telle que publiee par la Free Software Foundation, soit la version 3 de
la licence, soit (a votre choix) toute version ulterieure (GPL-3.0-or-later).

FreeAV est distribue dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ; sans meme la
garantie implicite de QUALITE MARCHANDE ou d'ADEQUATION A UN USAGE PARTICULIER. Voir la GNU General
Public License pour plus de details : texte complet dans [LICENSE](LICENSE).

Cette licence couvre le dossier `antivirus/` et les scripts qui construisent et testent FreeAV
(`.github/workflows/build-windows.yml` et `.github/workflows/antivirus-tests.yml`). Elle ne couvre
pas les autres projets du depot.

ClamAV, que FreeAV peut installer a votre demande, est un programme separe de Cisco Talos sous sa
propre licence (GPLv2) : https://github.com/Cisco-Talos/clamav. FreeAV ne le redistribue pas : il le
telecharge depuis la release officielle de Cisco, et le lance comme un programme a part.

FreeAV.exe contient d'autres logiciels libres (Python, Tcl/Tk, OpenSSL, YARA, le chargeur de
PyInstaller...). Leurs licences sont reproduites dans [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt),
inclus dans FreeAV.exe et joint a chaque version publiee.
