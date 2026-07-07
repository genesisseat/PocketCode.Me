# PocketCode
<img width="595" height="285" alt="image" src="https://github.com/user-attachments/assets/1cd08efc-f925-46da-a509-1755272be83a" />

A lightweight command-line AI assistant built for **Termux** on Android. PocketCode connects to **Google AI Studio (Gemini/Gemma models)** using your own API key, and lets you chat directly from your phone's terminal — no browser, no app switching.

---

## Features

- 🔑 **Single API key** — one Google AI Studio key stored locally, updateable anytime
- 🧠 **Model picker** — switch between available Gemini/Gemma text models on the fly
- 💬 **Persistent conversation memory** — chat history is saved to disk and reloaded automatically, even after closing the app
- 🧵 **Session management** — start a new conversation anytime without losing the old one
- 📱 **Phone-first design** — minimal typing, slash-commands instead of long CLI flags
- 🚫 **No usage tracking** — no local quota counters; Google's own rate limits apply and are simply surfaced as friendly errors if hit

---

## Requirements

- [Termux](https://termux.dev/) installed on Android
- Python 3.10+
- `pip install requests`

---

## Installation

```bash
pkg update && pkg upgrade
pkg install python
pip install requests

git clone <your-repo-url> pocketcode
cd pocketcode
chmod +x pocketcode.py
```

(Optional) Add an alias so you can run it from anywhere:

```bash
echo 'alias pocketcode="python ~/pocketcode/pocketcode.py"' >> ~/.bashrc
source ~/.bashrc
```

---

## Usage

Start the app:

```bash
pocketcode
```

You'll land directly in chat mode:

```
You: hello!
AI: Hi there! How can I help you today?
```

### Slash Commands

| Command             | Description                                      |
|----------------------|--------------------------------------------------|
| `/help`              | Show all available commands                       |
| `/config`            | View current model and masked API key              |
| `/key <api_key>`     | Update your Google AI Studio API key               |
| `/model`             | List available Gemini/Gemma models and switch      |
| `/new`               | Start a new conversation (previous one is saved)  |
| `/history`           | List saved conversation sessions                  |
| `/clear`             | Clear the current conversation's history          |
| `/exit`              | Save and quit                                     |

---

## Configuration Storage

PocketCode stores config and history locally on-device — nothing is sent anywhere except your chosen AI provider's API.

```
~/.pocketcode/
├── config.json        # active provider name, endpoint URL, API key
└── sessions/
    ├── 2026-07-01_142300.jsonl
    └── 2026-07-06_091500.jsonl
```

**`config.json` example:**
```json
{
  "api_key": "AIza...",
  "model": "gemini-3.1-flash-lite"
}
```

⚠️ **Security note:** The API key is stored in plaintext. After first run, PocketCode sets file permissions to `600` (owner read/write only). Avoid sharing your `~/.pocketcode` folder or backing it up to shared/cloud storage without stripping the key first.

---

## Google AI Studio API Details

PocketCode talks directly to the Gemini API:

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}
```

Request body uses Gemini's `contents` / `parts` format (not OpenAI's `messages` format):
```json
{
  "contents": [
    { "role": "user", "parts": [{ "text": "hello" }] },
    { "role": "model", "parts": [{ "text": "hi there!" }] }
  ]
}
```
Note: Gemini uses `"model"` as the role name for AI replies (not `"assistant"`), so saved history must map to this when sent.

The reply text is found at `candidates[0].content.parts[0].text` in the response.

### Available Free-Tier Text Models

| Model | Daily Requests |
|---|---|
| Gemini 2.5 Flash | 20 |
| Gemini 2.5 Flash Lite | 20 |
| Gemini 3 Flash | 20 |
| Gemini 3.1 Flash Lite | 500 |
| Gemini 3.5 Flash | 20 |
| Gemma 4 26B | 1,500 |
| Gemma 4 31B | 1,500 |

PocketCode does **not** track usage locally — daily quotas reset on Google's side automatically. If a limit is hit, the API returns a `429` error, which PocketCode displays as a short friendly message rather than raw JSON.

---

## Conversation Memory

- Each session is saved as a `.jsonl` file (one JSON message per line) under `~/.pocketcode/sessions/`
- On launch, PocketCode reloads your most recent session so you can pick up where you left off
- To avoid resending huge histories (and hitting token limits), only the last N messages are sent to the model — the full log is still kept on disk
- Use `/new` to start a fresh session without deleting the old one
- History is converted to Gemini's `contents` format at send time (see API Details below)

---

## Roadmap / Ideas

- [ ] ANSI color output for AI vs. system messages
- [ ] Token-based (not just message-count-based) history trimming
- [ ] Live-fetch available models from Google's `/models` endpoint instead of a hardcoded list
- [ ] Optional encrypted key storage via `termux-api` / Android Keystore
- [ ] Export a session to plain text or Markdown

---

## License

MIT (or your preferred license — update this section)
