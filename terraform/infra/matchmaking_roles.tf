# ── Feature: Matchmaking roles ───────────────────────────────────────────────
# Discord role IDs the deferred worker grants and removes, per environment.
# Role IDs belong to one server, so each env's IDs must come from the server
# that env's bot serves. Not secret.
#
# Replace each placeholder with the role's ID (Server Settings → Roles → right
# click the role → Copy Role ID; needs Developer Mode on). Until ALL FOUR IDs
# in an environment are numeric, the bot works out tiers but changes no roles,
# so existing roles are never disturbed by a half-finished setup.

locals {
  matchmaking_role_ids_by_env = {
    dev = {
      novice   = "ROLE_ID_PLACEHOLDER"
      fighter  = "ROLE_ID_PLACEHOLDER"
      ascended = "ROLE_ID_PLACEHOLDER"
      elite    = "ROLE_ID_PLACEHOLDER"
    }
    prod = {
      novice   = "ROLE_ID_PLACEHOLDER"
      fighter  = "ROLE_ID_PLACEHOLDER"
      ascended = "ROLE_ID_PLACEHOLDER"
      elite    = "ROLE_ID_PLACEHOLDER"
    }
  }

  matchmaking_role_ids = local.matchmaking_role_ids_by_env[var.deployment_env]
}
