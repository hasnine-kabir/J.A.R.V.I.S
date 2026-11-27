<h1 align="center">J.A.R.V.I.S. v2.1</h1>

An AI assistant for your PC, powered by Google Gemini. You talk to it in plain English (typed or spoken), and it decides which of its tools to use: open apps, run commands, search the web, check the weather, remember things about you, read and write code, play music, send email.

## Quick start (Windows)

1. Install Python 3.11 or newer.
2. Double-click **`install.bat`** (or run `pip install -r requirements-v2.txt`).
3. Double-click **`jarvis-ui.bat`** for the web UI (or run `python -m jarvis --web`).
4. Prefer the terminal? Double-click **`jarvis.bat`**. For hands-free voice in the terminal, **`jarvis-handsfree.bat`**.
5. On first launch, paste your free Gemini API key from https://aistudio.google.com/apikey. It is saved to `.env`.

```
python -m jarvis --web      # web UI at http://127.0.0.1:8765 (opens your browser)
python -m jarvis            # chat in the terminal
python -m jarvis --voice    # Jarvis speaks its replies
python -m jarvis --listen   # push-to-talk: press Enter on an empty line, then talk
python -m jarvis --handsfree   # always listening: say "Jarvis, ..." and it answers out loud
python -m jarvis --mic-test    # check that the microphone hears you
python -m jarvis --add-key     # add more Gemini API keys
python -m jarvis --ask "what's the weather in Dhaka?"   # one-shot answer
```

## Things to try

| You say | Jarvis uses |
|---|---|
| what's the weather in London? | system_info → weather |
| how's my PC doing? / how much disk space is left? | system_info |
| open notepad / open my Downloads folder | pc_control → open_application |
| list the files in E:/GITHUB | pc_control → list_directory |
| run `ipconfig` and tell me my IP | pc_control → run_command (asks you first) |
| search the web for the latest Python release and summarize it | web_search → search + read_page |
| who was Ada Lovelace? | wikipedia_search |
| show me the structure of this project, then explain jarvis/core/orchestrator.py | code_helper |
| remember my exam is on Friday / what do you know about me? | notes (stored in `memory.db`) |
| take a screenshot | screenshot |
| play some music / search YouTube for lofi beats | media |
| email bob@example.com that I'll be late | email_sender (asks you first) |

In-chat commands: `/help`, `/voice on|off`, `/listen`, `/handsfree`, `/notes`, `/facts`, `/keys`, `/addkey`, `/clear`, `exit`.

## Web UI

`jarvis-ui.bat` or `python -m jarvis --web` starts a local server and opens the UI in your browser.

- Replies stream in word by word. Tool use shows up as chips under the reply (amber while running, green when done).
- **Left panel:** the status orb (blue = ready, amber = thinking, green = listening, pulsing = speaking), voice-reply and hands-free switches, a live model picker, CPU/RAM/battery and your API keys.
- **Right panel:** what Jarvis remembers about you and your notes (hover to delete), the loaded skills, and recent actions.
- **Mic button:** push-to-talk. The answer is spoken back. **Hands-free switch:** always listening for "Jarvis, …".
- Keys: `Enter` sends, `Shift+Enter` adds a new line, `/` focuses the box, `Esc` stops speech.
- It works on phones and tablets too. Set `web.host: 0.0.0.0` in `config.yaml` to open it from another device on your Wi-Fi. There is no login, so only do that on a network you trust.
- Voice uses this PC's microphone and speakers, not the browser's.

## Speed

- Replies stream as they're generated, in both the web UI and the terminal. In voice modes Jarvis starts speaking after the first sentence.
- The default model is `gemini-3.5-flash-lite` with `thinking_level: minimal`. Most answers take 1 to 3 seconds. Pick a bigger model (e.g. `gemini-3.5-flash`) in the UI or `config.yaml` when you want deeper answers. Those are slower and often overloaded; Jarvis falls back automatically.
- When the model asks for several tools at once, they run in parallel.
- Heavy libraries load only when a skill first needs them, so startup is quick.

## Hands-free voice mode

Run `jarvis-handsfree.bat`, `python -m jarvis --handsfree`, or type `/handsfree` in the chat.

