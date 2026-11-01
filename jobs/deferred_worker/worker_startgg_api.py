"""start.gg GraphQL reads for matchmaking: a user's linked Discord account and
their MBAACC results.

Never log the API key or full responses; log query names, IDs and status only.
"""
import logging
import re
import time
from dataclasses import dataclass

import requests

import worker_constants as constants
from matchmaking_rules import EventResult

logger = logging.getLogger()

STARTGG_API_URL = "https://api.start.gg/gql/alpha"
MBAACC_VIDEOGAME_ID = 22407

_EVENTS_PER_PAGE = 50          # ~450 query complexity, under start.gg's 1000 cap
_MAX_EVENT_PAGES = 20          # hard cap: 1000 events
_PHASE_GROUP_STANDINGS_PER_PAGE = 64

# Retries for transient failures. At most this many tries per request, waiting
# 1s then 2s between them (or start.gg's Retry-After, capped).
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 1
_MAX_RETRY_WAIT_SECONDS = 30
_sleep = time.sleep  # patched in tests


class StartggUnavailableError(Exception):
    """start.gg could not be reached, rate-limited us, or answered with an error."""


@dataclass(frozen=True)
class StartggUser:
    id: int
    slug: str
    discord_ids: list[str]
    gamer_tag: str | None = None


USER_QUERY = """
query MatchmakingUser($slug: String!) {
  user(slug: $slug) {
    id
    slug
    player { gamerTag }
    authorizations(types: [DISCORD]) { externalId }
  }
}
"""

USER_EVENTS_QUERY = """
query MatchmakingUserEvents($slug: String!, $userId: ID!, $page: Int!, $perPage: Int!, $videogameId: ID!) {
  user(slug: $slug) {
    events(query: {page: $page, perPage: $perPage, filter: {videogameId: [$videogameId]}}) {
      pageInfo { totalPages }
      nodes {
        id
        name
        numEntrants
        startAt
        tournament { name }
        userEntrant(userId: $userId) {
          id
          standing { placement setRecordWithoutByes }
        }
      }
    }
  }
}
"""

PHASE_GROUP_STANDINGS_QUERY = """
query PhaseGroupStandings($phaseGroupId: ID!, $perPage: Int!) {
  phaseGroup(id: $phaseGroupId) {
    standings(query: {page: 1, perPage: $perPage}) {
      nodes { placement entrant { id } }
    }
  }
}
"""

# MIRROR: src/commands/matchmaking/startgg_profile.py — keep in sync
# (independent Lambda packaging prevents imports).
_PROFILE_URL_PATTERN = re.compile(r"start\.gg/user/([A-Za-z0-9_-]+)", re.IGNORECASE)
_PROFILE_SLUG_PATTERN = re.compile(r"(?:user/)?([A-Za-z0-9_-]+)/?")


def parse_profile_slug(value: str) -> str | None:
    """Normalize a start.gg profile URL, 'user/<id>' slug or bare '<id>' to
    'user/<id>'. Returns None if it isn't recognizable as a profile."""
    text = (value or "").strip()
    match = _PROFILE_URL_PATTERN.search(text) or _PROFILE_SLUG_PATTERN.fullmatch(text)
    return f"user/{match.group(1)}" if match else None


class _Retryable(Exception):
    """A failure worth trying again: network trouble, rate limiting, or a 5xx."""

    def __init__(self, retry_after: float | None = None):
        super().__init__()
        self.retry_after = retry_after


