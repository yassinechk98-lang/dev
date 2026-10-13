# Temporaire (branche de test seulement) : affiche chaque ecran de connexion sur le runner
# Windows et en fait une capture PNG, pour verifier le rendu reel.
import sys
import time
import traceback
from pathlib import Path

import tkinter as tk
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "antivirus"))

from freeav import login, login_gui, privacy  # noqa: E402

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
login.SCRYPT = {"n": 2 ** 12, "r": 8, "p": 1}
login.SCRYPT_RECOVERY = {"n": 2 ** 10, "r": 8, "p": 1}
PASSWORD = "cheval-batterie-agrafe"
failed = []

root = tk.Tk()
root.withdraw()


def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.015)


def wait(condition, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        root.update()
        if condition():
            return
        time.sleep(0.015)
    raise TimeoutError("etat attendu non atteint")


def title(window):
    labels = [w for w in window.content.winfo_children() if isinstance(w, tk.Label)]
    return labels[0].cget("text") if labels else ""


def shot(window, name, settle=0.9):
    window.attributes("-topmost", True)
    window.lift()
    pump(settle)
    x, y = window.winfo_rootx(), window.winfo_rooty()
    w, h = window.winfo_width(), window.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(OUT / f"apercu-{name}.png")
    print(f"capture {name} : {w}x{h}, ecran {title(window)!r}", flush=True)


def step(name, fn):
    t = time.monotonic()
    try:
        fn()
    except Exception:
        failed.append(name)
        print(f"ECHEC {name}", flush=True)
        traceback.print_exc()
    print(f"  ({time.monotonic() - t:.1f} s)", flush=True)


state = {}


def setup():
    login.disable()
    w = login_gui.AccessWindow(root, "offer")
    shot(w, "01-proposition")
    w.show_account()
    w.f_nick.set("Yassine")
    w.f_pass.set(PASSWORD)
    w.f_confirm.set(PASSWORD)
    w.f_pass.focus()
    shot(w, "02-creation")
    w.submit_account()
    w.boxes.set("482")
    shot(w, "03-qr-code")
    then = time.time() - 60  # code d'il y a deux pas : la connexion qui suit reste valide
    w.boxes.set(login.totp(w.secret, then))
    secret = w.secret
    nickname, password = w.nickname, w.password
    codes = login.create(nickname, password, secret, login.totp(secret, then), now=then)
    w.show_codes(codes, lambda: None, step=(3, 3))
    shot(w, "04-codes-de-secours")
    w.confirm_box.toggle()
    w.show_done("FreeAV est protégé", "À la prochaine ouverture, FreeAV demandera votre pseudo "
                "et votre mot de passe, puis le code de votre téléphone.", "Terminer",
                lambda: w.finish(True))
    shot(w, "05-termine", settle=1.2)
    w.destroy()
    state.update(secret=secret, codes=codes)


def sign_in():
    w = login_gui.AccessWindow(root, "open")
    shot(w, "06-connexion")
    w.f_nick.set("Yassine")
    w.f_pass.set("pas-le-bon-mot-de-passe")
    w.submit_login()
    wait(lambda: w.notice.text)
    shot(w, "07-erreur")
    w.f_pass.set(PASSWORD)
    w.submit_login()
    wait(lambda: title(w) == "Vérification en deux étapes")
    w.boxes.set("39")
    shot(w, "08-code-otp")
    w.show_code(recovery=True)
    w.f_code.set(state["codes"][0])
    shot(w, "09-code-de-secours")
    w.submit_code()
    wait(lambda: title(w).startswith("Bienvenue"))
    shot(w, "10-bienvenue", settle=1.2)
    w.destroy()


def forgot():
    w = login_gui.AccessWindow(root, "open")
    w.show_forgot()
    w.f_nick.set("Yassine")
    w.f_code.set("123456")
    w.f_new.set("trois-mots-faciles")
    w.f_confirm.set("trois-mots-faciles")
    shot(w, "11-mot-de-passe-oublie")
    w.show_no_code()
    shot(w, "12-plus-aucun-code")
    w.destroy()


def manage():
    w = login_gui.AccessWindow(root, "manage")
    w.f_pass.set(PASSWORD)
    shot(w, "13-confirmer")
    w.submit_login()
    wait(lambda: title(w) == "Vérification en deux étapes")
    w.show_code(recovery=True)
    w.f_code.set(state["codes"][1])
    w.submit_code()
    wait(lambda: title(w) == "Connexion à FreeAV")
    shot(w, "14-reglages")
    w.show_change_password()
    w.f_new.set("Un-Mot-De-Passe-Tres-Solide-42")
    shot(w, "15-nouveau-mot-de-passe")
    w.show_manage()
    w.show_confirm("Retirer la connexion ?", "FreeAV s'ouvrira de nouveau sans pseudo ni mot de "
                   "passe. La protection n'est pas touchée.", "Retirer", lambda: None,
                   danger=True)
    shot(w, "16-retirer")
    w.destroy()


def locked():
    w = login_gui.AccessWindow(root, "lock")
    shot(w, "17-verrouille")
    w.destroy()


def main_window():
    from freeav import gui
    privacy.accept(False, False)
    app = gui.App()
    app.attributes("-topmost", True)
    end = time.monotonic() + 2.5
    while time.monotonic() < end:
        app.update()
        time.sleep(0.015)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(OUT / "apercu-18-fenetre.png")
    print(f"capture 18-fenetre : {w}x{h}", flush=True)
    app.destroy()


t0 = time.monotonic()
print("ecran", root.winfo_screenwidth(), "x", root.winfo_screenheight(), "scaling",
      root.tk.call("tk", "scaling"), flush=True)
for name, fn in (("setup", setup), ("sign_in", sign_in), ("forgot", forgot),
                 ("manage", manage), ("locked", locked)):
    step(name, fn)
root.destroy()
step("main_window", main_window)
print(f"total {time.monotonic() - t0:.1f} s, echecs : {failed}", flush=True)
sys.exit(1 if failed else 0)