- Say **"Jarvis, what's the weather?"** and it answers out loud.
- Say just **"Jarvis"** and it replies "Yes?", then listens for your request.
- After each reply you have about 10 seconds to ask a follow-up without saying "Jarvis".
- Say **"never mind"** to cancel, or **"goodbye"** (or press Ctrl+C) to stop.
- Speech that doesn't include "Jarvis" is ignored. Recognition uses Google's free speech service, so audio of what you say is sent to Google.
- If Jarvis doesn't react to your voice, run `python -m jarvis --mic-test` and follow its advice (usually lowering `voice.mic_threshold`).

## Multiple API keys

Put several keys in `.env` as `GEMINI_API_KEYS=key1,key2,key3`, or add them with `/addkey`. When a key runs out of quota, Jarvis switches to the next one and retries automatically. `/keys` shows which key is in use.

**Permissions.** `safety.confirm_actions` in `config.yaml` controls this. When `false` (full access), Jarvis runs shell commands, writes files and sends email without asking. When `true`, it shows you exactly what it wants to do first and waits for **y** (or a spoken "yes" in hands-free mode). Reading, searching and opening apps always run right away. Jarvis also reads web pages, which could contain text that tries to trick it, so turn confirmations on if that worries you.

## Configuration

`config.yaml` holds your name, Jarvis's personality, the Gemini model (`llm.model`, default `gemini-3.5-flash-lite`, with automatic fallbacks, and `llm.thinking_level`), the web UI (`web.host`, `web.port`) and voice settings (`voice.enabled`, `voice.name` such as "Zira" or "David", `voice.language` such as `en-IN`).

`.env` holds secrets (git-ignored; see `.env.example`):

```
GEMINI_API_KEY=...
SMTP_EMAIL=you@gmail.com        # optional, for email
SMTP_PASSWORD=app-password      # a Gmail App Password, not your normal password
```

Jarvis remembers facts and notes across sessions in `memory.db`, and writes logs to `jarvis.log`.

## Architecture

```
jarvis/
├── __main__.py           entry point, first-run setup, CLI flags
├── config.py             config.yaml + .env
├── core/
│   ├── brain.py          Brain protocol + GeminiBrain (google-genai, streaming, function calling)
│   ├── orchestrator.py   input → brain → tools (with confirmation) → reply
│   ├── memory.py         short-term conversation + long-term SQLite (facts, notes, session summaries)
│   └── skill_registry.py auto-discovers skills in jarvis/skills/
├── skills/               one file per skill; subclass BaseSkill, list Tools, implement execute()
├── voice/                speaker (Windows speech / pyttsx3), listener (sounddevice + speech recognition)
├── ui/terminal.py        rich + prompt_toolkit chat UI (streaming)
├── ui/handsfree.py       wake-word voice loop for the terminal
├── web/server.py         FastAPI + WebSocket server for the web UI
├── web/static/           the web UI (plain HTML/CSS/JS, no build step)
└── utils/
```

**Add a skill:** drop a new file in `jarvis/skills/` with a `BaseSkill` subclass. It is picked up automatically on the next start. Set `confirm=True` on any `Tool` that changes things.

**Tests:** `python -m pytest`

---

## Legacy v1

The original keyword-matching version of this project (`jarvis.py`, `helpers.py`, …) is still in the repo root, unchanged. The v1 README follows.

<h1 align="center">J.A.R.V.I.S </h1> 

<div align="center">
  
