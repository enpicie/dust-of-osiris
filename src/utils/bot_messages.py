# Central place to configure all the bot's static messages — where its
# "personality" shows. Keep user-facing copy here, not inline in commands.
# MIRROR: jobs/deferred_worker/worker_messages.py — keep in sync (GENERAL_ERROR, INVALID_STARTGG_PROFILE)

#############################
# Error Messages           #
#############################
GENERAL_ERROR = "Something went wrong! Please try again in a moment."
REQUIRE_MANAGE_SERVER = "Sorry! Only users with the 'Manage Server' permission can do that."
SERVER_ONLY = "This command only works inside a server."

#############################
# Matchmaking              #
#############################
INVALID_STARTGG_PROFILE = (
    "That doesn't look like a start.gg discriminator. It's the 8-character code next to "
    "your name on your start.gg profile, like `a1b2c3d4`. Run `/matchmaking-help` for where to find it."
)
CHECKING_STARTGG = "⏳ Checking your start.gg results..."
UPDATING_ROLES = "⏳ Updating your roles..."
MATCHMAKING_HELP = (
    "**Finding your start.gg discriminator**\n"
    "1. Log in at start.gg and open your profile.\n"
    "2. Your discriminator is the 8-character code next to your name, like `a1b2c3d4`. "
    "It's also the end of your profile link: `start.gg/user/a1b2c3d4`.\n"
    "\n"
    "**Connect Discord on start.gg**\n"
    "So I can confirm the account is yours, connect this Discord account in your start.gg "
    "account settings (Connections) and make it visible on your profile.\n"
    "\n"
    "**Commands**\n"
    "• `/request-matchmaking-role startgg_discriminator`: get the role your results earn. "
    "If I can't confirm the start.gg account is yours, you get **Fighter**.\n"
    "• `/results-view startgg_discriminator`: see the results your role is based on.\n"
    "• `/remove-matchmaking-role`: drop your Novice, Ascended or Elite role.\n"
    "• `/get-fighter-role` / `/remove-fighter-role`: **Fighter** is open to everyone "
    "and works alongside any other matchmaking role.\n"
    "• `/appeal-matchmaking-role`: think you qualify for more? Find out how to appeal."
)
APPEAL = (
    "To appeal your matchmaking role, contact @enpicie with links to the start.gg "
    "results that support the role you want."
)
