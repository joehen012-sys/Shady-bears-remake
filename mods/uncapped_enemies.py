"""
Uncapped Enemies Mod
Keeps the original player-history follow behaviour, but enforces a
consistent delay gap between every enemy.

Enemy i uses:
    delay_ms = BASE_DELAY_MS + i * DELAY_STEP_MS

So all enemies trail the player with identical timing gaps.
"""
BASE_DELAY_MS = 2000
DELAY_STEP_MS = 500

_last_count = -1


def on_load(context):
    global _last_count
    _last_count = -1


def on_level_start(level, player):
    global _last_count
    _apply_consistent_delays(level)
    _last_count = len(level.bees)


def on_update(level, player, dt):
    global _last_count
    count = len(level.bees)
    if count != _last_count:
        _apply_consistent_delays(level)
        _last_count = count


def on_unload():
    global _last_count
    _last_count = -1


# ── helpers ──────────────────────────────────────────────────────────────────

def _apply_consistent_delays(level):
    for i, bear in enumerate(level.bees):
        bear.delay_ms = BASE_DELAY_MS + i * DELAY_STEP_MS