[![Welcome to my profile](https://img.shields.io/badge/Hello,Devs!-Welcome-blue.svg?style=flat&logo=github)](https://github.com/gauravsingh9356/J.A.R.V.I.S)
[![Open Source Love](https://badges.frapsoft.com/os/v2/open-source.svg?v=103)](https://github.com/gauravsingh9356/J.A.R.V.I.S)
 [![GitHub issues](https://img.shields.io/github/issues/GauravSingh9356/J.A.R.V.I.S)](https://github.com/GauravSingh9356/J.A.R.V.I.S/issues)
![Stars](https://img.shields.io/github/stars/gauravsingh9356/J.A.R.V.I.S?style=flat&logo=github)
![Forks](https://img.shields.io/github/forks/gauravsingh9356/J.A.R.V.I.S?style=flat&logo=github)
[![GitHub license](https://img.shields.io/github/license/GauravSingh9356/J.A.R.V.I.S)](https://github.com/GauravSingh9356/J.A.R.V.I.S/blob/master/LICENSE)
  
[![forthebadge made-with-python](http://ForTheBadge.com/images/badges/made-with-python.svg)](https://www.python.org/)

  </div>



<img src="jarvis1.jpg"/>

### Requirements:

<li>datetime</li>
<li>os</li>
<li> pyttsx3</li>
<li> wikipedia</li>
<li> speech_recognition </li>
<li> webbrowser</li>
<li> sys</li>
<li> smtplib</li>
<li>requests</li>
<li>json</li>
<li>defflib</li>
<li>geocoder</li>
<li>pyjokes</li>
<li>psutil</li>
<li> pyautogui</li>
<li> opencv</li>

<h2>Required Packages</h2>

```
pip install -r requirements.txt
```

> _ To install PyAudio on windows head over to https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio and download the .whl for your machine and run the installation as shown below, then install the remaining dependencies from the requirements.txt file. You may remove pyAduio from the requirements file if it interrupts your installation (its there for unix users)
```bash
pip install PyAudio‑0.2.11‑cp<version>‑cp<version>m‑win_amd<architecture>.whl
```

### On Ubuntu based Linux distribution you need to install the following packages, so that the code works:

```
sudo apt-get update && sudo apt-get install espeak

```

### What it does...

  <ul>
   <li>Dynamic Authentication using Optical Face Recognition</li>
<li>Send emails</li>
  <li>Dynamic News Reporting at any time with api integration</li>
  <li>Todo list generator, Yes it remembers all!</li> 
<li>Open any website with just a voice command</li>
<li>Plays Music</li>
<li>Tells time</li>
<li>Wikipedia powered AI</li>
<li>Dictionary with Intelligent Sensing i.e. auto checking if spell mistake</li>
<li>Weather Report such as temp, wind speed, humidity, weather description</li>
<li>Latitude and longitude</li>
 <li>YouTube searching</li> 
 <li>Google Map searching</a>
 <li>YouTube Downloader, download any youtube video by just putting url of video</li>
 <li>Now Master can switch b/w J.A.R.V.I.S and F.R.I.D.A.Y, switch to female voice assistant</li>
</ul>

<table>
  <tr>
    <td><img src="images/Screenshot%20(138).png"/></td>
      <td><img src="https://github.com/GauravSingh9356/J.A.R.V.I.S/blob/master/images/face-600x900.png"/></td>
    

</tr>
<tr>
<td><img src="images/email.jpg"/></td>
<td><img src="https://github.com/GauravSingh9356/J.A.R.V.I.S/blob/master/images/maxresdefault.jpg"/></td>
</tr>
<td><img src="https://github.com/GauravSingh9356/J.A.R.V.I.S/blob/master/images/4-Best-Weather-Forecast-APIs-for-Development-of-Weather-Apps-624x304.jpeg"/></td>
  <td><img src="https://github.com/GauravSingh9356/J.A.R.V.I.S/blob/master/images/maxresdefault%20(1).jpg"/></td>
</tr>
<tr>
  <td><img src="canny.jpg"/>
          </td>
  <td><img src="ImgContor.jpg"/>
          </td>
</tr>
</table>

## Some Sneak peeks:

<ul>
  <li><h2> Jarvis, Are you there?</h2></li>
  <li><h2> At your service, Sir</h2></li>
  
  <li><h2> Jarvis, What are today's news headlines? can you tell?</h2></li>
  <li><h2>Ofcourse, Sir -> Then news headlines   Would you like to visit the news url?</h2></li>
  
  <li><h2> Search Youtube</h2></li>
  <li><h2>What you want to search, Sir</h2></li>
  <li><h2>Coding for kids</h2></li>
  <li><h2> Opens youtube in browser with desired search query results </h2></li>
  
   <li><h2> Jarvis, Can you send email to Gaurav?</h2></li>
  <li><h2>What I say sir, Sir</h2></li>
   <li><h2>Gaurav is a good boy</h2></li>
  <li><h2> Email is sent successfully, Sir</h2></li>
  
  # And so on....
  
<a href="https://techtalkswithgaurav.blogspot.com/2020/06/your-personal-assistant-jarvis.html" target="_blank">Read complete blog article</a>

## Contribution:
Thank you for your interest in contributing to our Repo! Pull requests are welcome. For fixing typos, please make a PR with your fixes. We are happy for every contribution.
A lot can be done with this project. Core AI chatbot like functionality can be added. More python scripts can be associated. Pull requests for any such changes are accepted. Feel free to fork this project and make your own changes too.
