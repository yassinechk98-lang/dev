# FreeAV : prototype d'antivirus gratuit

Scanner de fichiers en Python. Il fonctionne avec la seule bibliotheque standard ; le moteur YARA
est optionnel (`pip install -r requirements-optional.txt`).

## Fonctionnalites

- **Detection par signatures** : empreintes SHA-256 et MD5 des fichiers comparees a une base locale
  (`freeav/data/signatures.txt`). Les bases de hachage ClamAV (`.hdb`, `.hsb`) se chargent avec `--db`.
- **Moteur ClamAV optionnel** : si le demon `clamd` tourne, FreeAV lui envoie chaque fichier
  (protocole INSTREAM) et profite de ses millions de signatures.
- **Regles YARA open source** : FreeAV applique les regles de la communaute, par exemple
  [Yara-Rules/rules](https://github.com/Yara-Rules/rules) (GPL-2.0). Deposez-les dans `~/.freeav/yara`
  ou passez `--yara <dossier>`. Les fichiers de regles invalides sont ignores un par un.
- **Base publique MalwareBazaar** : `python -m freeav update` telecharge les empreintes des malwares
  recents publiees par [abuse.ch](https://bazaar.abuse.ch) (CC0), en HTTPS, avec verification stricte.
- **Quarantaine** : les fichiers infectes sont deplaces dans `~/.freeav/quarantine`, encodes pour ne
  plus etre executables, et peuvent etre restaures ou supprimes.
- **Ligne de commande** et **interface graphique** (Tkinter).

## Utilisation

```bash
cd antivirus

# Analyser un dossier (code de sortie 1 si une menace est trouvee)
python -m freeav scan ~/Downloads

# Mettre automatiquement les menaces en quarantaine, avec ClamAV en plus
python -m freeav scan ~/Downloads --quarantine --clamav

# Mettre a jour les signatures (MalwareBazaar)
python -m freeav update

# Ajouter les regles YARA de la communaute
git clone --depth 1 https://github.com/Yara-Rules/rules ~/.freeav/yara/yara-rules
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

Pas encore de protection en temps reel ni de mise a jour automatique planifiee. Aucun antivirus,
gratuit ou payant, ne detecte toutes les menaces : FreeAV complete les bonnes pratiques
(mises a jour du systeme, sauvegardes, prudence avec les pieces jointes), il ne les remplace pas.
