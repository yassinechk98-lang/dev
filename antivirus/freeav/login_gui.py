# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Ecrans de connexion de FreeAV (Tkinter), dans une seule fenetre au theme sombre du site :
connexion (pseudo et mot de passe), code OTP a 6 chiffres, mot de passe oublie, creation de
l'acces (QR code, codes de secours), reglages et verrouillage de la fenetre principale.

La logique (empreintes, codes, delais) est dans login.py ; rien ici ne touche au reseau.
Les verifications (scrypt) tournent dans un fil a part pour que la fenetre reste fluide.
"""

import math
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import font as tkfont
from tkinter import ttk

from . import __version__, login, qrcode, updater

OFFERED_SETTING = "login_offered"

# Couleurs du site FreeAV (theme sombre)
SURFACE = "#121a16"
FIELD = "#17211c"
HOVER = "#1c2822"
BORDER = "#24302a"
BORDER_HOVER = "#3a4c42"
TEXT = "#e8f0eb"
MUTED = "#9aaba1"
FAINT = "#6b7c72"
ACCENT = "#22c55e"
ACCENT_LIGHT = "#4ade80"
ACCENT_DARK = "#16a34a"
ON_ACCENT = "#05210f"
ACCENT_SOFT = "#132a1c"
BLUE = "#38bdf8"
DANGER = "#f87171"
DANGER_SOFT = "#2a1414"
WARN = "#fbbf24"
LIME = "#a3e635"
FONT = "Segoe UI"
MONO = "Consolas"

WIDTH, HEIGHT = 820, 580
BRAND_W = 290
CONTENT_W = 434
HALF_W = (CONTENT_W - 14) // 2


# -- dessin -----------------------------------------------------------------------------

def focused(widget: tk.Misc):
    """Widget qui a le focus clavier (None si aucun, ou dans une boite de dialogue)."""
    try:
        return widget.focus_get()
    except (KeyError, tk.TclError):
        return None


class Timers:
    """Minuteries (animations, delais) annulees quand le widget est detruit : sans cela, Tk
    signale une « commande inconnue » quand une minuterie d'un ecran ferme se declenche."""

    def later(self, ms: int, fn, *args) -> str:
        jobs = self.__dict__.setdefault("_jobs", set())
        job = ""

        def run():
            jobs.discard(job)
            fn(*args)
        job = self.after(ms, run)
        jobs.add(job)
        return job

    def destroy(self):
        for job in self.__dict__.pop("_jobs", ()):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        super().destroy()


def _rgb(color: str) -> tuple:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def mix(a: str, b: str, t: float) -> str:
    """Couleur entre a (t=0) et b (t=1)."""
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    """Rectangle aux coins arrondis (polygone lisse aux points doubles)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = (x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
           x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1)
    return canvas.create_polygon(pts, smooth=True, **kw)


def draw_icon(c: tk.Canvas, kind: str, x: float, y: float, color: str, tag: str = "icon",
              w: float = 1.6) -> None:
    """Petites icones au trait (18 x 18 environ), dessinees : rien a embarquer."""
    line = {"fill": color, "width": w, "capstyle": "round", "joinstyle": "round", "tags": tag}
    ring = {"outline": color, "width": w, "tags": tag}
    if kind == "user":
        c.create_oval(x - 4, y - 8, x + 4, y, **ring)
        c.create_arc(x - 7, y + 1, x + 7, y + 15, start=0, extent=180, style="arc", **ring)
    elif kind == "lock":
        c.create_arc(x - 4.5, y - 9, x + 4.5, y - 1, start=0, extent=180, style="arc", **ring)
        c.create_line(x - 4.5, y - 5, x - 4.5, y - 1, **line)
        c.create_line(x + 4.5, y - 5, x + 4.5, y - 1, **line)
        round_rect(c, x - 7, y - 1, x + 7, y + 8, 2.5, fill="", **ring)
        c.create_line(x, y + 2.5, x, y + 4.5, **line)
    elif kind == "key":
        c.create_oval(x - 8, y - 4, x, y + 4, **ring)
        c.create_line(x, y, x + 8, y, **line)
        c.create_line(x + 5, y, x + 5, y + 3.5, **line)
        c.create_line(x + 8, y, x + 8, y + 3.5, **line)
    elif kind == "phone":
        round_rect(c, x - 5.5, y - 9, x + 5.5, y + 9, 2.5, fill="", **ring)
        c.create_line(x - 1.5, y + 6, x + 1.5, y + 6, **line)
    elif kind == "shield":
        c.create_polygon(x, y - 9, x + 7.5, y - 6, x + 7, y + 2, x, y + 9, x - 7, y + 2,
                         x - 7.5, y - 6, fill="", joinstyle="round", **ring)
        c.create_line(x - 3, y, x - 0.5, y + 2.5, x + 3.5, y - 2.5, **line)
    elif kind == "check":
        c.create_line(x - 4.5, y, x - 1.2, y + 3.5, x + 5, y - 3.5, **{**line, "width": w + 0.6})
    elif kind == "bolt":
        c.create_polygon(x + 1.5, y - 9, x - 5, y + 1.5, x - 0.5, y + 1.5, x - 1.5, y + 9,
                         x + 5, y - 1.5, x + 0.5, y - 1.5, fill="", joinstyle="round", **ring)
    elif kind == "cloud-off":
        c.create_arc(x - 8, y - 5, x + 2, y + 5, start=90, extent=180, style="arc", **ring)
        c.create_arc(x - 4, y - 8, x + 6, y + 2, start=10, extent=170, style="arc", **ring)
        c.create_arc(x - 1, y - 3, x + 9, y + 5, start=-90, extent=150, style="arc", **ring)
        c.create_line(x - 3, y + 5, x + 5, y + 5, **line)
        c.create_line(x - 8, y - 8, x + 8, y + 8, **line)
    elif kind in ("eye", "eye-off"):
        c.create_arc(x - 9, y - 6, x + 9, y + 12, start=20, extent=140, style="arc", **ring)
        c.create_arc(x - 9, y - 12, x + 9, y + 6, start=200, extent=140, style="arc", **ring)
        c.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, **ring)
        if kind == "eye-off":
            c.create_line(x - 8, y - 7, x + 8, y + 7, **line)
    elif kind == "chevron":
        c.create_line(x - 2.5, y - 5, x + 2.5, y, x - 2.5, y + 5, **line)


def _shield_points(cx, cy, s):
    pts = ((32, 3), (57, 12), (55, 35), (32, 61), (9, 35), (7, 12))
    return [v for px, py in pts for v in (cx + (px - 32) * s, cy + (py - 32) * s)]


def draw_emblem(c: tk.Canvas, cx, cy, s, tag="emblem") -> None:
    """Bouclier de FreeAV en deux tons, avec sa coche."""
    c.create_polygon(_shield_points(cx, cy, s), fill=ACCENT, outline="", tags=tag)
    half = ((32, 3), (32, 61), (9, 35), (7, 12))
    c.create_polygon([v for px, py in half for v in (cx + (px - 32) * s, cy + (py - 32) * s)],
                     fill=ACCENT_LIGHT, outline="", tags=tag)
    c.create_line(cx - 11 * s, cy + 1 * s, cx - 3 * s, cy + 9 * s, cx + 12 * s, cy - 8 * s,
                  fill="#ffffff", width=5 * s, capstyle="round", joinstyle="round", tags=tag)


# -- composants -------------------------------------------------------------------------

class Field(tk.Frame):
    """Champ arrondi : libelle, icone, texte ou mot de passe (avec bouton pour l'afficher)."""

    def __init__(self, parent, label: str, icon: str | None = None, secret: bool = False,
                 width: int = CONTENT_W, mono: bool = False, on_change=None):
        super().__init__(parent, bg=SURFACE)
        self.secret, self.width, self.hidden = secret, width, True
        self.var = tk.StringVar()
        top = tk.Frame(self, bg=SURFACE)
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text=label, bg=SURFACE, fg=MUTED, font=(FONT, 9, "bold")).pack(side="left")
        self.caps = tk.Label(top, text="", bg=SURFACE, fg=WARN, font=(FONT, 8, "bold"))
        self.caps.pack(side="right")
        h = 44
        self.canvas = tk.Canvas(self, width=width, height=h, bg=SURFACE, highlightthickness=0,
                                bd=0)
        self.canvas.pack(anchor="w")
        self.box = round_rect(self.canvas, 1, 1, width - 1, h - 1, 10, fill=FIELD,
                              outline=BORDER, width=1.5)
        x = 14
        if icon:
            draw_icon(self.canvas, icon, 25, h / 2, FAINT)
            x = 44
        right = width - (44 if secret else 14)
        self.entry = tk.Entry(self.canvas, textvariable=self.var, bd=0, relief="flat", bg=FIELD,
                              fg=TEXT, insertbackground=TEXT, insertwidth=2,
                              highlightthickness=0, selectbackground=ACCENT_DARK,
                              selectforeground="#ffffff", disabledbackground=FIELD,
                              font=(MONO, 12) if mono else (FONT, 11),
                              show="\u2022" if secret else "")
        self.canvas.create_window(x, h / 2, window=self.entry, anchor="w", width=right - x)
        if secret:
            self._draw_eye()
            self.canvas.tag_bind("eye", "<Button-1>", lambda e: self.toggle())
            self.canvas.tag_bind("eye", "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
            self.canvas.tag_bind("eye", "<Leave>", lambda e: self.canvas.config(cursor=""))
            for seq in ("<KeyPress>", "<KeyRelease>"):
                self.entry.bind(seq, self._caps_lock, add="+")
        self.entry.bind("<FocusIn>", lambda e: self._border(), add="+")
        self.entry.bind("<FocusOut>", lambda e: self._border(), add="+")
        for widget in (self.canvas, self.entry):
            widget.bind("<Enter>", lambda e: self._border(hover=True), add="+")
            widget.bind("<Leave>", lambda e: self._border(), add="+")
        self.canvas.bind("<Button-1>", lambda e: self.focus())
        self.error_state = False
        self.var.trace_add("write", lambda *a: self._edited(on_change))

    def _draw_eye(self):
        self.canvas.delete("eye")
        x, y = self.width - 24, 22
        self.canvas.create_rectangle(x - 14, y - 14, x + 14, y + 14, fill=FIELD, outline="",
                                     tags="eye")
        draw_icon(self.canvas, "eye" if self.hidden else "eye-off", x, y, MUTED, tag="eye")

    def toggle(self):
        self.hidden = not self.hidden
        self.entry.config(show="\u2022" if self.hidden else "")
        self._draw_eye()

    def _caps_lock(self, event):
        state = getattr(event, "state", 0)
        on = isinstance(state, int) and bool(state & 0x2)  # Verr. Maj. (LockMask)
        if event.type == tk.EventType.KeyPress and event.keysym == "Caps_Lock":
            on = not on  # l'etat ne change qu'apres cette touche
        self.caps.config(text="Verr. Maj. activé" if on else "")

    def _edited(self, on_change):
        if self.error_state:
            self.error_state = False
            self._border()
        if on_change:
            on_change(self.get())

    def _border(self, hover=False):
        if self.error_state:
            color, width = DANGER, 2
        elif focused(self) is self.entry:
            color, width = ACCENT, 2
        else:
            color, width = (BORDER_HOVER if hover else BORDER), 1.5
        self.canvas.itemconfig(self.box, outline=color, width=width)

    def mark_error(self):
        self.error_state = True
        self._border()

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str):
        self.var.set(value)

    def clear(self):
        self.var.set("")

    def focus(self):
        self.entry.focus_set()
        self.entry.icursor("end")


