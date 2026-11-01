# ── Feature: Matchmaking roles ───────────────────────────────────────────────
# Discord role IDs the deferred worker grants and removes, per environment.
# Role IDs belong to one server, so each env's IDs must come from the server
# that env's bot serves. Not secret.
#
# To change one: Server Settings → Roles → right click the role → Copy Role ID
# (needs Developer Mode on), then redeploy. If any ID in an environment is not
# numeric, the bot works out tiers but changes no roles, so existing roles are
# never disturbed by a half-finished setup.

locals {
  matchmaking_role_ids_by_env = {
    dev = {
      novice   = "1566560991976886613"
      fighter  = "1566561065117024376"
      ascended = "1566561092770201801"
      elite    = "1566562009150128279"
    }
    prod = {
      novice   = "1566562775961051137"
      fighter  = "1566525791615852717"
      ascended = "1566562959533019367"
      elite    = "1566563268053704704"
    }
  }

  matchmaking_role_ids = local.matchmaking_role_ids_by_env[var.deployment_env]
}
