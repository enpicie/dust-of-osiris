# Central place to configure all the bot's static messages — where its
# "personality" shows. Keep user-facing copy here, not inline in commands.
# MIRROR: jobs/deferred_worker/worker_messages.py — keep in sync (GENERAL_ERROR, INVALID_STARTGG_PROFILE)

#############################
# Error Messages           #
#############################
GENERAL_ERROR = "Something went wrong. Please try again in a moment."
REQUIRE_MANAGE_SERVER = "Sorry! Only users with the 'Manage Server' permission can do that."
SERVER_ONLY = "This command only works inside a server."
UNKNOWN_ROLE = "Pick one of the matchmaking roles: Novice, Fighter, Ascended or Elite."

#############################
# Matchmaking              #
#############################
INVALID_STARTGG_PROFILE = (
    "Your start.gg discriminator is the 8-char code next to your name on your start.gg profile "
    "like `a1b2c3d4`. Run `/help-startgg` for where to find it."
)
CHECKING_AND_ASSIGNING = "Checking your start.gg results and assigning your role..."
CHECKING_STARTGG = "Checking your start.gg results..."
UPDATING_ROLES = "Updating your roles..."

HELP_STARTGG = (
    "**Finding your start.gg discriminator**\n"
    "1. Log in at start.gg and open your profile.\n"
    "2. Your discriminator is the 8-character code next to your name, like `a1b2c3d4`. "
    "It is also the end of your profile link: `start.gg/user/a1b2c3d4`.\n"
    "\n"
    "**Connect Discord on start.gg**\n"
    "So I can confirm the account is yours, connect this Discord account in your start.gg "
    "account settings (Connections) and make it visible on your profile. "
    'Remember to click "Save" after.'
)
# {fighter} is a silent mention of the Fighter role.
HELP_COMMANDS = (
    "**Commands**\n"
    "• `/request-matchmaking-role` - Get a pingable matchmaking role based on your tournament results in start.gg\n"
    "• `/get-fighter-role` - {fighter} is available for everyone even if you have another matchmaking role. "
    "It is the general looking-for-games role.\n"
    "• `/remove-matchmaking-role` - Remove a matchmaking role from yourself.\n"
    "• `/appeal-matchmaking-role` - Learn how to request a higher matchmaking role than the one you were assigned.\n"
    "• `/results-view` - See the start.gg results your matchmaking role is based on.\n"
    "• `/help-startgg` - Find your start.gg discriminator and connect Discord on start.gg."
)
# {novice} / {ascended} / {elite} are silent role mentions.
HELP = (
    "Use `/request-matchmaking-role` to get a pingable matchmaking role based on your start.gg tournament results.\n"
    "To ascend from {novice}, you must achieve a result of 2-2 or better in a tournament with 24+ entrants.\n"
    "To reach {ascended}, you must ascend from the [Melt Your Blood](https://start.gg/meltyourblood) series.\n"
    "To become {elite}, you must reach the top cut of a stacked, highly-competitive tournament "
    "(e.g. Top 16 at CoN 2025, Top 4 CB 2026, requirements vary per event)."
)
APPEAL = "If you want to request a higher role than the one you were assigned, please DM @enpicie with supporting results."
