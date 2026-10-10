# FreeAV : prototype d'antivirus gratuit

Scanner de fichiers en Python. Il fonctionne avec la seule bibliotheque standard ; le moteur YARA
est optionnel (`pip install -r requirements-optional.txt`). Python 3.10 ou plus recent.

## Fonctionnalites

- **Detection par signatures** : empreintes SHA-256 et MD5 des fichiers comparees a une base locale
  (`freeav/data/signatures.txt`). Les bases de hachage ClamAV (`.hdb`, `.hsb`) se chargent avec `--db`.
- **Moteur ClamAV optionnel** : si le demon `clamd` tourne, FreeAV lui envoie chaque fichier
  (protocole INSTREAM) et profite de ses millions de signatures.
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
- **Ligne de commande** et **interface graphique** (Tkinter).

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

Chaque modification est sauvegardee dans `~/.freeav/repair-backups` et peut etre annulee, sauf le
nettoyage des fichiers temporaires et les outils Windows (signales "definitif"). Sous Windows, un
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
Pas encore de protection en temps reel ni de mise a jour automatique planifiee. Aucun antivirus,
gratuit ou payant, ne detecte toutes les menaces : FreeAV complete les bonnes pratiques
(mises a jour du systeme, sauvegardes, prudence avec les pieces jointes), il ne les remplace pas.
