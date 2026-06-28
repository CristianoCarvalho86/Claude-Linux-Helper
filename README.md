# 🐧 Claude Linux Helper 🤖

A friendly CLI assistant for **Linux newcomers** (Ubuntu / Debian) who want to
set up and use the [Claude AI](https://claude.ai) API on their system.

---

## Features

| Feature | Details |
|---------|---------|
| **AI chat** | Multi-turn conversation with Claude, tuned for Linux & Ubuntu guidance |
| **Built-in tips** | Offline quick-reference for 8 topic areas – no API key needed |
| **Slash commands** | `/help`, `/tips <category>`, `/categories`, `/reset`, `/exit` |
| **Beginner-friendly** | Step-by-step instructions, copy-paste commands, safe-use warnings |

---

## Requirements

- Python 3.8+
- An Anthropic API key (free tier available at <https://console.anthropic.com/>)

---

## Quick Start (Ubuntu / Debian)

### 1 – Clone the repository

```bash
git clone https://github.com/CristianoCarvalho86/Claude-Linux-Helper.git
cd Claude-Linux-Helper
```

### 2 – Run the setup script

```bash
bash setup.sh
```

The script will:
- Install Python 3 and pip via `apt` (if needed)
- Create a virtual environment (`venv/`)
- Install the Python dependencies (`anthropic`, `rich`)

### 3 – Set your API key

Get a free key at <https://console.anthropic.com/> and export it:

```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

To make it permanent:

```bash
echo "export ANTHROPIC_API_KEY='sk-ant-...'" >> ~/.bashrc
source ~/.bashrc
```

### 4 – Start the helper

```bash
source venv/bin/activate
python3 main.py
```

---

## Manual Installation (any distro)

```bash
pip3 install -r requirements.txt
export ANTHROPIC_API_KEY='sk-ant-...'
python3 main.py
```

---

## Usage

Once running, just type your question:

```
You: How do I install a package on Ubuntu?
You: What does chmod +x do?
You: How do I set my ANTHROPIC_API_KEY permanently?
```

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show the full built-in Linux quick-reference |
| `/tips <category>` | Show tips for one category (e.g. `/tips packages`) |
| `/categories` | List all available tip categories |
| `/reset` | Clear the conversation history |
| `/exit` or `/quit` | Leave the program |

### Tip Categories

`navigation` · `files` · `packages` · `processes` · `network` · `permissions` · `python` · `claude`

---

## Project Structure

```
Claude-Linux-Helper/
├── main.py          # CLI entry point
├── agent.py         # Claude conversation agent
├── config.py        # API key & model configuration
├── linux_tips.py    # Built-in offline Linux quick-reference
├── requirements.txt # Python dependencies
├── setup.sh         # Ubuntu/Debian one-shot setup script
└── tests/
    └── test_agent.py
```

---

## Running Tests

```bash
pip3 install pytest
python3 -m pytest tests/ -v
```

---

## License

MIT – see [LICENSE](LICENSE).