class Button(Timers, tk.Canvas):
    """Bouton arrondi : principal (vert), secondaire ou danger, avec etat « en cours »."""

    STYLES = {
        "primary": (ACCENT, ACCENT_LIGHT, ACCENT_DARK, "", ON_ACCENT),
        "secondary": (FIELD, HOVER, BORDER, BORDER, TEXT),
        "danger": (DANGER_SOFT, "#3a1a1a", "#4a1f1f", "#5b2626", DANGER),
    }

    def __init__(self, parent, text: str, command, kind: str = "primary",
                 width: int = CONTENT_W, height: int = 44):
        bg = parent.cget("bg")
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0,
                         takefocus=1, cursor="hand2")
        self.command, self.text, self.kind = command, text, kind
        self.enabled, self.busy, self.hover, self.pressed = True, False, False, False
        self.fill, self.fill_hover, self.fill_press, self.outline, self.fg = self.STYLES[kind]
        self.w, self.h = width, height
        self.rect = round_rect(self, 1, 1, width - 1, height - 1, 10, fill=self.fill,
                               outline=self.outline or self.fill, width=1.5)
        self.font = (FONT, 10, "bold")
        self.label = self.create_text(width / 2, height / 2, text=text, fill=self.fg,
                                      font=self.font)
        self.spinner = None
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<KeyPress-Return>", lambda e: (self.invoke(), "break")[1])
        self.bind("<KeyPress-space>", lambda e: (self.invoke(), "break")[1])
        self.bind("<FocusIn>", lambda e: self._paint())
        self.bind("<FocusOut>", lambda e: self._paint())

    def _set(self, **state):
        for k, v in state.items():
            setattr(self, k, v)
        self._paint()

    def _paint(self):
        if not self.winfo_exists():
            return
        if not self.enabled and not self.busy:
            fill, fg = mix(self.fill, SURFACE, 0.55), mix(self.fg, SURFACE, 0.45)
        elif self.pressed:
            fill, fg = self.fill_press, self.fg
        elif self.hover and not self.busy:
            fill, fg = self.fill_hover, self.fg
        else:
            fill, fg = self.fill, self.fg
        has_focus = focused(self) is self
        outline = TEXT if has_focus else (self.outline or fill)
        self.itemconfig(self.rect, fill=fill, outline=outline, width=2 if has_focus else 1.5)
        self.itemconfig(self.label, fill=fg)
        self.config(cursor="hand2" if self.enabled and not self.busy else "")

    def _release(self, event):
        inside = 0 <= event.x <= self.w and 0 <= event.y <= self.h
        self._set(pressed=False)
        if inside:
            self.invoke()

    def invoke(self):
        if self.enabled and not self.busy:
            self.command()

    def set_enabled(self, on: bool):
        self.enabled = bool(on)
        self._paint()

    def set_text(self, text: str):
        self.text = text
        self.itemconfig(self.label, text=text)

    def set_busy(self, on: bool, text: str = "Vérification"):
        if not self.winfo_exists():
            return
        self.busy = on
        if on:
            width = tkfont.Font(font=self.font).measure(text)
            x = self.w / 2 + 12
            self.coords(self.label, x, self.h / 2)
            self.itemconfig(self.label, text=text)
            sx = x - width / 2 - 14
            self.spinner = self.create_arc(sx - 7, self.h / 2 - 7, sx + 7, self.h / 2 + 7,
                                           start=90, extent=270, style="arc", width=2,
                                           outline=self.fg)
            self._spin()
        else:
            if self.spinner:
                self.delete(self.spinner)
                self.spinner = None
            self.coords(self.label, self.w / 2, self.h / 2)
            self.itemconfig(self.label, text=self.text)
        self._paint()

    def _spin(self):
        if self.spinner and self.winfo_exists():
            start = float(self.itemcget(self.spinner, "start"))
            self.itemconfig(self.spinner, start=(start - 24) % 360)
            self.later(40, self._spin)


class Link(tk.Label):
    """Lien texte (vert clair), utilisable au clavier."""

    def __init__(self, parent, text: str, command, color: str = ACCENT_LIGHT, size: int = 9):
        bg = parent.cget("bg")
        super().__init__(parent, text=text, bg=bg, fg=color, cursor="hand2", takefocus=1,
                         font=(FONT, size, "bold"), highlightthickness=1,
                         highlightbackground=bg, highlightcolor=mix(color, bg, 0.4))
        self.command = command
        self.normal = tkfont.Font(font=(FONT, size, "bold"))
        self.under = tkfont.Font(font=(FONT, size, "bold"))
        self.under.configure(underline=True)
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<KeyPress-Return>", lambda e: (self.command(), "break")[1])
        self.bind("<KeyPress-space>", lambda e: (self.command(), "break")[1])
        self.bind("<Enter>", lambda e: self.config(font=self.under))
        self.bind("<Leave>", lambda e: self.config(font=self.normal))


class Notice(tk.Frame):
    """Message sous le formulaire : erreur (rouge), succes (vert) ou information."""

    KINDS = {"error": (DANGER, DANGER_SOFT), "success": (ACCENT_LIGHT, ACCENT_SOFT),
             "info": (BLUE, "#0f2230"), "warn": (WARN, "#2a2110")}

    def __init__(self, parent):
        super().__init__(parent, bg=SURFACE)
        self.inner = tk.Frame(self, bg=DANGER_SOFT)
        self.bar = tk.Frame(self.inner, bg=DANGER, width=3)
        self.bar.pack(side="left", fill="y")
        self.label = tk.Label(self.inner, text="", bg=DANGER_SOFT, fg=TEXT, font=(FONT, 9),
                              justify="left", anchor="w", wraplength=CONTENT_W - 28, padx=10,
                              pady=8)
        self.label.pack(side="left", fill="x", expand=True)

    def show(self, text: str, kind: str = "error"):
        fg, bg = self.KINDS[kind]
        self.inner.config(bg=bg)
        self.bar.config(bg=fg)
        self.label.config(text=text, bg=bg)
        self.inner.pack(fill="x", pady=(0, 12))

    def hide(self):
        self.label.config(text="")
        self.inner.pack_forget()
        self.config(height=1)  # sinon le cadre vide garde sa hauteur

    @property
    def text(self) -> str:
        return self.label.cget("text")


