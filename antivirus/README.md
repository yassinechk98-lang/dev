# FreeAV : prototype d'antivirus gratuit

Scanner de fichiers en Python, sans dependance a l'execution (bibliotheque standard uniquement).

## Fonctionnalites

- **Detection par signatures** : empreintes SHA-256 et MD5 des fichiers comparees a une base locale
  (`freeav/data/signatures.txt`). Les bases de hachage ClamAV (`.hdb`, `.hsb`) se chargent avec `--db`.
- **Moteur ClamAV optionnel** : si le demon `clamd` tourne, FreeAV lui envoie chaque fichier
  (protocole INSTREAM) et profite de ses millions de signatures.
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

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Limites du prototype

Pas encore de protection en temps reel, d'analyse heuristique, ni de mise a jour automatique
de la base de signatures. Ce sont les prochaines etapes possibles.
