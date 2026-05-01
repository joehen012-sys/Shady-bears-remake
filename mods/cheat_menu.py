"""
Cheat Menu Mod
--------------
Press  F3  during gameplay to toggle the cheat menu.
W / S  or  Up / Down  to move selection.
Enter  to toggle a cheat ON/OFF, or activate a one-shot action.

Set Enemies row: press Enter to open a text box, type a number, Enter to apply.
"""
import pygame

# ── internal state ────────────────────────────────────────────────────────────
_open = False
_selected = 0

_cheats = [
    {"label": "God Mode",       "key": "god_mode",
        "active": False, "action": False},
    {"label": "Infinite Jumps", "key": "inf_jumps",
        "active": False, "action": False},
    {"label": "Speed Boost",    "key": "speed_boost",
        "active": False, "action": False},
    {"label": "No Gravity",     "key": "no_gravity",
        "active": False, "action": False},
    {"label": "Acorn Magnet",   "key": "acorn_magnet",
        "active": False, "action": False},
    {"label": "+1 Acorn",       "key": "add_acorn",
        "active": False, "action": True},
    {"label": "+1 Enemy",       "key": "spawn_bear",
        "active": False, "action": True},
    {"label": "Set Enemies",    "key": "set_enemies",   "active": False, "action": True,
     "textbox": True},
]

_textbox_open = False
_textbox_text = ""

_prev_up = False
_prev_down = False
_prev_f3 = False
_orig_speed = None
_orig_gravity = None


def _cheat(key):
    for c in _cheats:
        if c["key"] == key:
            return c["active"]
    return False


# ── mod hooks ─────────────────────────────────────────────────────────────────

def on_load(context):
    pass


def on_unload():
    global _textbox_open
    import player as pm
    if _orig_speed is not None:
        pm.MOVE_SPEED = _orig_speed
    for c in _cheats:
        c["active"] = False
    _textbox_open = False


def on_event(event):
    global _open, _textbox_open, _textbox_text, _selected
    from mod_manager import mod_manager

    if not _open:
        return
    if event.type != pygame.KEYDOWN:
        return

    if _textbox_open:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            try:
                count = max(0, int(_textbox_text))
            except ValueError:
                count = 0
            mod_manager.set_enemy_count = count
            _textbox_open = False
            _textbox_text = ""
        elif event.key == pygame.K_ESCAPE:
            _textbox_open = False
            _textbox_text = ""
        elif event.key == pygame.K_BACKSPACE:
            _textbox_text = _textbox_text[:-1]
        elif event.unicode.isdigit() and len(_textbox_text) < 4:
            _textbox_text += event.unicode
        return

    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        c = _cheats[_selected]
        if c.get("textbox"):
            _textbox_open = True
            _textbox_text = ""
        elif c["action"]:
            if c["key"] == "add_acorn":
                mod_manager.add_acorns += 1
            elif c["key"] == "spawn_bear":
                mod_manager.spawn_bear += 1
        else:
            c["active"] = not c["active"]


def on_update(level, player, dt):
    global _open, _selected, _prev_up, _prev_down, _prev_f3
    global _orig_speed, _orig_gravity, _textbox_open, _textbox_text

    import player as pm
    from mod_manager import mod_manager

    keys = pygame.key.get_pressed()

    f3 = keys[pygame.K_F3]
    if f3 and not _prev_f3:
        _open = not _open
        if not _open:
            _textbox_open = False
            _textbox_text = ""
    _prev_f3 = f3

    if _open and not _textbox_open:
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        if up and not _prev_up:
            _selected = (_selected - 1) % len(_cheats)
        if down and not _prev_down:
            _selected = (_selected + 1) % len(_cheats)
        _prev_up = up
        _prev_down = down
    else:
        _prev_up = _prev_down = False

    mod_manager.paused = _open
    mod_manager.god_mode = _cheat("god_mode")

    if not _open:
        if _cheat("inf_jumps"):
            player.jumps_used = 0

        if _orig_speed is None:
            _orig_speed = pm.MOVE_SPEED
        pm.MOVE_SPEED = _orig_speed * \
            2 if _cheat("speed_boost") else _orig_speed

        if _cheat("no_gravity"):
            player.vel_y = 0.0

        if _cheat("acorn_magnet"):
            MAGNET_RANGE = 150
            for coin in level.coins:
                dx = player.rect.centerx - coin.rect.centerx
                dy = player.rect.centery - coin.rect.centery
                dist = (dx * dx + dy * dy) ** 0.5
                if 0 < dist < MAGNET_RANGE:
                    speed = 6 * dt
                    coin.rect.centerx += int(dx / dist * speed)
                    coin.rect.centery += int(dy / dist * speed)


