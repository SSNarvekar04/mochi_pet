"""Mochi Pet - AI-Powered Virtual Desktop Pet (Practical No. 8)

A small always-on-top desktop pet drawn with tkinter. Mochi has animated
expressions (blink, bounce, happy, sleepy, sad, thinking, talking), needs
(hunger, energy, happiness) and chats using Generative AI (Anthropic API).

If ANTHROPIC_API_KEY is not set, Mochi runs in clearly labelled DEMO MODE
with simple scripted replies so the app still works offline.
"""
import json
import math
import os
import queue
import random
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("MOCHI_MODEL", "claude-sonnet-5-5")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
DEMO_MODE = not API_KEY
TRANSPARENT = "#010101"  # becomes see-through on Windows


def load_env_file(path=".env"):
    """Tiny .env loader so no extra dependency is needed."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env_file()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("MOCHI_MODEL", MODEL)
DEMO_MODE = not API_KEY


# ------------------------------------------------------------------ AI brain
class Brain:
    def __init__(self):
        self.history = []

    def system_prompt(self, pet):
        return (
            "You are Mochi, a cute, playful virtual desktop pet who lives on the "
            "user's screen. Reply in 1-2 short, warm sentences, with occasional "
            "pet-like sounds (nya, *purr*, *wiggle*). Encourage the user while "
            "they work or study. Stay in character. Your current state: "
            f"hunger fullness {pet.hunger:.0f}/100, energy {pet.energy:.0f}/100, "
            f"happiness {pet.happy:.0f}/100. Mention it naturally if you are "
            "hungry, tired or sad."
        )

    def reply(self, text, pet):
        if DEMO_MODE:
            return self.demo_reply(text, pet)
        self.history.append({"role": "user", "content": text})
        body = json.dumps({
            "model": MODEL,
            "max_tokens": 200,
            "system": self.system_prompt(pet),
            "messages": self.history[-10:],
        }).encode()
        req = urllib.request.Request(API_URL, data=body, headers={
            "content-type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            out = "".join(b.get("text", "") for b in data["content"]).strip()
            self.history.append({"role": "assistant", "content": out})
            return out or "*tilts head* nya?"
        except urllib.error.HTTPError as e:
            self.history.pop()
            return f"(AI error {e.code}. Check your API key.)"
        except Exception as e:  # network etc.
            self.history.pop()
            return f"(Can't reach AI: {type(e).__name__})"

    @staticmethod
    def demo_reply(text, pet):
        t = text.lower()
        if any(w in t for w in ("hi", "hello", "hey")):
            return "Nya! Hello friend! *wiggle*"
        if any(w in t for w in ("hungry", "food", "eat")):
            return "Mochi is " + ("hungry... feed me?" if pet.hunger < 50 else "full and happy!")
        if any(w in t for w in ("study", "work", "exam", "code")):
            return "You can do it! I'll cheer for you. Take a break every 25 minutes!"
        if any(w in t for w in ("sad", "tired", "stress")):
            return "*snuggles* Take a deep breath. I'm right here with you."
        if "love" in t:
            return "Mochi loves you too! *purr*"
        return random.choice([
            "Nya? Tell me more!", "*tilts head* Interesting...",
            "Mochi is listening. *wiggle*", "Let's keep going together!",
        ])


# ------------------------------------------------------------------ pet state
class Pet:
    def __init__(self):
        self.hunger = 80.0   # fullness
        self.energy = 80.0
        self.happy = 80.0
        self.sleeping = False
        self.talking_until = 0.0
        self.thinking = False
        self.petted_until = 0.0

    def tick(self, dt):
        if self.sleeping:
            self.energy = min(100, self.energy + 6 * dt)
            self.hunger = max(0, self.hunger - 0.2 * dt)
            if self.energy >= 100:
                self.sleeping = False
        else:
            self.hunger = max(0, self.hunger - 0.6 * dt)
            self.energy = max(0, self.energy - 0.4 * dt)
            drain = 0.3 + (0.4 if self.hunger < 30 else 0)
            self.happy = max(0, self.happy - drain * dt)

    def expression(self, now):
        if self.sleeping:
            return "sleep"
        if self.thinking:
            return "thinking"
        if now < self.petted_until:
            return "love"
        if now < self.talking_until:
            return "talk"
        if self.hunger < 25 or self.happy < 25:
            return "sad"
        if self.energy < 25:
            return "sleepy"
        if self.happy > 70:
            return "happy"
        return "neutral"


# ------------------------------------------------------------------ UI
class MochiApp:
    W, H = 280, 250

    def __init__(self, root):
        self.root = root
        self.pet = Pet()
        self.brain = Brain()
        self.q = queue.Queue()
        self.last = time.time()
        self.next_blink = self.last + 3
        self.blink_until = 0.0
        self.hearts = []

        root.title("Mochi Pet")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=TRANSPARENT)
        try:
            root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        root.geometry("+200+120")

        self.canvas = tk.Canvas(root, width=self.W, height=self.H,
                                bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_pet)

        panel = tk.Frame(root, bg="#fff4f8", padx=8, pady=6)
        panel.pack(fill="x")
        self.bubble = tk.Label(panel, text="", bg="#fff4f8", fg="#5a3550",
                               wraplength=260, justify="left",
                               font=("Segoe UI", 10, "italic"))
        self.bubble.pack(fill="x")

        self.stat_lbl = tk.Label(panel, bg="#fff4f8", fg="#7a5a70",
                                 font=("Segoe UI", 8))
        self.stat_lbl.pack(fill="x")

        btns = tk.Frame(panel, bg="#fff4f8")
        btns.pack(fill="x", pady=3)
        for text, cmd in (("🍡 Feed", self.feed), ("🎾 Play", self.play),
                          ("😴 Sleep", self.sleep), ("✖", root.destroy)):
            tk.Button(btns, text=text, command=cmd, relief="flat",
                      bg="#ffd9e8", activebackground="#ffc2da",
                      font=("Segoe UI", 9)).pack(side="left", padx=2)

        row = tk.Frame(panel, bg="#fff4f8")
        row.pack(fill="x")
        self.entry = tk.Entry(row, font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send)
        tk.Button(row, text="Send", command=self.send, relief="flat",
                  bg="#d9e8ff").pack(side="left", padx=(4, 0))

        mode = "DEMO MODE (no API key)" if DEMO_MODE else f"AI: {MODEL}"
        self.say(f"Nya! I'm Mochi! [{mode}] Double-click me to pet me.", 5)
        self.animate()

    # ---- interactions
    def say(self, text, seconds=4):
        self.bubble.config(text=text)
        self.pet.talking_until = time.time() + seconds

    def feed(self):
        if self.pet.sleeping:
            return self.say("Zzz... (Mochi is sleeping)")
        self.pet.hunger = min(100, self.pet.hunger + 30)
        self.pet.happy = min(100, self.pet.happy + 5)
        self.say("Yum yum! Mochi loves dango! 🍡")

    def play(self):
        if self.pet.sleeping:
            return self.say("Zzz... (Mochi is sleeping)")
        if self.pet.energy < 15:
            return self.say("Too sleepy to play... nya...")
        self.pet.happy = min(100, self.pet.happy + 20)
        self.pet.energy = max(0, self.pet.energy - 10)
        self.pet.hunger = max(0, self.pet.hunger - 5)
        self.hearts += [(random.randint(90, 190), 120, time.time()) for _ in range(3)]
        self.say("Wheee! That was fun! *bounce*")

    def sleep(self):
        self.pet.sleeping = not self.pet.sleeping
        self.say("Goodnight... zzz" if self.pet.sleeping else "Good morning! *stretch*")

    def on_pet(self, _e):
        if self.pet.sleeping:
            self.pet.sleeping = False
        self.pet.happy = min(100, self.pet.happy + 8)
        self.pet.petted_until = time.time() + 2
        self.hearts += [(random.randint(100, 180), 100, time.time()) for _ in range(4)]
        self.say("*purr* nya~")

    def on_press(self, e):
        self._dx, self._dy = e.x, e.y

    def on_drag(self, e):
        x = self.root.winfo_x() + e.x - self._dx
        y = self.root.winfo_y() + e.y - self._dy
        self.root.geometry(f"+{x}+{y}")

    def on_release(self, _e):
        pass

    def send(self, _e=None):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.pet.sleeping = False
        self.pet.thinking = True
        self.bubble.config(text="Mochi is thinking...")
        threading.Thread(target=lambda: self.q.put(self.brain.reply(text, self.pet)),
                         daemon=True).start()

    # ---- animation loop
    def animate(self):
        now = time.time()
        dt = min(now - self.last, 1.0)
        self.last = now
        self.pet.tick(dt)

        try:
            reply = self.q.get_nowait()
            self.pet.thinking = False
            self.pet.happy = min(100, self.pet.happy + 3)
            self.say(reply, 6 + len(reply) / 20)
        except queue.Empty:
            pass

        if now > self.next_blink:
            self.blink_until = now + 0.15
            self.next_blink = now + random.uniform(2.5, 6)

        self.draw(now)
        p = self.pet
        self.stat_lbl.config(
            text=f"🍡 {p.hunger:.0f}   ⚡ {p.energy:.0f}   💖 {p.happy:.0f}")
        self.root.after(40, self.animate)

    def draw(self, now):
        c = self.canvas
        c.delete("all")
        expr = self.pet.expression(now)
        cx, base = self.W / 2, 215

        speed = {"sleep": 1.2, "sleepy": 1.5, "sad": 1.5, "love": 8,
                 "happy": 4, "talk": 5}.get(expr, 3)
        s = math.sin(now * speed)
        squash = 1 + 0.04 * s
        lift = max(0, s) * (10 if expr in ("happy", "love", "talk") else 4)
        w, h = 80 * (2 - squash), 70 * squash
        top = base - 2 * h - lift
        bot = base - lift

        c.create_oval(cx - 60, 222, cx + 60, 240, fill="#d9c9d3", outline="")  # shadow
        # ears
        for sx in (-1, 1):
            c.create_oval(cx + sx * w * 0.55 - 14, top - 8, cx + sx * w * 0.55 + 14, top + 28,
                          fill="#ffffff", outline="#e0c8d6", width=2)
        c.create_oval(cx - w, top, cx + w, bot, fill="#ffffff", outline="#e0c8d6", width=3)

        ey = top + h * 0.85
        ex = w * 0.42
        blinking = now < self.blink_until
        self.draw_eyes(c, cx, ey, ex, expr, blinking)

        # cheeks
        blush = "#ffb3c9" if expr != "sad" else "#d9d9ea"
        for sx in (-1, 1):
            c.create_oval(cx + sx * w * 0.62 - 12, ey + 18, cx + sx * w * 0.62 + 12, ey + 30,
                          fill=blush, outline="")
        self.draw_mouth(c, cx, ey + 24, expr, now)

        if expr == "sleep":
            for i in range(3):
                off = (now * 20 + i * 25) % 75
                c.create_text(cx + w * 0.7 + i * 8, top - off + 40, text="z",
                              fill="#8a7a9a", font=("Segoe UI", 12 + i * 4, "bold"))
        if expr == "thinking":
            c.create_text(cx + w * 0.8, top, text="💭", font=("Segoe UI", 20))
        if expr == "sad" and not self.pet.sleeping:
            c.create_oval(cx + ex + 8, ey + 10, cx + ex + 16, ey + 24, fill="#8ec5ff", outline="")

        self.hearts = [(x, y, t0) for (x, y, t0) in self.hearts if now - t0 < 1.5]
        for x, y, t0 in self.hearts:
            c.create_text(x, y - (now - t0) * 60, text="💗", font=("Segoe UI", 14))

    @staticmethod
    def draw_eyes(c, cx, ey, ex, expr, blinking):
        for sx in (-1, 1):
            x = cx + sx * ex
            if expr == "sleep" or blinking or expr == "sleepy":
                c.create_arc(x - 10, ey - 6, x + 10, ey + 10, start=200, extent=140,
                             style="arc", outline="#5a3550", width=3)
            elif expr in ("happy", "love"):
                c.create_arc(x - 10, ey - 4, x + 10, ey + 14, start=20, extent=140,
                             style="arc", outline="#5a3550", width=3)
            else:
                r = 9
                c.create_oval(x - r, ey - r, x + r, ey + r, fill="#3a2540", outline="")
                c.create_oval(x - 3, ey - 6, x + 3, ey, fill="#ffffff", outline="")
                if expr == "sad":
                    c.create_line(x - 12, ey - 14, x + 8 * (-sx), ey - 18,
                                  fill="#5a3550", width=2)

    @staticmethod
    def draw_mouth(c, cx, y, expr, now):
        col = "#5a3550"
        if expr == "talk":
            o = 4 + 4 * abs(math.sin(now * 12))
            c.create_oval(cx - 7, y, cx + 7, y + o * 2, fill="#ff8fab", outline=col, width=2)
        elif expr in ("happy", "love"):
            c.create_arc(cx - 14, y - 8, cx + 14, y + 14, start=200, extent=140,
                         style="arc", outline=col, width=3)
        elif expr == "sad":
            c.create_arc(cx - 10, y + 4, cx + 10, y + 20, start=20, extent=140,
                         style="arc", outline=col, width=3)
        elif expr == "sleep":
            c.create_oval(cx - 3, y + 2, cx + 3, y + 8, outline=col, width=2)
        elif expr == "thinking":
            c.create_line(cx - 6, y + 4, cx + 6, y + 4, fill=col, width=3)
        else:
            c.create_arc(cx - 8, y - 4, cx + 8, y + 8, start=200, extent=140,
                         style="arc", outline=col, width=2)


if __name__ == "__main__":
    root = tk.Tk()
    MochiApp(root)
    root.mainloop()
