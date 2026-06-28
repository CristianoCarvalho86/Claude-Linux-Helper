"""
Built-in Linux quick-reference tips for new users.
These are shown without requiring an API call.
"""

CATEGORIES = {
    "navigation": {
        "title": "📁  File-system Navigation",
        "tips": [
            ("pwd", "Print current working directory"),
            ("ls -la", "List all files with details (including hidden ones)"),
            ("cd ~", "Go to your home directory"),
            ("cd ..", "Go up one directory level"),
            ("cd /path/to/dir", "Go to an absolute path"),
        ],
    },
    "files": {
        "title": "📄  File Operations",
        "tips": [
            ("cp source dest", "Copy a file"),
            ("mv source dest", "Move or rename a file"),
            ("rm filename", "Delete a file"),
            ("rm -r dirname", "Delete a directory and its contents"),
            ("mkdir dirname", "Create a new directory"),
            ("touch filename", "Create an empty file"),
            ("cat filename", "Display file contents"),
            ("less filename", "View a file page-by-page (q to quit)"),
        ],
    },
    "packages": {
        "title": "📦  Package Management (Ubuntu / Debian)",
        "tips": [
            ("sudo apt update", "Refresh the list of available packages"),
            ("sudo apt upgrade", "Upgrade all installed packages"),
            ("sudo apt install pkg", "Install a package"),
            ("sudo apt remove pkg", "Remove a package"),
            ("apt search keyword", "Search for a package by keyword"),
            ("apt show pkg", "Show details about a package"),
        ],
    },
    "processes": {
        "title": "⚙️   Processes",
        "tips": [
            ("ps aux", "List all running processes"),
            ("top", "Interactive process monitor (q to quit)"),
            ("htop", "Better process monitor – install with: sudo apt install htop"),
            ("kill PID", "Terminate a process by its PID"),
            ("Ctrl+C", "Interrupt the currently running command"),
        ],
    },
    "network": {
        "title": "🌐  Networking",
        "tips": [
            ("ip a", "Show network interfaces and IP addresses"),
            ("ping hostname", "Check connectivity to a host"),
            ("curl -I https://example.com", "Fetch HTTP headers"),
            ("wget https://example.com/file", "Download a file"),
            ("ss -tlnp", "Show listening ports"),
        ],
    },
    "permissions": {
        "title": "🔐  Permissions",
        "tips": [
            ("ls -l", "View file permissions"),
            ("chmod 644 file", "Set rw-r--r-- permissions on a file"),
            ("chmod +x script.sh", "Make a script executable"),
            ("chown user:group file", "Change file owner and group"),
            ("sudo command", "Run a command as root"),
        ],
    },
    "python": {
        "title": "🐍  Python & pip",
        "tips": [
            ("python3 --version", "Check installed Python version"),
            ("pip3 install package", "Install a Python package"),
            ("pip3 install -r requirements.txt", "Install from requirements file"),
            ("python3 -m venv venv", "Create a virtual environment"),
            ("source venv/bin/activate", "Activate the virtual environment"),
        ],
    },
    "claude": {
        "title": "🤖  Setting Up Claude",
        "tips": [
            ("pip3 install anthropic", "Install the Anthropic Python SDK"),
            (
                "export ANTHROPIC_API_KEY='sk-...'",
                "Set your API key for the current session",
            ),
            (
                "echo 'export ANTHROPIC_API_KEY=...' >> ~/.bashrc",
                "Persist the key across sessions",
            ),
            ("source ~/.bashrc", "Reload your shell configuration"),
            (
                "https://console.anthropic.com/",
                "Get your free API key here",
            ),
        ],
    },
}


def get_all_tips() -> str:
    """Return a formatted string of all tip categories."""
    lines: list[str] = []
    for cat in CATEGORIES.values():
        lines.append(f"\n{cat['title']}")
        lines.append("-" * 50)
        for cmd, desc in cat["tips"]:
            lines.append(f"  {cmd:<45} {desc}")
    return "\n".join(lines)


def get_category_tips(category: str) -> str:
    """Return tips for a single category, or an error message."""
    cat = CATEGORIES.get(category.lower())
    if not cat:
        available = ", ".join(CATEGORIES.keys())
        return f"Unknown category '{category}'. Available: {available}"
    lines = [f"\n{cat['title']}", "-" * 50]
    for cmd, desc in cat["tips"]:
        lines.append(f"  {cmd:<45} {desc}")
    return "\n".join(lines)
