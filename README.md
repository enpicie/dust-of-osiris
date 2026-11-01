# dust-of-osiris

Discord bot that looks up a user's tournament results on
[start.gg](https://start.gg) and determines which matchmaking role(s) they're
eligible for.

Serverless, on AWS Lambda, generated from
[discord-bot-template](https://github.com/enpicie/discord-bot-template).

Discord sends each slash command as an HTTP POST to API Gateway, which invokes
the bot Lambda. The Lambda checks Discord's signature, looks the command up in
the command map, runs it, and returns the reply.

```
Discord ──POST──▶ API Gateway ──▶ bot Lambda (src/) ──reply──▶ Discord
```

The bot Lambda also uses:
- **SQS → deferred worker Lambda** for commands that take longer than 3s ([Deferred commands](#deferred-commands))
- **Secrets Manager** for the bot token, for Discord REST calls ([Bot token](#bot-token))

## One-time setup

1. **Discord apps.** Create a dev app and a prod app in the
   [Developer Portal](https://discord.com/developers/applications). For each:
   - **Public Key** → `DISCORD_PUBLIC_KEY_DEV` / `_PROD` in [config.env](./config.env) (public, safe to commit)
   - **Application ID** → repo **variable** `DISCORD_APP_ID_DEV` / `_PROD`
   - **Bot Token** (Bot tab → Reset Token) → repo **secret** `DISCORD_BOT_TOKEN_DEV` / `_PROD`
2. **AWS access.** The pipelines use the org-level secrets
   `AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS` (Terraform) and `AWS_ROLE_ARN_S3`
   (artifact upload). Repos in the `enpicie` org inherit them.
3. **Deploy dev.** Push to any non-`main` branch.
4. **Point Discord at it.** Copy the `interactions_endpoint_url` Terraform output
   (in the deploy job's log) into the dev app's **General Information →
   Interactions Endpoint URL**. It has the shape
   `https://<api-id>.execute-api.<region>.amazonaws.com/dev/dust-of-osiris`.
   Discord pings it to verify when you save, and the bot answers the ping.
5. **Register commands.** Run the Dev Pipeline from the Actions tab with
   *Run Discord command registration* checked (see
   [Command registration](#command-registration)). Invite the bot
   (OAuth2 → URL Generator → scopes `bot` + `applications.commands`) and try `/ping`.
6. **Go to prod.** Push a version tag (`git tag 1.0.0 && git push origin 1.0.0`).
   The Release Pipeline deploys prod and registers every command. Point the prod
   app's Interactions Endpoint URL at the prod output the same way as step 4.

## Command registration

Slash commands must be registered with Discord before they show up in the
client. [scripts/register_commands.py](./scripts/register_commands.py) reads
`command_map` and registers each entry through Discord's API, using the
`DISCORD_APP_ID_*` repo variable and `DISCORD_BOT_TOKEN_*` secret for the
environment.

| When | How | What gets registered |
|---|---|---|
| Every prod release (tag push) | Automatic: the Release Pipeline's `register-commands` job runs after deploy | All commands |
| A dev deploy | Opt-in: run **Dev Pipeline** manually with *Run Discord command registration* checked | All commands |
| Any time | Run **Register Discord Bot Slash Commands** from the Actions tab, picking `dev` or `prod` | One command (`ping`), a prefix (`admin` → every `admin-*` command), or `all` |

Dev registration is opt-in because a plain push already deploys dev, and
re-registering every command on every push is slow. The script waits 10s
between commands to stay under Discord's rate limit.

Run this to list every command name the map defines:

```bash
PYTHONPATH=src python scripts/list_commands.py
```

Registration creates and updates commands, but it never deletes them. If you
rename or remove a command, delete the old one through Discord's API.
Global commands can take a while to appear in the Discord client.

## How commands work

Commands are discovered from a single dict, `command_map`.

- Each group lives in `src/commands/<group>/` and exports a `CommandMapping` from
  its `mapping.py`.
- [src/commands/command_map.py](./src/commands/command_map.py) merges the groups.
- [src/bot.py](./src/bot.py) dispatches from that dict, and
  [scripts/register_commands.py](./scripts/register_commands.py) registers every
  entry with Discord. So adding an entry to a `mapping.py` is all it takes for a
  command to be dispatched and registered.

```python
"echo": {
    "function": my_commands.echo,                 # (DiscordEvent, AWSServices) -> ResponseMessage
    "description": "Repeat what you say",         # ≤100 chars (Discord limit)
    "params": [
        CommandParam(
            name="text", description="What to repeat",
            param_type=AppCommandOptionType.string, required=True, choices=None,
            # autocomplete=True, autocomplete_handler=my_handlers.text_autocomplete,
        ),
    ]
},
```

**To add a group:** create `src/commands/<group>/` with `__init__.py`,
`<group>_commands.py` and `mapping.py`, then add one line for it to
`command_map.py`.

Error handling:
- Raise `ValueError("message")` from a command, and the user sees that message.
- Any other exception is logged, and the user gets `bot_messages.GENERAL_ERROR`.
- `tests/commands/test_command_map.py` checks every entry against Discord's
  registration rules, so a bad name or a description over 100 characters fails
  in CI, not at registration.

## Starter commands

| Command | Group | Shows |
|---|---|---|
| `/ping` | `general` | The minimum: endpoint, signature check, dispatch |
| `/slow-echo text` | `deferred_example` | The deferred pattern: ⏳ placeholder, then a followup from the worker |

Replace the example groups with your own (and update their lines in
`command_map.py`) once you've built your own commands.

## Deferred commands

Discord drops any reply that takes longer than **3 seconds**. Commands that might
take longer (external APIs, bulk writes, file generation) are split in two:

1. **Bot Lambda:** validate the input (bad input still gets an instant reply),
   call `deferred_dispatch.dispatch("<command>", event, aws_services)`, and
   return a `⏳` placeholder.
2. **Worker Lambda** ([jobs/deferred_worker/](./jobs/deferred_worker/)): SQS
   triggers it with the whole interaction. It looks up the handler in
   `_COMMAND_HANDLERS`, runs it, and posts the result as a followup to the
   original interaction.

Followups are authenticated by the interaction's own token, which is valid for
15 minutes, so the worker doesn't need the bot token for them. The worker is
packaged on its own and **cannot import `src/`**. Code needed on both sides is
copied, with a `MIRROR:` comment on each copy.

If a handler raises, the worker posts the general error instead of re-raising.
That stops SQS from re-running the command and posting a duplicate reply. A
message that still fails 3 times (e.g. the followup POST itself failed) moves
to the `-dlq` queue, where you can inspect it.

## Bot token

Replying to a command doesn't need the bot token. It's only needed for
**Discord REST calls** like assigning roles, posting to another channel, or
reading guild info. For those:

- The token is stored in Secrets Manager (`dust-of-osiris-discord-bot-token-<env>`).
- The Lambdas get only the secret's **name** as an env var, and
  [discord_api_helper.py](./src/utils/discord_api_helper.py) fetches the value
  once per warm container.
- It's never a plaintext env var, and it's never logged.

Any other secret your bot needs should follow the same pattern.

## CI/CD

| Trigger | Pipeline | Does |
|---|---|---|
| Push to non-`main` branch | Dev Pipeline | tests + lint + `terraform validate` → deploy dev |
| Manual (Actions tab) | Dev Pipeline | same, optionally registers commands |
| Push tag `X.Y.Z` | Release Pipeline | tests → deploy prod → register all commands |
| Manual | Register Discord Bot Slash Commands | register one command, a prefix (`admin` = `admin-*`), or `all` |

Deploys run as one Terraform root (`terraform/infra`). State is stored in S3 at
`projects/dust-of-osiris/<env>/infra.tfstate`, managed by
`enpicie/gh-action-workflow-terraform-run`. Lambda layers are rebuilt only when a
`requirements.txt` changes. Use *force_rebuild_layer* to override.

Local checks:

```bash
make test
```

```bash
make lint
```

There is no local Discord stack. Interactions need the deployed endpoint, so test
end to end on dev.

## Conventions

The code style is the same as Adomi's: imports through module aliases, mentions
through `message_helper`, a `[name]` prefix on every `print` in `src/`, and
`logger` in `jobs/`. The full rules are in [CLAUDE.md](./CLAUDE.md).
