# CLAUDE.md

## Project

dust-of-osiris — serverless Discord bot on AWS Lambda, generated from
enpicie/discord-bot-template (the same foundation as Adomi-san). It looks up a
user's tournament results on start.gg (via the deferred worker) and determines
which matchmaking role(s) they are eligible for under a configured rule set.

## Stack

- **Python 3.12** — Lambda runtime; single language across bot, jobs, and scripts.
- **AWS Lambda + API Gateway v2** — serverless HTTP entry point for Discord interactions; zero idle cost.
- **SQS + deferred worker Lambda** — work that can't finish inside Discord's 3-second deadline.
- **Secrets Manager** — Discord bot token and start.gg API key, fetched at runtime by name.
- **start.gg GraphQL API** — player results (MBAACC, videogame ID 22407); called only from the deferred worker.
- **Terraform (S3 remote state via org composite action)** — one root, `terraform/infra`; state keyed per project/env.
- **GitHub Actions** — dev pipeline on non-main pushes, release pipeline on version tags.

## Structure

```
src/                      # Main bot Lambda (Discord interactions)
  lambda_handler.py       # Entry point — Discord signature verification FIRST
  bot.py                  # Dispatches command name → handler via command_map
  commands/<group>/       # One directory per command group
    mapping.py            # Group's CommandMapping dict (self-discovery)
  commands/command_map.py # Merges every group's mapping.py into the registry
  utils/                  # Auth, Discord API, messages, deferred dispatch
jobs/deferred_worker/     # Independent Lambda zip. CANNOT import src/ —
                          # shared logic is duplicated with MIRROR comments.
terraform/infra/          # Bot Lambda, API Gateway, and one file per optional feature
scripts/                  # Discord command registration
tests/                    # pytest unit tests, mirror source layout
```

## Security Rules — Non-Negotiable

- No secret literals anywhere in code, config, comments, or tests.
- Secrets come only from environment variables or AWS Secrets Manager.
- Never log tokens, secrets, or full request/response payloads.
- PII stays out of logs — reference users/servers by ID only.
- Discord signature verification (PyNaCl) must remain the FIRST thing `lambda_handler` does. Never reorder, weaken, or bypass it.

## Conventions

The Code Style rules at the bottom of this file (imports, Discord mentions, logging) are binding. In addition:

- **Import carve-out:** Classes, dataclasses, exceptions, and TypedDicts MAY be from-imported; functions/constants of internal modules must use module-alias imports.
- **Command self-discovery:** to add a command group, create `src/commands/<group>/mapping.py` with the group's `CommandMapping` dict and merge it in `src/commands/command_map.py`. Register with Discord via the register-commands workflow.
- **Jobs are self-contained:** `jobs/<name>/` packages cannot import from `src/`. When logic must exist in both places, duplicate it and mark both copies with a MIRROR comment; never import across the boundary.
- **Job module names are unique across jobs and distinct from `src/`'s top-level names.** Each job imports by bare name, and every job directory plus `src/` share one `sys.path` under pytest. `tests/test_job_module_names.py` enforces both; `handler.py` is the one allowed repeat.
- **Matchmaking rules are data.** Tier qualifiers live in `jobs/deferred_worker/matchmaking_rules.py` (`QUALIFIERS`); change rules there, with a test per rule, then run `python scripts/build_rules_page.py` to regenerate the GitHub Pages rules page (`docs/index.html`; a test fails if it is stale). The worker only ever adds/removes the four matchmaking role IDs, and touches none until all four are configured. Roles only move up: a lower result never replaces a higher role, and moving up removes only lower level roles (Novice). Fighter is universal and a request never removes it. `/remove-matchmaking-role` removes exactly the one role named.
- **Anything that can exceed Discord's 3s deadline defers.** The command handler validates, calls `deferred_dispatch.dispatch(...)`, and returns a `⏳` placeholder; `jobs/deferred_worker` does the work and posts a followup.

## Do Not Modify Without Explicit Instruction

- `src/commands/command_map.py` merge mechanism (command self-discovery depends on it)
- `.github/workflows/` deploy plumbing (workflow-deploy.yml inputs/tf_vars wiring)
- Terraform state keys (`state_key:` values in workflow-deploy.yml)
- `config.env` values once deployed (changing them renames live AWS resources)

## Design Standards

N/A — no UI surface; Discord renders all output.

---

# Code Style

## Imports

Import modules as aliases rather than importing individual functions. This keeps call sites readable — readers can trace methods back to their source without hunting through import lists.

**Do:**
```python
import database.dynamodb_utils as db_helper
db_helper.put_note(...)
```

**Don't:**
```python
from database.dynamodb_utils import put_note, get_note_or_fail
put_note(...)
```

This applies to all internal modules (helpers, utils, db, etc.).

## Discord Mentions

Use `message_helper` for all Discord mention/ping formatting. Never inline the raw Discord syntax manually.

| Mention type | Use |
|---|---|
| User ping | `message_helper.get_user_ping(user_id)` → `<@id>` |
| Channel mention | `message_helper.get_channel_mention(channel_id)` → `<#id>` |
| Role ping | `message_helper.get_role_ping(role_id)` → `<@&id>` |

## Logging

**`src/` code** uses `print` with a `[name]` prefix identifying the subsystem. The name must match the module's domain and be consistent within that file.

```python
print(f"[db] GET NOTE server={server_id} note={note_name!r}")
print(f"[discord] GET /guilds/{guild_id}")
print(f"[notes] Saved note={note_name!r} server={server_id}")
```

**`jobs/` code** uses the standard `logger` (`logging.getLogger()`) — no plain `print`.

Never use a bare `print(...)` without the `[name]` prefix in `src/`, and never use `print` at all in `jobs/`.