def _retry_after_seconds(response: requests.Response) -> float | None:
    try:
        return float(response.headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None


def _post_graphql_once(query_name: str, query: str, variables: dict) -> dict:
    """One GraphQL request. Raises _Retryable for transient failures and
    StartggUnavailableError for ones a retry won't fix."""
    try:
        response = requests.post(
            STARTGG_API_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {constants.get_startgg_api_key()}"},
            timeout=15,
        )
    except requests.RequestException as e:
        logger.warning(f"[startgg] {query_name} request failed: {type(e).__name__}")
        raise _Retryable() from e

    logger.info(f"[startgg] {query_name} status={response.status_code}")
    if response.status_code == 429 or response.status_code >= 500:
        raise _Retryable(_retry_after_seconds(response))
    if not response.ok:
        raise StartggUnavailableError()

    body = response.json()
    if body.get("errors"):
        messages = [error.get("message") or "" for error in body["errors"]]
        logger.error(f"[startgg] {query_name} errors={messages}")
        if any("rate limit" in message.lower() for message in messages):
            raise _Retryable()
        raise StartggUnavailableError()
    return body.get("data") or {}


def _post_graphql(query_name: str, query: str, variables: dict) -> dict:
    """Run one GraphQL query and return its `data`, or raise StartggUnavailableError.
    Transient failures (rate limits, 5xx, network) get at most _MAX_ATTEMPTS
    tries in total; this runs in the deferred worker, so waiting is fine."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return _post_graphql_once(query_name, query, variables)
        except _Retryable as e:
            if attempt == _MAX_ATTEMPTS:
                logger.error(f"[startgg] {query_name} giving up after {attempt} tries")
                raise StartggUnavailableError() from e
            delay = min(e.retry_after if e.retry_after is not None else _BACKOFF_SECONDS * 2 ** (attempt - 1),
                        _MAX_RETRY_WAIT_SECONDS)
            logger.warning(f"[startgg] {query_name} try {attempt}/{_MAX_ATTEMPTS} failed; retrying in {delay:.0f}s")
            _sleep(delay)
    raise StartggUnavailableError()  # unreachable: the loop returns or raises


def fetch_user(slug: str) -> StartggUser | None:
    """Look up a start.gg user and the Discord accounts they've connected. None if no such user."""
    user = _post_graphql("MatchmakingUser", USER_QUERY, {"slug": slug}).get("user")
    if not user:
        return None
    discord_ids = [
        str(auth["externalId"])
        for auth in (user.get("authorizations") or [])
        if auth and auth.get("externalId")
    ]
    return StartggUser(
        id=int(user["id"]),
        slug=user.get("slug") or slug,
        discord_ids=discord_ids,
        gamer_tag=(user.get("player") or {}).get("gamerTag"),
    )


def _parse_record(set_record) -> tuple[int, int]:
    if not isinstance(set_record, dict):
        return 0, 0
    return int(set_record.get("wins") or 0), int(set_record.get("losses") or 0)


def _parse_event(node: dict) -> EventResult | None:
    """One user.events node -> EventResult; None if the user has no entrant in it."""
    entrant = node.get("userEntrant")
    if not entrant:
        return None
    standing = entrant.get("standing") or {}
    wins, losses = _parse_record(standing.get("setRecordWithoutByes"))
    return EventResult(
        event_id=int(node["id"]),
        event_name=node.get("name") or "",
        tournament_name=(node.get("tournament") or {}).get("name") or "",
        num_entrants=node.get("numEntrants") or 0,
        start_at=node.get("startAt"),
        entrant_id=int(entrant["id"]) if entrant.get("id") else None,
        placement=standing.get("placement"),
        wins=wins,
        losses=losses,
    )


def fetch_mbaacc_results(slug: str, user_id: int) -> list[EventResult]:
    """Every MBAACC event the user entered, with their placement and set record."""
    results: dict[int, EventResult] = {}
    page = 1
    while page <= _MAX_EVENT_PAGES:
        data = _post_graphql("MatchmakingUserEvents", USER_EVENTS_QUERY, {
            "slug": slug,
            "userId": user_id,
            "page": page,
            "perPage": _EVENTS_PER_PAGE,
            "videogameId": MBAACC_VIDEOGAME_ID,
        })
        events = ((data.get("user") or {}).get("events")) or {}
        for node in events.get("nodes") or []:
            result = _parse_event(node)
            if result is not None:
                results[result.event_id] = result  # dedupe across pages
        total_pages = (events.get("pageInfo") or {}).get("totalPages") or 0
        if page >= total_pages:
            break
        page += 1
    else:
        logger.warning(f"[startgg] hit event page cap for {slug} pages={_MAX_EVENT_PAGES}")

    logger.info(f"[startgg] {slug} mbaacc_events={len(results)}")
    return list(results.values())


def fetch_phase_group_placements(phase_group_id: int) -> dict[int, int]:
    """Entrant ID -> placement within one phase group (bracket)."""
    data = _post_graphql("PhaseGroupStandings", PHASE_GROUP_STANDINGS_QUERY, {
        "phaseGroupId": phase_group_id,
        "perPage": _PHASE_GROUP_STANDINGS_PER_PAGE,
    })
    nodes = (((data.get("phaseGroup") or {}).get("standings")) or {}).get("nodes") or []
    return {
        int(node["entrant"]["id"]): node["placement"]
        for node in nodes
        if node.get("entrant") and node.get("placement") is not None
    }
