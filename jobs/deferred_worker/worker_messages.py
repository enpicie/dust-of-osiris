# MIRROR: src/utils/bot_messages.py — keep in sync (independent Lambda packaging prevents imports)
GENERAL_ERROR = "Something went wrong! Please try again in a moment."

#############################
# Matchmaking              #
#############################
# MIRROR: src/utils/bot_messages.py INVALID_STARTGG_PROFILE
INVALID_STARTGG_PROFILE = (
    "That doesn't look like a start.gg discriminator. It's the 8-character code next to "
    "your name on your start.gg profile, like `a1b2c3d4`. Run `/matchmaking-help` for where to find it."
)
STARTGG_PROFILE_NOT_FOUND = "I couldn't find a start.gg user with that discriminator."
STARTGG_NOT_LINKED = "I couldn't find a Discord account connected to that start.gg account."
STARTGG_LINKED_TO_SOMEONE_ELSE = "That start.gg account is connected to a different Discord account."
# Follows any of the three above when a role is requested; the member gets Fighter.
LINK_DISCORD_TO_STARTGG = (
    "\nTo get the role your results earn, connect this Discord account in your start.gg "
    "account settings (Connections), make it visible on your profile, then run "
    "`/request-matchmaking-role` again with your start.gg discriminator."
)
STARTGG_UNAVAILABLE = "😔 I couldn't get a response from start.gg. Please try again in a few minutes."

ROLES_NOT_CONFIGURED = (
    "You would get the {roles} matchmaking {noun}, but matchmaking roles aren't set up "
    "in this server yet, so I didn't change any roles."
)
ROLE_UPDATE_FAILED = (
    "I couldn't update your roles. A server admin needs to give me **Manage Roles** and "
    "rank my role above the matchmaking roles."
)

# {roles} is e.g. "**Elite** and **Ascended**"; {noun} is "role" or "roles".
ROLE_GRANTED = "✅ You now have the {roles} matchmaking {noun}."
ROLE_ALREADY_HELD = "You already have the {roles} matchmaking {noun}."
ROLE_ALREADY_HIGHER = (
    "You already have the {roles} matchmaking {noun}. Your results now point to **{tier}**, "
    "but roles only move up, so nothing changed."
)
QUALIFYING_RESULT = "\nQualifying result: {label}: {result}."
NOVICE_EXPLANATION = "\nI didn't find a result of {fighter} yet."
FIGHTER_OPEN_TO_EVERYONE = "\nAnyone can pick up **Fighter** too: use `/get-fighter-role`."
APPEAL_HINT = "\nThink you qualify for more? Use `/appeal-matchmaking-role`."

ROLES_REMOVED = "✅ Removed your {roles} matchmaking {noun}."
NO_ROLE_TO_REMOVE = "You don't have a Novice, Ascended or Elite matchmaking role."
FIGHTER_KEPT = "\nYou still have **Fighter**; use `/remove-fighter-role` to drop it."
NO_FIGHTER_TO_REMOVE = "You don't have the **Fighter** role."

RESULTS_HEADER = "**Matchmaking results for start.gg `{slug}`**\nEligible role: **{tier}**. Checked {count} MBAACC events."
RESULTS_QUALIFYING_HEADER = "\n**Qualifying results**"
RESULTS_OTHER_HEADER = "\n**Other results** (most recent first)"
RESULTS_NONE = "\nNo MBAACC results found on this profile."
RESULTS_TRUNCATED = "…and {count} more."
