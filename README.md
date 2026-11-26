<h1 align="center">J.A.R.V.I.S. v2.0</h1>

An AI assistant for your PC, powered by Google Gemini. You talk to it in plain English (typed or spoken), and it decides which of its tools to use: open apps, run commands, search the web, check the weather, remember things about you, read and write code, play music, send email.

## Quick start (Windows)

1. Install Python 3.11 or newer.
2. Double-click **`install.bat`** (or run `pip install -r requirements-v2.txt`).
3. Double-click **`jarvis.bat`** (or run `python -m jarvis`).
4. On first launch, paste your free Gemini API key from https://aistudio.google.com/apikey. It is saved to `.env`.

```
python -m jarvis            # chat in the terminal
python -m jarvis --voice    # Jarvis speaks its replies
python -m jarvis --listen   # press Enter on an empty line, then talk
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

In-chat commands: `/help`, `/voice on|off`, `/listen`, `/notes`, `/facts`, `/clear`, `exit`.

**Safety.** Before running a shell command, writing a file, or sending an email, Jarvis shows you exactly what it wants to do and waits for **y**. Everything else (reading, searching, opening apps) runs right away.

## Configuration

`config.yaml` holds your name, Jarvis's personality, the Gemini model (`llm.model`, default `gemini-2.5-flash`) and voice settings (`voice.enabled`, `voice.name` such as "Zira" or "David", `voice.language` such as `en-IN`).

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
│   ├── brain.py          Brain protocol + GeminiBrain (google-genai, function calling)
│   ├── orchestrator.py   input → brain → tools (with confirmation) → reply
│   ├── memory.py         short-term conversation + long-term SQLite (facts, notes, session summaries)
│   └── skill_registry.py auto-discovers skills in jarvis/skills/
├── skills/               one file per skill; subclass BaseSkill, list Tools, implement execute()
├── voice/                speaker (Windows speech / pyttsx3), listener (sounddevice + speech recognition)
├── ui/terminal.py        rich + prompt_toolkit chat UI
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
