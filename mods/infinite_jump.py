import pygame

_label_font = None
_active = False


def on_load(context):
    """Called once when this mod is enabled."""
    global _label_font, _active
    _label_font = None  # lazily initialised on first draw
    _active = True
    print("[infinite_jump] Infinite Jump enabled.")


def on_level_start(level, player):
    """Set a very high jump count so the player never runs out."""
    player.max_jumps = 9999


def on_update(level, player, dt):
    """Reset jumps_used every frame so the player always has jumps available."""
    if _active:
        player.jumps_used = 0


def on_draw(surface, level, player, camera_x):
    """Draw a badge showing the mod is active."""
    global _label_font
    if not _active:
        return
    if _label_font is None:
        _label_font = pygame.font.SysFont("Arial", 18, bold=True)
    text = _label_font.render("[INFINITE JUMP]", True, (100, 220, 255))
    surface.blit(text, (5, surface.get_height() - 28))


def on_unload():
    """Called when the mod is disabled."""
    global _active
    _active = False
    print("[infinite_jump] Infinite Jump disabled.")