def on_draw(surface, level, player, camera_x):
    if not _open:
        return

    pygame.font.init()
    font_big = pygame.font.SysFont("consolas", 22, bold=True)
    font_small = pygame.font.SysFont("consolas", 18)

    W, H = surface.get_size()
    panel_w = 340
    row_h = 32
    panel_h = 50 + len(_cheats) * row_h + 36
    px = (W - panel_w) // 2
    py = (H - panel_h) // 2

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((20, 20, 30, 215))
    pygame.draw.rect(panel, (180, 80, 80), (0, 0, panel_w, panel_h), 2,
                     border_radius=6)
    surface.blit(panel, (px, py))

    title = font_big.render("CHEAT MENU  [F3]", True, (255, 80, 80))
    surface.blit(title, (px + (panel_w - title.get_width()) // 2, py + 10))

    for i, cheat in enumerate(_cheats):
        y = py + 50 + i * row_h
        selected = (i == _selected)

        if selected:
            hl = pygame.Surface((panel_w - 20, row_h - 4), pygame.SRCALPHA)
            hl.fill((60, 30, 30, 180))
            surface.blit(hl, (px + 10, y))

        label_col = (255, 255, 200) if selected else (200, 200, 200)
        label_surf = font_small.render(cheat["label"], True, label_col)
        surface.blit(label_surf, (px + 16, y + 6))

        if cheat.get("textbox"):
            if selected and _textbox_open:
                box_w, box_h = 100, 22
                box_x = px + panel_w - box_w - 12
                box_y = y + 5
                pygame.draw.rect(surface, (240, 240, 255),
                                 (box_x, box_y, box_w, box_h), border_radius=3)
                pygame.draw.rect(surface, (255, 80, 80),
                                 (box_x, box_y, box_w, box_h), 2, border_radius=3)
                cursor = "|" if (pygame.time.get_ticks() //
                                 400) % 2 == 0 else ""
                txt = font_small.render(
                    _textbox_text + cursor, True, (20, 20, 20))
                surface.blit(txt, (box_x + 6, box_y + 2))
            else:
                hint = font_small.render(
                    "Enter #", True,
                    (255, 200, 50) if selected else (160, 130, 40))
                surface.blit(
                    hint, (px + panel_w - hint.get_width() - 14, y + 6))
        elif cheat["action"]:
            act = font_small.render(
                "ACT", True,
                (255, 200, 50) if selected else (160, 130, 40))
            surface.blit(act, (px + panel_w - act.get_width() - 14, y + 6))
        else:
            status = "ON " if cheat["active"] else "OFF"
            status_col = (80, 255, 80) if cheat["active"] else (180, 80, 80)
            st = font_small.render(status, True, status_col)
            surface.blit(st, (px + panel_w - st.get_width() - 14, y + 6))

    if _textbox_open:
        hint_txt = "type a number   Enter=apply   Esc=cancel"
    else:
        hint_txt = "W/S move   Enter toggle / activate"
    hint = font_small.render(hint_txt, True, (120, 120, 140))
    surface.blit(
        hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 26))
