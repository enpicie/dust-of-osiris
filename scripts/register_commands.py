import sys
import os
import time
from pathlib import Path

import requests

# --- Add src/ to sys.path so we can import command_map ---
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.append(str(SRC_DIR))

import commands.command_map as command_map  # noqa: E402 — imported after sys.path bootstrap

APP_ID = os.environ.get("DISCORD_APP_ID") # Repo Var
TOKEN = os.environ.get("DISCORD_BOT_TOKEN") # Repo Secret — set in $GITHUB_ENV by the workflow
COMMAND_NAME = os.environ.get("COMMAND_NAME") # Workflow Input

if not TOKEN or not APP_ID:
    raise RuntimeError("DISCORD_BOT_TOKEN and DISCORD_APP_ID must be set as environment variables")

# MIRROR: keep in sync with utils/discord_api_helper.DISCORD_API_BASE_URL
API_URL = f"https://discord.com/api/v10/applications/{APP_ID}/commands"


def build_command_payload(name: str, entry: dict) -> dict:
    # Convert a CommandEntry TypedDict into a Discord API payload.
    payload = {
        "name": name,
        "description": entry["description"] or "No description",
        "type": 1,  # 1 = slash command
        "options": [param.to_dict() for param in entry.get("params", [])],
    }
    return payload


def _matches(name: str, target: str) -> bool:
    """
    Returns True if the command name matches the target.
    - Exact match: name == target
    - Prefix match: name starts with target + "-" (e.g. "admin" matches "admin-ban")
    """
    return name == target or name.startswith(target + "-")


def main():
    """Register the commands matching COMMAND_NAME (or all) with the Discord API."""
    normalized = COMMAND_NAME.strip().lower()
    should_register_all = normalized == "all"
    # Prefix mode when input has no hyphen and isn't 'all' (e.g. "note", "general")
    # but also supports exact names like "admin-ban" or hyphenated prefixes
    is_multi = should_register_all or not any(normalized == name for name in command_map.command_map)
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json",
    }

    failed_commands = []
    matched_any = False

    for name, entry in command_map.command_map.items():
        if should_register_all or _matches(name, normalized):
            matched_any = True
            print(f"Registering command `{name}`")
            payload = build_command_payload(name, entry)
            response = requests.post(API_URL, headers=headers, json=payload)

            if response.status_code in (200, 201):
                print(f"✅ Registered command: {name}")
            else:
                print(f"❌ Failed to register command: {name} ({response.status_code})")
                print(f"PAYLOAD: {payload}")
                print(f"RESPONSE: {response.text}")
                failed_commands.append(name)

            if is_multi:
                # Rate limit gap when registering multiple commands
                time.sleep(10)
            else:
                break
        else:
            print(f"Skipping: {name}")

    if not should_register_all and not matched_any:
        raise RuntimeError(f"No commands found matching '{COMMAND_NAME}'")

    if failed_commands:
        failed_list = ', '.join(failed_commands)
        fail_message = f"Failed to register commands: {failed_list}"
        print(fail_message)
        raise RuntimeError(fail_message)


if __name__ == "__main__":
    main()
