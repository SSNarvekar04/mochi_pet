# Mochi Pet – AI-Powered Virtual Desktop Pet

Mochi is an interactive virtual pet that lives on your desktop, shows animated
expressions and chats with you using Generative AI while you work or study.

## Key features
- Animated pet: bouncing, blinking, happy / sleepy / sad / thinking / talking / love expressions
- Pet needs: hunger, energy and happiness change over time
- Interactions: Feed, Play, Sleep buttons; double-click to pet; drag to move; always on top
- AI conversations: personality-driven replies from the Anthropic API that react to Mochi's current mood
- Demo mode: if no API key is set, Mochi uses scripted replies (clearly labelled in the greeting)
- Standard library only – no packages to install

## Install and run (Windows)
```
git clone https://github.com/Jay208mane/mochi_pet
cd mochi_pet
copy .env.example .env
notepad .env
python mochi_pet.py
```
Put your key in `.env` (`ANTHROPIC_API_KEY=...`). Leave it as is for demo mode.
On Linux: `sudo apt install python3-tk`.

## How it works
| Part | Role |
|------|------|
| `Pet` | state: hunger, energy, happiness, sleeping; picks the current expression |
| `Brain` | builds a system prompt containing Mochi's state and calls the AI (background thread) |
| `MochiApp` | tkinter UI, 25 fps canvas animation, buttons, chat box |

## Purpose
To explore combining Generative AI with interactive animation to build an
intelligent virtual companion that makes everyday computer use more engaging.
