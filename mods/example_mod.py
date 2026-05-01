"""
Example Mod — Speed Boost
Demonstrates all available mod hooks.
When enabled, this mod increases the player's move speed by 50%.
"""

import pygame

_ORIGINAL_SPEED = None
_label_font = None
_active = False


def on_load(context):
    """Called once when this mod is enabled."""
    global _ORIGINAL_SPEED, _label_font, _active
    import player as player_module
    _ORIGINAL_SPEED = player_module.MOVE_SPEED
    player_module.MOVE_SPEED = int(_ORIGINAL_SPEED * 1.5)
    _label_font = None  # lazily initialised on first draw
    _active = True
    print("[example_mod] Speed Boost enabled — move speed:", player_module.MOVE_SPEED)


def on_level_start(level, player):
    """Called each time a new level starts."""
    print(f"[example_mod] Level started: {level.name}")


def on_update(level, player, dt):
    """Called every game-logic frame (after normal player update)."""
    pass  # nothing extra needed for speed boost


def on_draw(surface, level, player, camera_x):
    """Called after all normal game drawing — overlay HUD badge."""
    global _label_font
    if _label_font is None:
        _label_font = pygame.font.SysFont("consolas", 18)
    badge = _label_font.render("MOD: Speed Boost active", True, (255, 220, 80))
    surface.blit(badge, (10, surface.get_height() - 28))


def on_unload():
    """Called when the mod is disabled — restore original speed."""
    global _active
    if not _active:
        return
    import player as player_module
    if _ORIGINAL_SPEED is not None:
        player_module.MOVE_SPEED = _ORIGINAL_SPEED
    _active = False
    print("[example_mod] Speed Boost disabled — move speed restored.")
