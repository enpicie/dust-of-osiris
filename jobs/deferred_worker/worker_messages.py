# MIRROR: src/utils/bot_messages.py — keep in sync (independent Lambda packaging prevents imports)
GENERAL_ERROR = "Something went wrong. Please try again in a moment."

#############################
# Matchmaking              #
#############################
# {role} / {roles} are silent role mentions (bold labels if role IDs are unset);
# {noun} is "role" or "roles".

# MIRROR: src/utils/bot_messages.py INVALID_STARTGG_PROFILE
INVALID_STARTGG_PROFILE = (
    "Your start.gg discriminator is the 8-char code next to your name on your start.gg profile "
    "like `a1b2c3d4`. Run `/help-startgg` for where to find it."
)
STARTGG_PROFILE_NOT_FOUND = "I could not find a start.gg user with that discriminator."
STARTGG_NOT_LINKED = "I could not find a Discord account connected to that start.gg account."
STARTGG_LINKED_TO_SOMEONE_ELSE = "That start.gg account is connected to a different Discord account."
# Follows any of the three above.
LINK_DISCORD_TO_STARTGG = (
    "\nTo get the role your results earn, connect this Discord account in your start.gg "
    "account settings (Connections), make it visible on your profile, then run "
    "`/request-matchmaking-role` again with your start.gg discriminator."
)
STARTGG_UNAVAILABLE = "I could not get a response from start.gg. Please try again in a few minutes."

ROLES_NOT_CONFIGURED = (
    "You would get the {roles} matchmaking {noun}, but matchmaking roles are not set up "
    "in this server yet, so I did not change any roles."
)
ROLE_UPDATE_FAILED = (
    "I could not update your roles. A server admin needs to give me **Manage Roles** and "
    "rank my role above the matchmaking roles."
)

ROLE_GRANTED = "You now have the {roles} matchmaking {noun}."
ROLE_ALREADY_HELD = "You already have the {roles} matchmaking {noun}."
RESULTS_MAY_BE_MISSING = "\nYour results point to {roles}. Some results may be missing."
QUALIFYING_RESULT = "\nQualifying result: {result}."
# Ascended is explained by its bar, not individual results; the community knows the series.
ASCENDED_BAR = "\nAscended is the same bar as ascending from the [Melt Your Blood](https://start.gg/meltyourblood) series."
NO_RESULTS_FOUND = (
    "\nFound 0 MBAACC results for your profile. Ping {novice} in {channel} to request matches "
    "with other new players."
)
NOVICE_CHANNEL_FALLBACK = "the novice matchmaking channel"
FIGHTER_OPEN_TO_EVERYONE = "\n{fighter} is also available to everyone as the general looking-for-games role."

# One line per tier: how to move up (or that there is nowhere higher).
TIER_HINTS = {
    "novice": "Ascend from Novice by achieving a result of 2-2 or better in a tournament with 24+ entrants.",
    "fighter": "Ascend from Fighter by ascending from the [Melt Your Blood](https://start.gg/meltyourblood) series.",
    "ascended": "Gain Elite status by placing in the top echelon of a highly competitive tournament.",
    "elite": "You are already godlike.",
}

ROLES_REMOVED = "Removed your {roles} matchmaking {noun}."
ROLE_NOT_HELD = "You do not have the {role} matchmaking role."
UNKNOWN_ROLE = "Pick one of the matchmaking roles: Novice, Fighter, Ascended or Elite."

RESULTS_HEADER = "**Matchmaking results for {player}** (start.gg `{slug}`)"
RESULTS_POINT_TO = "\nYour results point to the {roles} matchmaking {noun}."
RESULTS_CHECKED = " Checked {count} MBAACC {events}."
RESULTS_QUALIFYING_LINK = "\n**[Qualifying results]({url})**"
