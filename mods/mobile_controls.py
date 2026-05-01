"""
Mobile Controls Mod
-------------------
Draws virtual on-screen buttons (Left, Right, Jump) and injects synthetic
key events so the game responds to mouse/touch clicks as if the matching
keyboard keys were pressed.

Buttons appear in the lower-left / lower-right of the screen.
"""

import pygame
import settings

# ── layout constants ──────────────────────────────────────────────────────────
_BTN_SIZE     = 70          # square side length in pixels
_BTN_MARGIN   = 16          # gap from screen edge
_BTN_GAP      = 10          # gap between left/right buttons
_BTN_ALPHA    = 160         # button background opacity (0-255)
_BTN_COLOR    = (255, 255, 255)
_BTN_ACTIVE   = (100, 200, 255)
_BTN_BORDER   = (180, 180, 180)
_ARROW_COLOR  = (20, 20, 20)
_FONT_SIZE    = 30

# State: which virtual buttons are currently held
_held = {"left": False, "right": False, "jump": False}

# pygame synthetic key codes to inject
_KEY_LEFT  = None
_KEY_RIGHT = None
_KEY_JUMP  = None

# Rects computed each frame (rebuilt when screen size changes)
_rects: dict = {}
_screen_size = (0, 0)

_font = None


def on_load(context):
    global _KEY_LEFT, _KEY_RIGHT, _KEY_JUMP, _font
    _font = None  # rebuilt lazily after pygame.display is ready
    _refresh_keys()


def on_event(event):
    if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.FINGERDOWN, pygame.FINGERUP):
        return

    if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        pressed = (event.type == pygame.MOUSEBUTTONDOWN)
        pos     = event.pos
    else:
        # Touch: scale finger position to window pixels
        w, h = pygame.display.get_surface().get_size()
        pos     = (int(event.x * w), int(event.y * h))
        pressed = (event.type == pygame.FINGERDOWN)

    _build_rects()
    for name, rect in _rects.items():
        if rect.collidepoint(pos):
            _set_held(name, pressed)


def on_update(level, player, dt):
    # Rebuild rects if window has been resized
    _build_rects()


def on_draw(surface, level, player, camera_x):
    global _font
    if _font is None:
        _font = pygame.font.SysFont(None, _FONT_SIZE)

    _build_rects()
    for name, rect in _rects.items():
        held = _held.get(name, False)
        bg   = _BTN_ACTIVE if held else _BTN_COLOR
        _draw_button(surface, rect, name, bg)


def on_unload():
    # Release any held buttons so the player doesn't get stuck moving
    for name in list(_held):
        _set_held(name, False)


# ── helpers ───────────────────────────────────────────────────────────────────

def _refresh_keys():
    global _KEY_LEFT, _KEY_RIGHT, _KEY_JUMP
    kb = settings.key_bindings
    _KEY_LEFT  = _resolve_key(kb.get("left",  "a"))
    _KEY_RIGHT = _resolve_key(kb.get("right", "d"))
    _KEY_JUMP  = _resolve_key(kb.get("jump",  "space"))


def _resolve_key(name):
    if not name:
        return pygame.K_SPACE
    name = name.strip()
    if len(name) == 1:
        return ord(name.lower())
    special = {
        "space": pygame.K_SPACE, "up": pygame.K_UP,
        "left": pygame.K_LEFT, "right": pygame.K_RIGHT,
    }
    return special.get(name.lower(), pygame.K_SPACE)


_KEY_MAP = {"left": None, "right": None, "jump": None}


def _get_keycode(name):
    _refresh_keys()
    return {"left": _KEY_LEFT, "right": _KEY_RIGHT, "jump": _KEY_JUMP}.get(name)


def _set_held(name, pressed):
    if _held.get(name) == pressed:
        return
    _held[name] = pressed
    keycode = _get_keycode(name)
    if keycode is None:
        return
    if pressed:
        ev = pygame.event.Event(pygame.KEYDOWN, {
            "key": keycode, "mod": 0, "unicode": "", "scancode": 0
        })
    else:
        ev = pygame.event.Event(pygame.KEYUP, {
            "key": keycode, "mod": 0, "unicode": "", "scancode": 0
        })
    pygame.event.post(ev)


def _build_rects():
    global _rects, _screen_size
    surf = pygame.display.get_surface()
    if surf is None:
        return
    w, h = surf.get_size()
    if (w, h) == _screen_size and _rects:
        return
    _screen_size = (w, h)

    b  = _BTN_SIZE
    m  = _BTN_MARGIN
    g  = _BTN_GAP
    by = h - m - b  # button top y

    _rects = {
        "left":  pygame.Rect(m,             by, b, b),
        "right": pygame.Rect(m + b + g,     by, b, b),
        "jump":  pygame.Rect(w - m - b,     by, b, b),
    }


def _draw_button(surface, rect, name, bg_color):
    # Semi-transparent background
    overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    overlay.fill((*bg_color, _BTN_ALPHA))
    surface.blit(overlay, rect.topleft)

    # Border
    pygame.draw.rect(surface, _BTN_BORDER, rect, 2, border_radius=10)

    # Arrow / label
    cx, cy = rect.centerx, rect.centery
    ac = _ARROW_COLOR
    if name == "left":
        pts = [(cx + 14, cy - 14), (cx - 14, cy), (cx + 14, cy + 14)]
        pygame.draw.polygon(surface, ac, pts)
    elif name == "right":
        pts = [(cx - 14, cy - 14), (cx + 14, cy), (cx - 14, cy + 14)]
        pygame.draw.polygon(surface, ac, pts)
    elif name == "jump":
        pts = [(cx - 14, cy + 14), (cx, cy - 16), (cx + 14, cy + 14)]
        pygame.draw.polygon(surface, ac, pts)