class CodeBoxes(Timers, tk.Frame):
    """Six cases pour le code a usage unique : saisie chiffre par chiffre, collage accepte,
    validation automatique au sixieme chiffre."""

    def __init__(self, parent, on_complete, count: int = 6):
        super().__init__(parent, bg=SURFACE)
        self.on_complete, self.count = on_complete, count
        self.boxes, self.vars = [], []
        for i in range(count):
            c = tk.Canvas(self, width=50, height=56, bg=SURFACE, highlightthickness=0, bd=0)
            c.pack(side="left", padx=(0, 20 if i == count // 2 - 1 else 10))
            rect = round_rect(c, 1, 1, 49, 55, 11, fill=FIELD, outline=BORDER, width=1.5)
            var = tk.StringVar()
            entry = tk.Entry(c, textvariable=var, width=2, justify="center", bd=0,
                             relief="flat", bg=FIELD, fg=TEXT, insertbackground=TEXT,
                             highlightthickness=0, font=(FONT, 18, "bold"))
            c.create_window(25, 28, window=entry, width=30)
            entry.bind("<KeyPress>", lambda e, i=i: self._key(e, i))
            entry.bind("<<Paste>>", lambda e: (self._paste(), "break")[1])
            entry.bind("<FocusIn>", lambda e, i=i: self._paint(), add="+")
            entry.bind("<FocusOut>", lambda e, i=i: self._paint(), add="+")
            c.bind("<Button-1>", lambda e, i=i: self.boxes[i][1].focus_set())
            self.boxes.append((c, entry, rect))
            self.vars.append(var)

    def _paint(self, error: bool = False):
        for (c, entry, rect), var in zip(self.boxes, self.vars):
            if error:
                color = DANGER
            elif focused(self) is entry:
                color = ACCENT
            elif var.get():
                color = BORDER_HOVER
            else:
                color = BORDER
            c.itemconfig(rect, outline=color, width=2 if color in (ACCENT, DANGER) else 1.5)

    def _key(self, event, i):
        keysym = event.keysym
        if keysym in ("Tab", "ISO_Left_Tab", "Return", "KP_Enter", "Escape"):
            return None
        if keysym == "BackSpace":
            if self.vars[i].get():
                self.vars[i].set("")
            elif i > 0:
                self.vars[i - 1].set("")
                self.boxes[i - 1][1].focus_set()
            self._paint()
            return "break"
        if keysym == "Left" and i > 0:
            self.boxes[i - 1][1].focus_set()
            return "break"
        if keysym == "Right" and i < self.count - 1:
            self.boxes[i + 1][1].focus_set()
            return "break"
        if (event.state & 0x4) and keysym.lower() == "v":
            self._paste()
            return "break"
        if len(event.char) == 1 and event.char in "0123456789":
            self.vars[i].set(event.char)
            if i < self.count - 1:
                self.boxes[i + 1][1].focus_set()
            self._paint()
            self._check()
        return "break"

    def _paste(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self.set("".join(ch for ch in text if ch.isdigit()))
        self._check()

    def _check(self):
        code = self.get()
        if len(code) == self.count and code.isdigit():
            self.later(80, self.on_complete, code)

    def set(self, code: str):
        digits = (code + " " * self.count)[:self.count]
        for var, ch in zip(self.vars, digits):
            var.set(ch.strip())
        target = min(len(code.strip()), self.count - 1)
        self.boxes[target][1].focus_set()
        self._paint()

    def get(self) -> str:
        return "".join(v.get() for v in self.vars)

    def clear(self, error: bool = False):
        for v in self.vars:
            v.set("")
        self.boxes[0][1].focus_set()
        self._paint(error)

    def focus(self):
        self.boxes[0][1].focus_set()
        self._paint()


class Countdown(Timers, tk.Canvas):
    """Anneau qui montre le temps restant avant que le code OTP change (30 secondes)."""

    def __init__(self, parent):
        super().__init__(parent, width=28, height=28, bg=SURFACE, highlightthickness=0, bd=0)
        self.create_oval(3, 3, 25, 25, outline=BORDER, width=3)
        self.arc = self.create_arc(3, 3, 25, 25, start=90, extent=-359, style="arc",
                                   outline=ACCENT, width=3)
        self.label = self.create_text(14, 14, text="", fill=MUTED, font=(FONT, 7, "bold"))
        self._tick()

    def _tick(self):
        if not self.winfo_exists():
            return
        left = login.OTP_STEP - time.time() % login.OTP_STEP
        color = WARN if left <= 5 else ACCENT
        self.itemconfig(self.arc, extent=-max(1, 360 * left / login.OTP_STEP), outline=color)
        self.itemconfig(self.label, text=str(math.ceil(left)))
        self.later(250, self._tick)


class StrengthMeter(tk.Frame):
    """Jauge de solidite du mot de passe."""

    LABELS = ("", "Faible", "Moyen", "Bon", "Excellent")
    COLORS = (DANGER, DANGER, WARN, LIME, ACCENT)

    def __init__(self, parent):
        super().__init__(parent, bg=SURFACE)
        self.bar_w = CONTENT_W - 150
        self.canvas = tk.Canvas(self, width=self.bar_w, height=6, bg=SURFACE,
                                highlightthickness=0, bd=0)
        self.canvas.pack(side="left", pady=(1, 0))
        self.label = tk.Label(self, text="", bg=SURFACE, fg=MUTED, font=(FONT, 8, "bold"),
                              anchor="e")
        self.label.pack(side="right")
        seg = (self.bar_w - 3 * 6) / 4
        self.segments = [round_rect(self.canvas, i * (seg + 6), 0, i * (seg + 6) + seg, 6, 3,
                                    fill=BORDER, outline="") for i in range(4)]
        self.score = 0
        self.update_for("")

    def update_for(self, password: str, nickname: str = ""):
        if not password:
            self.score, filled, color = 0, 0, BORDER
            text, fg = "12 caractères ou plus", MUTED
        else:
            self.score = login.strength(password, nickname)
            filled, color = max(self.score, 1), self.COLORS[self.score]
            if self.score:
                text = self.LABELS[self.score]
            else:
                text = "Trop court" if len(password) < login.MIN_PASSWORD else "Trop facile"
            fg = color
        for i, item in enumerate(self.segments):
            self.canvas.itemconfig(item, fill=color if i < filled else BORDER)
        self.label.config(text=text, fg=fg)


class QrView(tk.Canvas):
    """QR code dessine (modules noirs sur carte blanche, marge de 4 modules)."""

    def __init__(self, parent, text: str, target: int = 200):
        matrix = qrcode.make(text)
        n = len(matrix) + 8
        module = max(3, target // n)
        size = n * module
        super().__init__(parent, width=size, height=size, bg=SURFACE, highlightthickness=0,
                         bd=0)
        round_rect(self, 0, 0, size, size, 12, fill="#ffffff", outline="")
        for y, row in enumerate(matrix):
            x = 0
            while x < len(row):  # une barre par suite de modules noirs : moins d'objets
                if row[x]:
                    start = x
                    while x < len(row) and row[x]:
                        x += 1
                    self.create_rectangle((start + 4) * module, (y + 4) * module,
                                          (x + 4) * module, (y + 5) * module,
                                          fill="#000000", outline="")
                else:
                    x += 1
        self.size = size


class Switch(Timers, tk.Canvas):
    """Interrupteur anime."""

    def __init__(self, parent, value: bool = True, on_change=None):
        super().__init__(parent, width=44, height=24, bg=parent.cget("bg"), highlightthickness=0,
                         bd=0, cursor="hand2", takefocus=1)
        self.value, self.on_change = value, on_change
        self.track = round_rect(self, 1, 1, 43, 23, 11, fill=ACCENT, outline="")
        self.knob = self.create_oval(0, 0, 0, 0, fill="#ffffff", outline="")
        self.pos = 1.0 if value else 0.0
        self._place()
        self.bind("<Button-1>", lambda e: self.toggle())
        self.bind("<KeyPress-space>", lambda e: (self.toggle(), "break")[1])

    def _place(self):
        x = 4 + self.pos * 20
        self.coords(self.knob, x, 4, x + 16, 20)
        self.itemconfig(self.track, fill=mix(BORDER_HOVER, ACCENT, self.pos))

    def toggle(self):
        self.value = not self.value
        self._animate(1.0 if self.value else 0.0)
        if self.on_change:
            self.on_change(self.value)

    def _animate(self, target, steps=6):
        if not self.winfo_exists():
            return
        self.pos += (target - self.pos) / max(steps, 1)
        if steps <= 1:
            self.pos = target
        self._place()
        if steps > 1:
            self.later(16, self._animate, target, steps - 1)


class CheckBox(tk.Frame):
    """Case a cocher arrondie avec son libelle."""

    def __init__(self, parent, text: str, on_change=None):
        super().__init__(parent, bg=SURFACE, cursor="hand2")
        self.value, self.on_change = False, on_change
        self.box = tk.Canvas(self, width=22, height=22, bg=SURFACE, highlightthickness=0, bd=0,
                             takefocus=1)
        self.box.pack(side="left")
        self.label = tk.Label(self, text=text, bg=SURFACE, fg=TEXT, font=(FONT, 10))
        self.label.pack(side="left", padx=(8, 0))
        for w in (self, self.box, self.label):
            w.bind("<Button-1>", lambda e: self.toggle())
        self.box.bind("<KeyPress-space>", lambda e: (self.toggle(), "break")[1])
        self._paint()

    def _paint(self):
        self.box.delete("all")
        round_rect(self.box, 2, 2, 20, 20, 5, fill=ACCENT if self.value else FIELD,
                   outline=ACCENT if self.value else BORDER_HOVER, width=1.5)
        if self.value:
            draw_icon(self.box, "check", 11, 11, ON_ACCENT, w=2)

    def toggle(self):
        self.value = not self.value
        self._paint()
        if self.on_change:
            self.on_change(self.value)


class ActionRow(tk.Canvas):
    """Ligne cliquable des reglages : icone, libelle, detail et chevron."""

    def __init__(self, parent, icon: str, text: str, detail: str, command, danger=False):
        super().__init__(parent, width=CONTENT_W, height=54, bg=SURFACE, highlightthickness=0,
                         bd=0, cursor="hand2", takefocus=1)
        self.command = command
        color = DANGER if danger else ACCENT_LIGHT
        self.rect = round_rect(self, 1, 1, CONTENT_W - 1, 53, 10, fill=FIELD, outline=BORDER,
                               width=1.5)
        round_rect(self, 12, 13, 40, 41, 8, fill=DANGER_SOFT if danger else ACCENT_SOFT,
                   outline="")
        draw_icon(self, icon, 26, 27, color)
        self.create_text(54, 19, text=text, anchor="w", fill=DANGER if danger else TEXT,
                         font=(FONT, 10, "bold"))
        self.create_text(54, 37, text=detail, anchor="w", fill=MUTED, font=(FONT, 8))
        draw_icon(self, "chevron", CONTENT_W - 22, 27, FAINT)
        self.bind("<Enter>", lambda e: self.itemconfig(self.rect, fill=HOVER,
                                                       outline=BORDER_HOVER))
        self.bind("<Leave>", lambda e: self.itemconfig(self.rect, fill=FIELD, outline=BORDER))
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<KeyPress-Return>", lambda e: (self.command(), "break")[1])
        self.bind("<KeyPress-space>", lambda e: (self.command(), "break")[1])
        self.bind("<FocusIn>", lambda e: self.itemconfig(self.rect, outline=TEXT))
        self.bind("<FocusOut>", lambda e: self.itemconfig(self.rect, outline=BORDER))


BRAND_TOP, BRAND_BOTTOM = "#10291c", "#0a100d"
_backgrounds: dict[int, str] = {}


_TOP_RGB, _BOTTOM_RGB = _rgb(BRAND_TOP), _rgb(BRAND_BOTTOM)
_GLOWS = ((40, 40, 260, _rgb(ACCENT), 0.20), (BRAND_W, -30, 240, _rgb(BLUE), 0.12))


def brand_rgb(x: float, y: float, height: int) -> list:
    """Couleur du panneau de gauche en un point : degrade vertical et deux halos (le second
    est ancre en bas, d'ou la position negative comptee depuis le bas)."""
    t = y / height
    rgb = [a + (b - a) * t for a, b in zip(_TOP_RGB, _BOTTOM_RGB)]
    for gx, gy, radius, tint, strength in _GLOWS:
        gy = gy if gy >= 0 else height + gy
        d2 = ((x - gx) ** 2 + (y - gy) ** 2) / (radius * radius)
        if d2 < 1:
            k = strength * (1 - math.sqrt(d2)) ** 2
            rgb = [c + (v - c) * k for c, v in zip(rgb, tint)]
    return rgb


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(round(c) for c in rgb)


def brand_background(height: int) -> str:
    """Pixels du fond (a demi-resolution) au format de PhotoImage.put, calcules une fois."""
    if height not in _backgrounds:
        rows = []
        for j in range((height + 1) // 2):
            row = " ".join(_hex(brand_rgb(i * 2 + 1, j * 2 + 1, height))
                           for i in range(BRAND_W // 2))
            rows.append("{" + row + "}")
        _backgrounds[height] = " ".join(rows)
    return _backgrounds[height]


class Brand(Timers, tk.Canvas):
    """Panneau de gauche : degrade avec halos, bouclier anime, nom et points forts."""

    FEATURES = (("bolt", "Protection en temps réel", "Téléchargements, Bureau, clés USB"),
                ("shield", "Analyse rapide en un clic", "Signatures, YARA et ClamAV"),
                ("cloud-off", "Connexion 100 % locale", "Aucun compte en ligne"))

    def __init__(self, parent):
        super().__init__(parent, width=BRAND_W, height=HEIGHT, highlightthickness=0, bd=0,
                         bg=BRAND_BOTTOM)
        self.bg_item = self.create_image(0, 0, anchor="nw")
        self.bg_height = 0
        self.cx, self.cy = BRAND_W / 2, 140
        self.ring_bg = _hex(brand_rgb(self.cx, self.cy, HEIGHT))
        self.rings = [self.create_oval(0, 0, 0, 0, outline=ACCENT, width=2) for _ in range(3)]
        draw_emblem(self, self.cx, self.cy, 1.15)
        self.create_text(self.cx, 236, text="FreeAV", fill=TEXT, font=(FONT, 24, "bold"))
        self.create_text(self.cx, 268, text="Antivirus gratuit et libre", fill=MUTED,
                         font=(FONT, 10))
        y = 336
        for icon, title, detail in self.FEATURES:
            round_rect(self, 34, y - 15, 64, y + 15, 9, outline="",
                       fill=mix(_hex(brand_rgb(49, y, HEIGHT)), ACCENT, 0.16))
            draw_icon(self, icon, 49, y, ACCENT_LIGHT)
            self.create_text(78, y - 8, text=title, anchor="w", fill=TEXT, font=(FONT, 10, "bold"))
            self.create_text(78, y + 9, text=detail, anchor="w", fill=MUTED, font=(FONT, 8))
            y += 56
        self.footer = self.create_text(self.cx, HEIGHT - 24, fill=FAINT, font=(FONT, 8),
                                       text=f"FreeAV {__version__}  \u00b7  logiciel libre GPL-3.0")
        self._paint_background(HEIGHT)
        self.bind("<Configure>", lambda e: self._paint_background(e.height))
        self.phase = 0.0
        self._animate()

    def _paint_background(self, height: int):
        """Redessine le fond si la fenetre a du grandir pour un ecran plus long."""
        if height < 100 or height == self.bg_height:
            return
        self.bg_height = height
        small = tk.PhotoImage(master=self, width=BRAND_W // 2, height=(height + 1) // 2)
        small.put(brand_background(height))
        self.image = small.zoom(2, 2)
        self.itemconfig(self.bg_item, image=self.image)
        self.coords(self.footer, self.cx, height - 24)

    def _animate(self):
        if not self.winfo_exists():
            return
        self.phase = (self.phase + 0.012) % 1.0
        for k, ring in enumerate(self.rings):
            t = (self.phase + k / 3) % 1.0
            r = 46 + 46 * t
            self.coords(ring, self.cx - r, self.cy - r, self.cx + r, self.cy + r)
            self.itemconfig(ring, outline=mix(ACCENT, self.ring_bg, 0.25 + 0.75 * t),
                            width=2.5 - 1.5 * t)
        self.later(40, self._animate)


# -- fenetre ----------------------------------------------------------------------------

def _set_icon(window: tk.Tk) -> None:
    icon = Path(__file__).parent / "data" / "freeav.ico"  # ajoutee par la version Windows
    if icon.is_file():
        try:
            window.iconbitmap(default=str(icon))
        except tk.TclError:
            pass


class AccessWindow(Timers, tk.Toplevel):
    """Fenetre de connexion. Modes :
      - "open" : au lancement de FreeAV (result True si connecte) ;
      - "lock" : fenetre principale verrouillee (la croix reduit la fenetre) ;
      - "manage" : confirmer son identite puis changer les reglages de connexion ;
      - "setup" : creer l'acces ; "offer" : le proposer a la premiere ouverture.
    """

    TITLES = {"open": "Connexion", "lock": "Verrouillé", "manage": "Connexion",
              "setup": "Protéger l'accès", "offer": "Protéger l'accès"}

    def __init__(self, master, mode: str = "open"):
        super().__init__(master)
        self.mode = mode
        self.result = None
        self.title(f"FreeAV - {self.TITLES[mode]}")
        self.configure(bg=SURFACE)
        self.resizable(False, False)
        x = max(0, (self.winfo_screenwidth() - WIDTH) // 2)
        y = max(0, (self.winfo_screenheight() - HEIGHT) // 3)
        self.height = HEIGHT
        self.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
        self.brand = Brand(self)
        self.brand.pack(side="left", fill="y")
        self.body = tk.Frame(self, bg=SURFACE, padx=48, pady=24)
        self.body.pack(side="left", fill="both", expand=True)
        self.content = None
        self.primary: Button | None = None
        self.jobs: queue.Queue = queue.Queue()
        self.busy = False
        self._shaking = False
        self.password = ""
        account = login.load() if mode == "manage" else None
        self.nickname = account.nickname if account else ""  # deja connecte : pseudo connu
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Return>", self._enter)
        self.bind("<KP_Enter>", self._enter)
        if mode not in ("open", "lock"):
            self.bind("<Escape>", lambda e: self.close())
        self.later(60, self._to_front)
        {"open": self.show_login, "lock": self.show_login, "manage": self.show_login,
         "setup": self.show_account, "offer": self.show_offer}[mode]()

    # - mecanique commune -

    def _to_front(self):
        if self.winfo_exists():
            self.deiconify()
            self.lift()
            self.focus_force()

    def screen(self) -> tk.Frame:
        """Nouvel ecran : remplace le contenu du panneau de droite."""
        if self.content is not None:
            self.content.destroy()
        self.content = tk.Frame(self.body, bg=SURFACE)
        self.content.pack(expand=True, fill="x")
        self.primary = None
        self.later(0, self._fit)
        return self.content

    def _fit(self):
        """Agrandit la fenetre si l'ecran qui vient d'etre construit ne tient pas (textes plus
        longs, grandes polices) ; elle ne rapetisse jamais, pour ne pas sauter d'un ecran a
        l'autre."""
        if not self.winfo_exists() or self.content is None:
            return
        self.update_idletasks()  # tailles demandees a jour
        need = self.content.winfo_reqheight() + 2 * 24 + 16
        if need > self.height:
            self.height = min(need, self.winfo_screenheight() - 80)
            self.geometry(f"{WIDTH}x{self.height}")

    def focus_later(self, widget) -> None:
        """Donne le focus a un champ une fois l'ecran affiche (s'il existe encore)."""
        def go():
            if widget.winfo_exists():
                widget.focus()
        self.later(80, go)

    def steps(self, parent, current: int, total: int) -> None:
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", pady=(0, 14))
        c = tk.Canvas(row, width=total * 34, height=4, bg=SURFACE, highlightthickness=0, bd=0)
        c.pack(side="left")
        for i in range(total):
            round_rect(c, i * 34, 0, i * 34 + 28, 4, 2, outline="",
                       fill=ACCENT if i < current else BORDER)
        tk.Label(row, text=f"ÉTAPE {current} SUR {total}", bg=SURFACE, fg=FAINT,
                 font=(FONT, 8, "bold")).pack(side="left", padx=(10, 0))

    def heading(self, parent, title: str, subtitle: str = "") -> None:
        tk.Label(parent, text=title, bg=SURFACE, fg=TEXT, font=(FONT, 18, "bold"), anchor="w",
                 justify="left", wraplength=CONTENT_W).pack(fill="x")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=SURFACE, fg=MUTED, font=(FONT, 10), anchor="w",
                     justify="left", wraplength=CONTENT_W).pack(fill="x", pady=(4, 0))
        tk.Frame(parent, bg=SURFACE, height=18).pack(fill="x")

    def field(self, parent, *args, pady=(0, 12), **kw) -> Field:
        f = Field(parent, *args, **kw)
        f.pack(anchor="w", pady=pady)
        return f

    def button(self, parent, text, command, kind="primary", width=CONTENT_W, primary=True,
               **pack) -> Button:
        b = Button(parent, text, command, kind=kind, width=width)
        b.pack(**(pack or {"anchor": "w"}))
        if primary:
            self.primary = b
        return b

    def link_row(self, parent, left=None, right=None, pady=(14, 0)) -> None:
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", pady=pady)
        if left:
            Link(row, *left).pack(side="left")
        if right:
            Link(row, *right).pack(side="right")

    def note(self, parent, text: str, icon: str = "lock", pady=(16, 0)) -> None:
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", pady=pady)
        c = tk.Canvas(row, width=20, height=20, bg=SURFACE, highlightthickness=0, bd=0)
        c.pack(side="left", anchor="n")
        draw_icon(c, icon, 10, 10, FAINT, w=1.4)
        tk.Label(row, text=text, bg=SURFACE, fg=FAINT, font=(FONT, 8), justify="left",
                 anchor="w", wraplength=CONTENT_W - 28).pack(side="left", padx=(6, 0))

    def _enter(self, event=None):
        if self.primary is not None and self.primary.winfo_exists():
            self.primary.invoke()

    def work(self, fn, done, text: str = "Vérification") -> None:
        """Lance fn() dans un fil (scrypt prend un instant), puis done(resultat, erreur)."""
        if self.busy:
            return
        self.busy = True
        button = self.primary
        if button is not None:
            button.set_busy(True, text)

        def target():
            try:
                self.jobs.put((done, button, fn(), None))
            except Exception as exc:  # remis a l'interface, jamais perdu
                self.jobs.put((done, button, None, exc))

        threading.Thread(target=target, daemon=True).start()
        self.later(30, self._poll)

    def _poll(self):
        if not self.winfo_exists():
            return
        try:
            done, button, result, exc = self.jobs.get_nowait()
        except queue.Empty:
            self.later(30, self._poll)
            return
        self.busy = False
        if button is not None and button.winfo_exists():
            button.set_busy(False)
        done(result, exc)

    def shake(self):
        """Petit tremblement de la fenetre apres une erreur."""
        if self._shaking:
            return
        try:
            x, y = (int(v) for v in self.geometry().split("+")[1:3])
        except ValueError:
            return
        self._shaking = True
        offsets = (10, -9, 7, -5, 3, -1, 0)

        def step(i=0):
            if not self.winfo_exists():
                return
            if i < len(offsets):
                self.geometry(f"+{x + offsets[i]}+{y}")
                self.later(28, step, i + 1)
            else:
                self._shaking = False
        step()

    def error(self, notice: Notice, exc: Exception, *fields) -> None:
        """Affiche un refus (ou une erreur inattendue) et secoue la fenetre."""
        if isinstance(exc, login.LoginError):
            notice.show(str(exc))
        elif isinstance(exc, OSError):
            notice.show(f"Impossible d'enregistrer : {exc}")
        else:
            notice.show(f"Erreur inattendue : {exc}")
        for f in fields:
            f.mark_error()
        if isinstance(exc, login.Locked):
            self.countdown(notice, exc.wait)
        self.shake()

    def countdown(self, notice: Notice, wait: int) -> None:
        """Bouton grise et compte a rebours pendant l'attente imposee apres trop d'essais."""
        button = self.primary
        if button is None:
            return
        button.set_enabled(False)

        def tick(left=wait):
            if not button.winfo_exists():
                return
            if left <= 0:
                button.set_enabled(True)
                notice.show("Vous pouvez réessayer.", "info")
                return
            notice.show(f"Trop d'essais. Réessayez dans {left} s.", "warn")
            self.later(1000, tick, left - 1)
        tick()

    def finish(self, result) -> None:
        self.result = result
        self.destroy()

    def close(self) -> None:
        """La croix : fermer l'ecran de connexion ferme FreeAV (modes "open" et "lock",
        comme la croix de la fenetre principale) ou annule (reglages)."""
        self.finish(False if self.mode in ("open", "lock") else None)

    def check_mark(self, parent, size: int = 84) -> tk.Canvas:
        """Cercle et coche qui se dessinent."""
        c = tk.Canvas(parent, width=size, height=size, bg=SURFACE, highlightthickness=0, bd=0)
        circle = c.create_oval(size / 2, size / 2, size / 2, size / 2, fill=ACCENT_SOFT,
                               outline=ACCENT, width=2)
        mark = c.create_line(0, 0, 0, 0, fill=ACCENT_LIGHT, width=5, capstyle="round",
                             joinstyle="round", state="hidden")
        s = size / 84
        points = [(27 * s, 43 * s), (38 * s, 54 * s), (58 * s, 32 * s)]

        def step(i=0):
            if not c.winfo_exists():
                return
            if i <= 8:
                r = (size / 2 - 3) * (1 - (1 - i / 8) ** 3)
                c.coords(circle, size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r)
            else:
                t = min(1.0, (i - 8) / 8)
                seg = t * 2
                pts = [points[0]]
                if seg <= 1:
                    pts.append(_lerp(points[0], points[1], seg))
                else:
                    pts += [points[1], _lerp(points[1], points[2], seg - 1)]
                c.coords(mark, *[v for p in pts for v in p])
                c.itemconfig(mark, state="normal")
                if t >= 1:
                    return
            self.later(22, step, i + 1)
        step()
        return c

    # - connexion -

    def show_login(self, message: str | None = None, kind: str = "error"):
        c = self.screen()
        self.password = ""
        account = login.load()
        titles = {
            "open": ("Bon retour", "Entrez votre pseudo et votre mot de passe pour ouvrir FreeAV."),
            "lock": ("FreeAV est verrouillé", "La protection continue en arrière-plan. "
                     "Connectez-vous pour rouvrir la fenêtre."),
            "manage": ("Confirmez que c'est vous", "Entrez votre mot de passe pour modifier "
                       "la connexion à FreeAV."),
        }
        self.heading(c, *titles.get(self.mode, titles["open"]))
        self.f_nick = self.field(c, "Pseudo", icon="user")
        self.f_pass = self.field(c, "Mot de passe", icon="lock", secret=True, pady=(0, 6))
        self.link_row(c, right=("Mot de passe oublié ?", self.show_forgot), pady=(0, 16))
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        label = {"lock": "Déverrouiller", "manage": "Continuer"}.get(self.mode, "Se connecter")
        self.button(c, label, self.submit_login)
        if self.mode == "manage":
            self.link_row(c, left=("Annuler", lambda: self.finish(None)))
        elif self.mode == "lock":
            self.link_row(c, left=("Quitter FreeAV", lambda: self.finish(False)))
        self.note(c, "Connexion locale : votre mot de passe et vos codes restent sur ce PC.")
        if self.nickname:
            self.f_nick.set(self.nickname)
        if message:
            self.notice.show(message, kind)
        if account and (wait := login.wait_time(account)):
            self.countdown(self.notice, wait)
        target = self.f_pass if self.nickname else self.f_nick
        self.focus_later(target)

    def submit_login(self):
        nickname, password = self.f_nick.get().strip(), self.f_pass.get()
        if not nickname or not password:
            self.notice.show("Entrez votre pseudo et votre mot de passe.")
            (self.f_pass if nickname else self.f_nick).mark_error()
            self.shake()
            return
        self.nickname, self.password = nickname, password
        self.work(lambda: login.verify(nickname, password), self._after_login)

    def _after_login(self, result, exc):
        if isinstance(exc, login.CodeRequired):
            self.show_code()
        elif exc is not None:
            self.password = ""
            self.f_pass.clear()
            self.error(self.notice, exc, self.f_pass)
            self.f_pass.focus()
        else:
            self._unlocked(result)

    def show_code(self, recovery: bool = False):
        c = self.screen()
        self.recovery_mode = recovery
        if recovery:
            self.heading(c, "Code de secours", "Entrez l'un des codes de secours notés lors de "
                         "la configuration. Chaque code ne sert qu'une fois.")
            self.f_code = self.field(c, "Code de secours", icon="key", mono=True)
        else:
            self.heading(c, "Vérification en deux étapes", "Ouvrez Google Authenticator ou "
                         "Microsoft Authenticator et entrez le code à 6 chiffres de FreeAV.")
            self.boxes = CodeBoxes(c, lambda code: self.submit_code())
            self.boxes.pack(anchor="w")
            row = tk.Frame(c, bg=SURFACE)
            row.pack(fill="x", pady=(12, 16))
            Countdown(row).pack(side="left")
            tk.Label(row, text="Le code change toutes les 30 secondes.", bg=SURFACE, fg=MUTED,
                     font=(FONT, 9)).pack(side="left", padx=(8, 0))
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        self.button(c, "Valider", self.submit_code)
        self.link_row(c, left=("Retour", lambda: self.show_login()),
                      right=("Utiliser l'application" if recovery else
                             "Utiliser un code de secours", lambda: self.show_code(not recovery)))
        self.focus_later(self.f_code if recovery else self.boxes)

    def submit_code(self):
        if self.busy:
            return
        code = self.f_code.get() if self.recovery_mode else self.boxes.get()
        if len(code.strip()) < 6:
            self.notice.show("Entrez le code en entier.")
            self.shake()
            return
        self.work(lambda: login.verify(self.nickname, self.password, code), self._after_code)

    def _after_code(self, result, exc):
        if isinstance(exc, login.CodeRequired):  # mot de passe change entre-temps
            self.show_login()
        elif exc is not None:
            if self.recovery_mode:
                self.error(self.notice, exc, self.f_code)
                self.f_code.focus()
            else:
                self.boxes.clear(error=True)
                self.error(self.notice, exc)
        else:
            self._unlocked(result)

    def _unlocked(self, result: login.Unlock):
        self.password = ""
        if self.mode == "manage":
            self.show_manage("Il vous reste %d code(s) de secours." % result.recovery_left
                             if result.recovery_used else None)
            return
        c = self.screen()
        self.check_mark(c).pack(anchor="w", pady=(0, 16))
        self.heading(c, f"Bienvenue, {result.account.nickname}",
                     "Ouverture de FreeAV…" if not result.recovery_used else
                     f"Code de secours utilisé : il vous en reste {result.recovery_left}. "
                     "Créez-en de nouveaux depuis le bouton « Connexion » quand vous voulez.")
        if result.recovery_used:
            self.button(c, "Continuer", lambda: self.finish(True))
        else:
            self.later(750, self.finish, True)

    # - mot de passe oublie -

    def show_forgot(self):
        c = self.screen()
        account = login.load()
        otp = bool(account and account.otp)
        self.heading(c, "Mot de passe oublié", (
            "Prouvez que c'est vous avec le code à 6 chiffres de votre application "
            "d'authentification ou avec un code de secours, puis choisissez un nouveau mot "
            "de passe." if otp else "Prouvez que c'est vous avec l'un de vos codes de secours, "
            "puis choisissez un nouveau mot de passe."))
        row = tk.Frame(c, bg=SURFACE)
        row.pack(fill="x", pady=(0, 12))
        self.f_nick = Field(row, "Pseudo", icon="user", width=HALF_W)
        self.f_nick.pack(side="left")
        self.f_code = Field(row, "Code OTP ou de secours" if otp else "Code de secours",
                            icon="key", width=HALF_W, mono=True)
        self.f_code.pack(side="right")
        self.f_new = self.field(c, "Nouveau mot de passe", icon="lock", secret=True, pady=(0, 8),
                                on_change=lambda v: self.meter.update_for(v, self.f_nick.get()))
        self.meter = StrengthMeter(c)
        self.meter.pack(fill="x", pady=(0, 12))
        self.f_confirm = self.field(c, "Confirmez le mot de passe", icon="lock", secret=True)
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        self.button(c, "Changer le mot de passe", self.submit_forgot)
        self.link_row(c, left=("Retour à la connexion", lambda: self.show_login()),
                      right=("Plus aucun code ?", self.show_no_code))
        if self.nickname:
            self.f_nick.set(self.nickname)
        self.focus_later(self.f_code if self.nickname else self.f_nick)

    def submit_forgot(self):
        nickname, code = self.f_nick.get().strip(), self.f_code.get()
        new, confirm = self.f_new.get(), self.f_confirm.get()
        if not nickname or not code.strip():
            self.notice.show("Entrez votre pseudo et un code.")
            (self.f_code if nickname else self.f_nick).mark_error()
            return self.shake()
        if problem := login.password_problem(new, nickname):
            self.notice.show(problem)
            self.f_new.mark_error()
            return self.shake()
        if new != confirm:
            self.notice.show("Les deux mots de passe ne sont pas identiques.")
            self.f_confirm.mark_error()
            return self.shake()
        self.nickname = nickname
        self.work(lambda: login.reset_password(nickname, code, new), self._after_forgot)

    def _after_forgot(self, result, exc):
        if exc is not None:
            self.f_code.clear()
            self.error(self.notice, exc, self.f_code)
            self.f_code.focus()
            return
        left = (f" Il vous reste {result.recovery_left} code(s) de secours."
                if result.recovery_used else "")
        self.show_done("Mot de passe changé",
                       "Connectez-vous maintenant avec votre nouveau mot de passe." + left,
                       "Se connecter", lambda: self.show_login())

    def show_no_code(self):
        self.show_message(
            "Plus aucun code ?",
            "Sans code de votre application ni code de secours, le mot de passe ne peut pas "
            "être changé : personne d'autre ne connaît vos codes, c'est ce qui protège "
            "FreeAV.\n\nLa connexion n'est qu'un verrou pour la fenêtre de FreeAV : pour la "
            f"retirer, supprimez le fichier {login.LOGIN_FILE}. Vos réglages, la quarantaine "
            "et la protection ne sont pas touchés.", self.show_forgot)

    # - creation de l'acces -

    def show_offer(self):
        c = self.screen()
        pill = tk.Label(c, text="  NOUVEAU  ", bg=ACCENT_SOFT, fg=ACCENT_LIGHT,
                        font=(FONT, 8, "bold"), pady=2)
        pill.pack(anchor="w", pady=(0, 12))
        self.heading(c, "Protégez l'accès à FreeAV", "Sans votre pseudo et votre mot de passe, "
                     "personne ne pourra ouvrir FreeAV, sortir un fichier de la quarantaine ni "
                     "couper la protection depuis la fenêtre.")
        for icon, text in (("user", "Un pseudo et un mot de passe à l'ouverture de FreeAV"),
                           ("phone", "Un code à 6 chiffres sur votre téléphone (OTP), en option"),
                           ("bolt", "La protection en arrière-plan continue sans connexion"),
                           ("cloud-off", "Tout reste sur ce PC : aucun compte en ligne")):
            row = tk.Frame(c, bg=SURFACE)
            row.pack(fill="x", pady=(0, 10))
            ic = tk.Canvas(row, width=30, height=30, bg=SURFACE, highlightthickness=0, bd=0)
            ic.pack(side="left")
            round_rect(ic, 0, 0, 30, 30, 8, fill=ACCENT_SOFT, outline="")
            draw_icon(ic, icon, 15, 15, ACCENT_LIGHT)
            tk.Label(row, text=text, bg=SURFACE, fg=TEXT, font=(FONT, 10)).pack(side="left",
                                                                                 padx=(12, 0))
        buttons = tk.Frame(c, bg=SURFACE)
        buttons.pack(fill="x", pady=(14, 0))
        self.button(buttons, "Configurer", self.show_account, width=HALF_W, side="left")
        Button(buttons, "Plus tard", lambda: self.finish(None), kind="secondary",
               width=HALF_W).pack(side="right")
        self.note(c, "Vous pourrez l'activer à tout moment avec le bouton « Connexion » de la "
                  "fenêtre principale.", icon="shield")

    def show_account(self):
        c = self.screen()
        self.want_otp = getattr(self, "want_otp", True)
        self.steps_row = tk.Frame(c, bg=SURFACE)
        self.steps_row.pack(fill="x")
        self._draw_steps(1)
        self.heading(c, "Créez votre accès", "Votre mot de passe n'est jamais enregistré en "
                     "clair : FreeAV n'en garde qu'une empreinte.")
        self.f_nick = self.field(c, "Pseudo", icon="user",
                                 on_change=lambda v: self.meter.update_for(self.f_pass.get(), v))
        row = tk.Frame(c, bg=SURFACE)
        row.pack(fill="x", pady=(0, 8))
        self.f_pass = Field(row, "Mot de passe", icon="lock", secret=True, width=HALF_W,
                            on_change=lambda v: self.meter.update_for(v, self.f_nick.get()))
        self.f_pass.pack(side="left")
        self.f_confirm = Field(row, "Confirmation", icon="lock", secret=True, width=HALF_W)
        self.f_confirm.pack(side="right")
        self.meter = StrengthMeter(c)
        self.meter.pack(fill="x", pady=(0, 14))
        otp = tk.Frame(c, bg=FIELD, padx=14, pady=10, highlightthickness=1,
                       highlightbackground=BORDER)
        otp.pack(fill="x", pady=(0, 14))
        Switch(otp, self.want_otp, self._otp_switched).pack(side="right")
        words = tk.Frame(otp, bg=FIELD)
        words.pack(side="left", fill="x")
        title = tk.Frame(words, bg=FIELD)
        title.pack(anchor="w")
        tk.Label(title, text="Code à usage unique (OTP)", bg=FIELD, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(side="left")
        tk.Label(title, text=" RECOMMANDÉ ", bg=ACCENT_SOFT, fg=ACCENT_LIGHT,
                 font=(FONT, 7, "bold")).pack(side="left", padx=(8, 0))
        tk.Label(words, text="Avec Google Authenticator ou Microsoft Authenticator", bg=FIELD,
                 fg=MUTED, font=(FONT, 8)).pack(anchor="w")
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        self.button(c, "Continuer", self.submit_account)
        if self.mode == "offer":
            self.link_row(c, left=("Retour", self.show_offer))
        else:
            self.link_row(c, left=("Annuler", lambda: self.finish(None)))
        if self.nickname:
            self.f_nick.set(self.nickname)
        self.focus_later(self.f_nick)

    def _draw_steps(self, current: int):
        for child in self.steps_row.winfo_children():
            child.destroy()
        self.steps(self.steps_row, current, 3 if self.want_otp else 2)

    def _otp_switched(self, on: bool):
        self.want_otp = on
        self._draw_steps(1)

    def submit_account(self):
        nickname, password = self.f_nick.get().strip(), self.f_pass.get()
        if problem := login.nickname_problem(nickname):
            self.notice.show(problem)
            self.f_nick.mark_error()
            return self.shake()
        if problem := login.password_problem(password, nickname):
            self.notice.show(problem)
            self.f_pass.mark_error()
            return self.shake()
        if password != self.f_confirm.get():
            self.notice.show("Les deux mots de passe ne sont pas identiques.")
            self.f_confirm.mark_error()
            return self.shake()
        self.nickname, self.password = nickname, password
        if self.want_otp:
            self.secret = login.new_otp_secret()
            self.show_qr()
        else:
            self.work(lambda: login.create(nickname, password), self._created,
                      text="Enregistrement")

    def show_qr(self, enabling: bool = False):
        c = self.screen()
        self.enabling = enabling
        if enabling:
            self.secret = login.new_otp_secret()
        else:
            self.steps(c, 2, 3)
        self.heading(c, "Scannez ce QR code", "Dans votre application d'authentification, "
                     "touchez « + », puis « Scanner un code QR ».")
        nickname = self.nickname or (login.load() or login.Account("FreeAV", {})).nickname
        row = tk.Frame(c, bg=SURFACE)
        row.pack(fill="x", pady=(0, 14))
        QrView(row, login.otp_uri(self.secret, nickname)).pack(side="left", anchor="n")
        side = tk.Frame(row, bg=SURFACE)
        side.pack(side="left", fill="both", expand=True, padx=(20, 0))
        tk.Label(side, text="Pas de caméra ?", bg=SURFACE, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        tk.Label(side, text="Choisissez « Saisir une clé » et recopiez :", bg=SURFACE, fg=MUTED,
                 font=(FONT, 9), wraplength=200, justify="left").pack(anchor="w", pady=(2, 8))
        groups = login.format_secret(self.secret).split()
        key = tk.Label(side, text=" ".join(groups[:4]) + "\n" + " ".join(groups[4:]),
                       bg=FIELD, fg=TEXT, font=(MONO, 11, "bold"), justify="left", padx=10,
                       pady=8)
        key.pack(anchor="w")
        Link(side, "Copier la clé", lambda: self._copy(self.secret, "Clé copiée.")).pack(
            anchor="w", pady=(8, 0))
        tk.Label(side, text=f"Compte : {nickname} (FreeAV)\nType : basé sur l'heure",
                 bg=SURFACE, fg=FAINT, font=(FONT, 8), justify="left").pack(anchor="w",
                                                                             pady=(8, 0))
        tk.Label(c, text="Entrez le code affiché par l'application", bg=SURFACE, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 6))
        self.boxes = CodeBoxes(c, lambda code: self.submit_qr())
        self.boxes.pack(anchor="w", pady=(0, 12))
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        bottom = tk.Frame(c, bg=SURFACE)
        bottom.pack(fill="x")
        self.button(bottom, "Vérifier", self.submit_qr, width=170, side="right")
        Link(bottom, "Retour", (lambda: self.show_manage()) if enabling else
             self.show_account).pack(side="left")
        self.focus_later(self.boxes)

    def _copy(self, text: str, message: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.notice.show(message, "success")

    def submit_qr(self):
        if self.busy:
            return
        code = self.boxes.get()
        if len(code) < 6:
            self.notice.show("Entrez les 6 chiffres du code.")
            return self.shake()
        if self.enabling:
            self.work(lambda: login.enable_otp(self.secret, code), self._otp_enabled)
        else:
            nickname, password, secret = self.nickname, self.password, self.secret
            self.work(lambda: login.create(nickname, password, secret, code), self._created,
                      text="Enregistrement")

    def _otp_enabled(self, _result, exc):
        if exc is not None:
            self.boxes.clear(error=True)
            return self.error(self.notice, exc)
        self.show_manage("Code OTP activé : FreeAV le demandera à chaque connexion.")

    def _created(self, codes, exc):
        if exc is not None:
            if self.want_otp and hasattr(self, "boxes") and self.boxes.winfo_exists():
                self.boxes.clear(error=True)
            return self.error(self.notice, exc)
        self.password = ""
        otp = self.want_otp

        def done():
            self.show_done("FreeAV est protégé", "À la prochaine ouverture, FreeAV demandera "
                           "votre pseudo et votre mot de passe" + (", puis le code de votre "
                                                                   "téléphone." if otp else "."),
                           "Terminer", lambda: self.finish(True))
        self.show_codes(codes, done, step=(3, 3) if otp else (2, 2))

    def show_codes(self, codes: list[str], then, step=None):
        c = self.screen()
        if step:
            self.steps(c, *step)
        self.heading(c, "Notez vos codes de secours", "Si vous oubliez votre mot de passe ou "
                     "perdez votre téléphone, chaque code permet une fois de reprendre la main. "
                     "Ils ne seront plus affichés.")
        panel = tk.Canvas(c, width=CONTENT_W, height=150, bg=SURFACE, highlightthickness=0,
                          bd=0)
        panel.pack(anchor="w", pady=(0, 12))
        round_rect(panel, 1, 1, CONTENT_W - 1, 149, 12, fill=FIELD, outline=BORDER, width=1.5)
        for i, code in enumerate(codes):
            x = 40 + (i % 2) * (CONTENT_W / 2)
            y = 30 + (i // 2) * 30
            panel.create_text(x - 16, y, text=f"{i + 1}.", anchor="e", fill=FAINT,
                              font=(FONT, 9))
            panel.create_text(x, y, text=code, anchor="w", fill=TEXT, font=(MONO, 13, "bold"))
        text = "Codes de secours FreeAV (chacun ne sert qu'une fois)\n" + "\n".join(codes) + "\n"
        actions = tk.Frame(c, bg=SURFACE)
        actions.pack(fill="x", pady=(0, 12))
        Button(actions, "Copier", lambda: self._copy(text, "Codes copiés : collez-les dans un "
                                                     "endroit sûr."), kind="secondary",
               width=HALF_W, height=38).pack(side="left")
        Button(actions, "Enregistrer…", lambda: self._save_codes(text),
               kind="secondary", width=HALF_W, height=38).pack(side="right")
        self.confirm_box = CheckBox(c, "J'ai mis ces codes en lieu sûr",
                                    lambda on: self.primary.set_enabled(on))
        self.confirm_box.pack(anchor="w", pady=(0, 12))
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        self.button(c, "Terminer", then)
        self.primary.set_enabled(False)

    def _save_codes(self, text: str):
        name = filedialog.asksaveasfilename(
            parent=self, title="Enregistrer les codes de secours", defaultextension=".txt",
            initialfile="codes-de-secours-FreeAV.txt", filetypes=[("Texte", "*.txt")])
        if not name:
            return
        try:
            Path(name).write_text(text, encoding="utf-8")
        except OSError as exc:
            self.notice.show(f"Impossible d'enregistrer : {exc}")
            return
        self.notice.show(f"Codes enregistrés dans {name}. Gardez ce fichier hors du PC "
                         "(clé USB, papier...).", "success")

    def show_done(self, title: str, text: str, button: str, command):
        c = self.screen()
        self.check_mark(c).pack(anchor="w", pady=(0, 16))
        self.heading(c, title, text)
        self.button(c, button, command)
        self.focus_later(self.primary)

    def show_message(self, title: str, text: str, back):
        c = self.screen()
        self.heading(c, title, text)
        self.button(c, "Retour", back, kind="secondary")

    # - reglages -

    def show_manage(self, message: str | None = None):
        account = login.load()
        if account is None:
            return self.finish(True)
        c = self.screen()
        self.heading(c, "Connexion à FreeAV", f"Connecté en tant que « {account.nickname} ». "
                     "Ces réglages restent sur ce PC.")
        summary = tk.Canvas(c, width=CONTENT_W, height=64, bg=SURFACE, highlightthickness=0,
                            bd=0)
        summary.pack(anchor="w", pady=(0, 12))
        half = CONTENT_W / 2
        for i, (label, value, good) in enumerate((
                ("Code OTP", "Activé" if account.otp else "Désactivé", account.otp),
                ("Codes de secours", f"{len(account.recovery)} sur {login.RECOVERY_CODES}",
                 len(account.recovery) > 2))):
            x = i * (half + 6)
            round_rect(summary, x + 1, 1, x + half - 7, 63, 10, fill=FIELD, outline=BORDER,
                       width=1.5)
            summary.create_text(x + 16, 20, text=label.upper(), anchor="w", fill=FAINT,
                                font=(FONT, 7, "bold"))
            summary.create_oval(x + 16, 38, x + 24, 46, fill=ACCENT if good else WARN,
                                outline="")
            summary.create_text(x + 32, 42, text=value, anchor="w", fill=TEXT,
                                font=(FONT, 11, "bold"))
        rows = [("lock", "Changer le mot de passe", "Le pseudo reste le même",
                 self.show_change_password, False)]
        if account.otp:
            rows.append(("phone", "Désactiver le code OTP", "Le mot de passe suffira",
                         lambda: self.show_confirm(
                             "Désactiver le code OTP ?", "FreeAV ne demandera plus que votre "
                             "pseudo et votre mot de passe. Vous pourrez le réactiver.",
                             "Désactiver", lambda: self._apply(login.disable_otp,
                                                               "Code OTP désactivé.")), False))
        else:
            rows.append(("phone", "Activer le code OTP", "Google ou Microsoft Authenticator",
                         lambda: self.show_qr(enabling=True), False))
        rows += [("key", "Nouveaux codes de secours", "Les anciens ne marcheront plus",
                  lambda: self.show_confirm(
                      "Remplacer vos codes de secours ?", "Vous recevrez 8 nouveaux codes. Les "
                      "anciens ne marcheront plus.", "Remplacer", self._renew), False),
                 ("shield", "Retirer la connexion", "FreeAV s'ouvrira sans mot de passe",
                  lambda: self.show_confirm(
                      "Retirer la connexion ?", "FreeAV s'ouvrira de nouveau sans pseudo ni mot "
                      "de passe. La protection n'est pas touchée.", "Retirer", self._remove,
                      danger=True), True)]
        for icon, text, detail, command, danger in rows:
            ActionRow(c, icon, text, detail, command, danger).pack(anchor="w", pady=(0, 8))
        self.notice = Notice(c)
        self.notice.pack(fill="x", pady=(4, 0))
        if message:
            self.notice.show(message, "success")
        self.button(c, "Fermer", lambda: self.finish(True), kind="secondary")

    def show_confirm(self, title: str, text: str, label: str, command, danger: bool = False):
        c = self.screen()
        self.heading(c, title, text)
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        buttons = tk.Frame(c, bg=SURFACE)
        buttons.pack(fill="x")
        Button(buttons, "Annuler", lambda: self.show_manage(), kind="secondary",
               width=HALF_W).pack(side="left")
        self.button(buttons, label, command, kind="danger" if danger else "primary",
                    width=HALF_W, side="right")

    def _apply(self, fn, message: str):
        self.work(fn, lambda _r, exc: self.error(self.notice, exc) if exc
                  else self.show_manage(message), text="Enregistrement")

    def _renew(self):
        self.work(login.renew_recovery_codes, lambda codes, exc: self.error(self.notice, exc)
                  if exc else self.show_codes(codes, lambda: self.show_manage(
                      "Nouveaux codes de secours enregistrés.")), text="Enregistrement")

    def _remove(self):
        def done(_r, exc):
            if exc:
                return self.error(self.notice, exc)
            self.show_done("Connexion retirée", "FreeAV s'ouvrira de nouveau sans mot de passe. "
                           "Vous pouvez la réactiver à tout moment.", "Fermer",
                           lambda: self.finish(True))
        self.work(login.disable, done, text="Enregistrement")

    def show_change_password(self):
        c = self.screen()
        account = login.load()
        nickname = account.nickname if account else ""
        self.heading(c, "Nouveau mot de passe", "Choisissez un mot de passe d'au moins 12 "
                     "caractères, par exemple trois mots séparés par des tirets.")
        self.f_new = self.field(c, "Nouveau mot de passe", icon="lock", secret=True, pady=(0, 8),
                                on_change=lambda v: self.meter.update_for(v, nickname))
        self.meter = StrengthMeter(c)
        self.meter.pack(fill="x", pady=(0, 12))
        self.f_confirm = self.field(c, "Confirmez le mot de passe", icon="lock", secret=True)
        self.notice = Notice(c)
        self.notice.pack(fill="x")
        self.button(c, "Enregistrer", lambda: self._save_password(nickname))
        self.link_row(c, left=("Retour", lambda: self.show_manage()))
        self.focus_later(self.f_new)

    def _save_password(self, nickname: str):
        new = self.f_new.get()
        if problem := login.password_problem(new, nickname):
            self.notice.show(problem)
            self.f_new.mark_error()
            return self.shake()
        if new != self.f_confirm.get():
            self.notice.show("Les deux mots de passe ne sont pas identiques.")
            self.f_confirm.mark_error()
            return self.shake()
        self._apply(lambda: login.change_password(new), "Mot de passe changé.")


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# -- branchements avec la fenetre principale ----------------------------------------------

def unlock() -> bool:
    """Avant d'ouvrir la fenetre principale : demande la connexion si elle est activee.
    Retourne False si l'utilisateur ferme l'ecran sans se connecter."""
    if not login.enabled():
        return True
    root = tk.Tk()
    root.withdraw()
    _set_icon(root)
    try:
        window = AccessWindow(root, "open")
        root.wait_window(window)
        return bool(window.result)
    finally:
        root.destroy()


def _modal(app, mode: str) -> AccessWindow:
    window = AccessWindow(app, mode)
    window.transient(app)
    window.update_idletasks()
    try:
        window.grab_set()  # fenetre modale : la fenetre principale attend
    except tk.TclError:
        pass
    app.wait_window(window)
    refresh(app)
    return window


def offer(app) -> None:
    """Propose une seule fois de proteger FreeAV par un mot de passe (premiere ouverture)."""
    if login.enabled() or updater.load_setting(OFFERED_SETTING, False,
                                               updater.CONFIG_FILE) is True:
        return
    try:
        updater.save_setting(OFFERED_SETTING, True, updater.CONFIG_FILE)
    except OSError:
        pass
    if app.winfo_exists():
        _modal(app, "offer")


def manage(app) -> None:
    """Bouton « Connexion... » : creer l'acces, ou le modifier apres avoir confirme son
    identite."""
    _modal(app, "manage" if login.enabled() else "setup")


def lock(app) -> None:
    """Cache la fenetre principale jusqu'a la connexion (la protection continue)."""
    if not login.enabled() or not app.winfo_exists():
        return
    app.withdraw()
    window = AccessWindow(app, "lock")
    app.wait_window(window)
    if window.result:
        app.deiconify()
        return
    stop = getattr(app, "watch_stop", None)
    if stop is not None:
        stop.set()
    app.destroy()


def refresh(app) -> None:
    """Affiche le bouton « Verrouiller » seulement si la connexion est activee."""
    if not app.winfo_exists():
        return
    keys = ("<Control-l>", "<Control-L>")
    if login.enabled():
        app.lock_btn.pack(side="right", padx=6, after=app.login_btn)
        for key in keys:
            app.bind(key, lambda e: lock(app))
    else:
        app.lock_btn.pack_forget()
        for key in keys:
            app.unbind(key)


def attach(app, offer_now: bool = True) -> None:
    """Ajoute « Connexion... » et « Verrouiller » au bandeau de la fenetre principale, et
    propose la connexion une fois si la politique de confidentialite est deja acceptee (sinon,
    la proposition suit sa validation)."""
    app.login_btn = ttk.Button(app.banner, text="Connexion...", command=lambda: manage(app))
    app.login_btn.pack(side="right", padx=6)
    app.lock_btn = ttk.Button(app.banner, text="Verrouiller", command=lambda: lock(app))
    refresh(app)
    from . import privacy
    if offer_now and not privacy.needs_first_run():
        app.after(700, lambda: offer(app))
