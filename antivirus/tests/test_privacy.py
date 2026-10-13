"""Politique de confidentialite a la premiere ouverture et changements annonces avant l'installation."""

from freeav import installer, privacy, selfupdate, updater
from test_engines import windows_system


def test_first_run_choices_are_saved_and_shown_once(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "CONFIG_FILE", tmp_path / "config.json")
    assert privacy.needs_first_run()
    assert privacy.defender_enabled() and selfupdate.auto_check_enabled()
    privacy.accept(check_updates=False, defender=False)
    assert not privacy.needs_first_run()
    assert not selfupdate.auto_check_enabled() and not privacy.defender_enabled()
    privacy.set_defender(True)
    assert privacy.defender_enabled() and not selfupdate.auto_check_enabled()


def test_policy_names_every_connection():
    for host in ("github.com", "mb-api.abuse.ch", "database.clamav.net", "Microsoft"):
        assert host in privacy.SUMMARY
    assert privacy.PRIVACY_URL.startswith("https://") and privacy.PRIVACY_URL.endswith("confidentialite.html")


def test_install_announces_what_it_changes(tmp_path):
    system, _ = windows_system(tmp_path)
    changes = installer.planned_changes(system)
    source = tmp_path / "FreeAV.exe"
    source.write_bytes(b"MZ" * 10)
    done = installer.install(system, source)
    assert len(changes) == len(done)
    assert str(installer.target_exe(system).parent) in changes[0]
    assert any(installer.MENU_LABEL in c for c in changes)
