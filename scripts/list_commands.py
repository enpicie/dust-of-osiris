import sys
from pathlib import Path

# --- Add src/ to sys.path so we can import command_map ---
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.append(str(SRC_DIR))

import commands.command_map as command_map  # noqa: E402 — imported after sys.path bootstrap

def main():
    """Print the name of every registered bot command."""
    for name, entry in command_map.command_map.items():
        print(name)

if __name__ == "__main__":
    main()
