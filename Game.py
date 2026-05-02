import pygame
import random
import collections
import json
import pathlib
import asset_handling
import settings
import player as player_module
from player import Player
from level import LEVELS, ShadyBear, Level, Platform, Coin
from mod_manager import mod_manager

ACORNS_PER_BEAR = 5   # collect this many acorns → one extra enemy spawns


pygame.init()

window_width = settings.WINDOW_WIDTH
window_height = settings.WINDOW_HEIGHT
LOGICAL_WIDTH = 1000
LOGICAL_HEIGHT = 800
texture_pack_data = asset_handling.load_texture_pack(settings.texture_pack)
if texture_pack_data is None:
    texture_pack_data = asset_handling.fallback_texture_pack()


# replaced by _apply_window_mode after init
window = pygame.display.set_mode(
    (window_width, window_height), pygame.RESIZABLE)
pygame.display.set_caption("Shady Bears")


def _hit_row(mouse_y, start_y, line_height, count):
    """Return which menu row the mouse Y falls in, or -1 if none."""
    for i in range(count):
        top = start_y + i * line_height
        if top <= mouse_y < top + line_height:
            return i
    return -1


_WINDOW_MODES = ["window", "borderless", "fullscreen"]


def _apply_window_mode(mode, width, height):
    """Apply fullscreen / borderless / windowed mode and return the new surface."""
    if mode == "fullscreen":
        # Use native monitor mode for reliable fullscreen on all resolutions.
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    elif mode == "borderless":
        info = pygame.display.Info()
        return pygame.display.set_mode((info.current_w, info.current_h), pygame.NOFRAME)
    else:
        return pygame.display.set_mode((width, height), pygame.RESIZABLE)


def _compute_viewport(target_size, source_size, allow_upscale=False):
    """Center source in target, preserving aspect ratio with optional upscaling."""
    target_w, target_h = target_size
    source_w, source_h = source_size

    if source_w <= 0 or source_h <= 0:
        return pygame.Rect(0, 0, target_w, target_h)

    if allow_upscale:
        scale = min(target_w / source_w, target_h / source_h)
    else:
        # Keep gameplay/UI size stable on larger windows and different aspect ratios.
        # Only scale down when the window is smaller than the logical surface.
        scale = min(1.0, target_w / source_w, target_h / source_h)
    draw_w = max(1, int(source_w * scale))
    draw_h = max(1, int(source_h * scale))
    draw_x = (target_w - draw_w) // 2
    draw_y = (target_h - draw_h) // 2
    return pygame.Rect(draw_x, draw_y, draw_w, draw_h)


def _window_to_game_pos(window_pos, viewport, game_size):
    """Convert a window-space mouse position to logical game coordinates."""
    mx, my = window_pos
    if not viewport.collidepoint(mx, my):
        return None

    game_w, game_h = game_size
    local_x = (mx - viewport.x) / viewport.w
    local_y = (my - viewport.y) / viewport.h
    gx = int(local_x * game_w)
    gy = int(local_y * game_h)
    gx = max(0, min(game_w - 1, gx))
    gy = max(0, min(game_h - 1, gy))
    return gx, gy


def _present_scaled(source_surface, target_surface, allow_upscale=False):
    """Letterbox and present source surface to the current window."""
    viewport = _compute_viewport(
        target_surface.get_size(), source_surface.get_size(), allow_upscale=allow_upscale)

    if viewport.size != source_surface.get_size():
        # Blur the backdrop so side areas feel dynamic without looking like
        # duplicated copies of the gameplay frame.
        tw, th = target_surface.get_size()
        blur_w = max(1, tw // 12)
        blur_h = max(1, th // 12)
        tiny = pygame.transform.smoothscale(source_surface, (blur_w, blur_h))
        backdrop = pygame.transform.smoothscale(tiny, (tw, th))
        target_surface.blit(backdrop, (0, 0))
        shade = pygame.Surface(target_surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        target_surface.blit(shade, (0, 0))

        scaled = pygame.transform.smoothscale(source_surface, viewport.size)
        target_surface.blit(scaled, viewport.topleft)
    else:
        target_surface.fill((0, 0, 0))
        target_surface.blit(source_surface, viewport.topleft)
    return viewport


def _parse_color(value, fallback):
    """Accept [r,g,b] / [r,g,b,a] arrays or #RRGGBB strings."""
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return (
                int(value[1:3], 16),
                int(value[3:5], 16),
                int(value[5:7], 16),
            )
        except ValueError:
            return fallback

    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (
                max(0, min(255, int(value[0]))),
                max(0, min(255, int(value[1]))),
                max(0, min(255, int(value[2]))),
            )
        except (TypeError, ValueError):
            return fallback

    return fallback


def _draw_forest_bg(surface, bg_color):
    """Draw a Shady-Bears-style teal birch-forest background."""
    w, h = surface.get_size()
    surface.fill(bg_color)

    # Sky gradient bands (subtle)
    for i in range(8):
        shade = tuple(max(0, c - i * 4) for c in bg_color)
        pygame.draw.rect(surface, shade, (0, i * h // 8, w, h // 8 + 1))

    # Mist / cloud blobs at bottom (cream-white)
    mist = (230, 225, 210, 120)
    for mx, my, mw, mh in [
        (0,   h - 140, 200, 100), (150, h - 100, 280, 90),
        (380, h - 120, 240, 80),  (560, h - 90,  260, 100),
        (760, h - 130, 240, 90),  (940, h - 100, 200, 80),
    ]:
        s = pygame.Surface((mw, mh), pygame.SRCALPHA)
        pygame.draw.ellipse(s, mist, s.get_rect())
        surface.blit(s, (mx, my))

    # Birch tree trunks — tall pale vertical bars
    trunk_positions = [60, 160, 290, 410, 490, 580, 680, 780, 880, 960]
    for tx in trunk_positions:
        trunk_w = 18
        trunk_color = (200, 215, 205)
        dark_color = (160, 175, 168)
        # main trunk
        pygame.draw.rect(surface, trunk_color,
                         (tx - trunk_w // 2, 60, trunk_w, h - 60))
        # dark stripe down centre
        pygame.draw.rect(surface, dark_color,
                         (tx - 2, 60, 4, h - 60))
        # Characteristic birch knot marks
        for ky in range(100, h - 200, 90):
            pygame.draw.ellipse(surface, dark_color,
                                (tx - trunk_w // 2 - 2, ky, trunk_w + 4, 10))

    # Round cloud-like foliage blobs at various heights
    foliage = (175, 210, 195, 140)
    for fx, fy, fr in [
        (60,  80, 55), (160, 60, 50), (290, 90, 60), (410, 70, 50),
        (490, 85, 55), (580, 65, 52), (680, 80, 58), (780, 70, 50),
        (880, 90, 55), (960, 75, 50),
        (120, 160, 40), (350, 140, 42), (530, 155, 38), (730, 145, 44),
    ]:
        s = pygame.Surface((fr * 2, fr * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, foliage, (fr, fr), fr)
        surface.blit(s, (fx - fr, fy - fr))


def draw_main_menu(surface, font, title_font, options, selected_index):
    _draw_forest_bg(surface, (110, 165, 155))

    # Dark translucent overlay so text is readable
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((8, 18, 10, 155))
    surface.blit(overlay, (0, 0))

    w = surface.get_width()
    title = title_font.render("Shady Bears", True, (245, 235, 160))
    info = font.render(
        "UP/DOWN: Select   ENTER: Choose   ESC: Exit", True, (190, 215, 195))

    surface.blit(title, (w // 2 - title.get_width() // 2, 80))
    surface.blit(info,  (w // 2 - info.get_width() // 2, 135))

    start_y = 210
    line_height = 48

    for i, option in enumerate(options):
        if i == selected_index:
            color = (120, 235, 160)
            prefix = "> "
        else:
            color = (215, 225, 215)
            prefix = "  "
        line = font.render(f"{prefix}{option}", True, color)
        surface.blit(line, (w // 2 - line.get_width() //
                     2, start_y + i * line_height))


def draw_level_select_menu(surface, font, title_font, selected_index, level_names):
    _draw_forest_bg(surface, (105, 155, 145))
    ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    ov.fill((8, 18, 10, 165))
    surface.blit(ov, (0, 0))

    title = title_font.render("Select Level", True, (245, 235, 180))
    info = font.render(
        "UP/DOWN: Select  ENTER: Play  ESC: Back", True, (210, 220, 210))
    surface.blit(title, (40, 30))
    surface.blit(info, (40, 75))

    rows = list(level_names) + ["Back"]
    start_y = 170
    line_height = 40
    for i, row in enumerate(rows):
        is_selected = (i == selected_index)
        color = (130, 240, 175) if is_selected else (220, 220, 220)
        prefix = "> " if is_selected else "  "
        text = font.render(f"{prefix}{row}", True, color)
        surface.blit(text, (60, start_y + i * line_height))


def draw_settings_menu(surface, font, title_font, selected_index, packs, pack_selected_index):
    _draw_forest_bg(surface, (110, 165, 155))
    _ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    _ov.fill((8, 18, 10, 170))
    surface.blit(_ov, (0, 0))

    title = title_font.render("Settings", True, (245, 235, 180))
    info = font.render(
        "UP/DOWN: Select  LEFT/RIGHT: Change  ENTER: Open  ESC: Back", True, (210, 210, 210))

    surface.blit(title, (40, 30))
    surface.blit(info, (40, 75))

    if packs:
        selected_pack_name = packs[pack_selected_index]
    else:
        selected_pack_name = "No packs found"

    rows = [
        f"Refresh Rate: {settings.refresh_rate}",
        f"Resolution: {settings.WINDOW_WIDTH} x {settings.WINDOW_HEIGHT}",
        f"Window Mode: {getattr(settings, 'window_mode', 'window')}",
        f"Texture Packs",
        f"Mods",
        "Back"
    ]

    start_y = 150
    line_height = 42

    for i, row in enumerate(rows):
        color = (120, 225, 160) if i == selected_index else (220, 220, 220)
        prefix = "> " if i == selected_index else "  "
        line = font.render(f"{prefix}{row}", True, color)
        surface.blit(line, (60, start_y + i * line_height))


def _coerce_mod_setting_type(value, schema_rule):
    stype = schema_rule.get("type") if isinstance(schema_rule, dict) else None
    if stype in ("bool", "int", "float", "str"):
        return stype
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _get_mod_setting_entries(mod_path):
    status = mod_manager.get_mod_status(mod_path) or {}
    meta = status.get("metadata", {}) if isinstance(status, dict) else {}
    schema = meta.get("settings_schema", {})
    if not isinstance(schema, dict):
        schema = {}
    current = mod_manager.get_mod_settings(mod_path)

    keys = sorted(set(current.keys()) | set(
        schema.keys()), key=lambda k: str(k).lower())
    entries = []
    for key in keys:
        if not isinstance(key, str):
            continue
        rule = schema.get(key, {})
        if not isinstance(rule, dict):
            rule = {}

        value = current[key] if key in current else rule.get("default", "")
        stype = _coerce_mod_setting_type(value, rule)
        choices = rule.get("choices", [])
        if not isinstance(choices, (list, tuple)):
            choices = []

        entries.append({
            "key": key,
            "value": value,
            "type": stype,
            "step": rule.get("step", 1 if stype == "int" else 0.1),
            "min": rule.get("min"),
            "max": rule.get("max"),
            "choices": list(choices),
            "default": rule.get("default"),
        })
    return entries


def _format_mod_setting_value(value, stype):
    if stype == "bool":
        return "ON" if bool(value) else "OFF"
    if stype == "float":
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "0.00"
    return str(value)


def _change_mod_setting(mod_path, setting_entry, direction):
    key = setting_entry["key"]
    stype = setting_entry["type"]
    value = setting_entry["value"]

    if stype == "bool":
        new_value = not bool(value)
    elif setting_entry["choices"]:
        choices = setting_entry["choices"]
        try:
            idx = choices.index(value)
        except ValueError:
            idx = 0
        new_value = choices[(idx + direction) % len(choices)]
    elif stype == "int":
        try:
            step = int(setting_entry.get("step", 1))
        except (TypeError, ValueError):
            step = 1
        try:
            cur = int(value)
        except (TypeError, ValueError):
            cur = 0
        new_value = cur + (step * direction)
    elif stype == "float":
        try:
            step = float(setting_entry.get("step", 0.1))
        except (TypeError, ValueError):
            step = 0.1
        try:
            cur = float(value)
        except (TypeError, ValueError):
            cur = 0.0
        new_value = round(cur + (step * direction), 4)
    else:
        # Free-text strings are not edited in this menu yet.
        return False

    vmin = setting_entry.get("min")
    vmax = setting_entry.get("max")
    if isinstance(new_value, (int, float)) and vmin is not None:
        try:
            new_value = max(new_value, vmin)
        except TypeError:
            pass
    if isinstance(new_value, (int, float)) and vmax is not None:
        try:
            new_value = min(new_value, vmax)
        except TypeError:
            pass

    return mod_manager.set_mod_setting(mod_path, key, new_value, save=True)


def draw_mods_submenu(surface, font, title_font, selected_index, all_mods,
                      panel_focus="list", setting_index=0):
    _draw_forest_bg(surface, (110, 165, 155))
    _ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    _ov.fill((8, 18, 10, 170))
    surface.blit(_ov, (0, 0))

    title = title_font.render("Mod Manager", True, (245, 235, 180))
    info = font.render(
        "TAB: Focus Settings  ENTER: Toggle/Edit  LEFT/RIGHT: Change", True, (210, 210, 210))

    surface.blit(title, (40, 30))
    surface.blit(info, (40, 75))

    start_y = 130
    line_height = 36

    if not all_mods:
        surface.blit(
            font.render("No mods found in mods/ folder.",
                        True, (255, 120, 120)),
            (60, start_y))
    else:
        rows = list(all_mods) + ["Back"]
        for i, row in enumerate(rows):
            is_selected = (i == selected_index)
            color = (120, 225, 160) if is_selected else (220, 220, 220)
            prefix = "> " if is_selected else "  "
            if i < len(all_mods):
                status = "[ON] " if mod_manager.is_enabled(row) else "[OFF]"
                status_color = (100, 220, 100) if mod_manager.is_enabled(
                    row) else (180, 80, 80)
                _ms = mod_manager.get_mod_status(row) or {}
                _display = (_ms.get("metadata") or {}).get("name") or row
                surface.blit(font.render(f"{prefix}{_display}", True, color),
                             (60, start_y + i * line_height))
                surface.blit(font.render(status, True, status_color),
                             (surface.get_width() - 100, start_y + i * line_height))
            else:
                surface.blit(font.render(f"{prefix}{row}", True, color),
                             (60, start_y + i * line_height))

    if all_mods and 0 <= selected_index < len(all_mods):
        selected_path = all_mods[selected_index]
        status = mod_manager.get_mod_status(selected_path) or {}
        meta = status.get("metadata", {})
        setting_entries = _get_mod_setting_entries(selected_path)
        panel_x = min(460, max(260, surface.get_width() // 2))
        panel_y = 125
        panel_w = max(260, surface.get_width() - panel_x - 40)
        panel_h = 290

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((12, 22, 18, 190))
        pygame.draw.rect(panel, (80, 120, 95),
                         panel.get_rect(), 2, border_radius=8)
        surface.blit(panel, (panel_x, panel_y))

        header = font.render("Selected Mod", True, (210, 240, 220))
        name = font.render(meta.get("name", selected_path),
                           True, (255, 255, 210))
        version = font.render(
            f"Version: {meta.get('version', '0.0.0')}", True, (190, 215, 195))
        author = font.render(
            f"Author: {meta.get('author', 'unknown')}", True, (190, 215, 195))
        path_line = font.render(selected_path, True, (170, 190, 175))

        surface.blit(header, (panel_x + 14, panel_y + 10))
        surface.blit(name, (panel_x + 14, panel_y + 42))
        surface.blit(version, (panel_x + 14, panel_y + 76))
        surface.blit(author, (panel_x + 14, panel_y + 106))
        surface.blit(path_line, (panel_x + 14, panel_y + 136))

        desc = (meta.get("description", "") or "No description")[:80]
        desc_line = font.render(f"Desc: {desc}", True, (180, 210, 190))
        surface.blit(desc_line, (panel_x + 14, panel_y + 166))

        settings_header_color = (
            230, 245, 220) if panel_focus == "settings" else (180, 205, 185)
        settings_header = font.render("Settings", True, settings_header_color)
        surface.blit(settings_header, (panel_x + 14, panel_y + 196))

        if setting_entries:
            visible_rows = 3
            clamped_index = max(
                0, min(setting_index, len(setting_entries) - 1))
            start = max(0, clamped_index - (visible_rows - 1))
            end = min(len(setting_entries), start + visible_rows)
            for row_i, entry in enumerate(setting_entries[start:end]):
                absolute_idx = start + row_i
                row_y = panel_y + 224 + row_i * 22
                is_active = panel_focus == "settings" and absolute_idx == clamped_index
                key_color = (135, 245, 175) if is_active else (200, 225, 205)
                val_color = (255, 240, 180) if is_active else (185, 205, 190)
                key_text = font.render(entry["key"], True, key_color)
                value_label = _format_mod_setting_value(
                    entry["value"], entry["type"])
                val_text = font.render(value_label[:20], True, val_color)
                surface.blit(key_text, (panel_x + 18, row_y))
                surface.blit(val_text, (panel_x + panel_w -
                             val_text.get_width() - 12, row_y))
        else:
            none_text = font.render(
                "No settings yet for this mod.", True, (150, 170, 155))
            surface.blit(none_text, (panel_x + 14, panel_y + 224))

        error_text = status.get("error")
        if error_text:
            err = font.render(
                f"Error: {str(error_text)[:48]}", True, (255, 130, 130))
            surface.blit(err, (panel_x + 14, panel_y + panel_h - 26))


def draw_texture_pack_submenu(surface, font, title_font, packs, selected_index, active_pack):
    _draw_forest_bg(surface, (110, 165, 155))
    _ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    _ov.fill((8, 18, 10, 170))
    surface.blit(_ov, (0, 0))

    title = title_font.render("Texture Packs", True, (245, 235, 180))
    info = font.render(
        "UP/DOWN: Select  ENTER: Apply  ESC: Back", True, (210, 210, 210))

    surface.blit(title, (40, 30))
    surface.blit(info, (40, 75))

    rows = list(packs) + ["Back"]
    start_y = 130
    line_height = 36

    for i, row in enumerate(rows):
        is_cursor = i == selected_index
        is_active_pack = i < len(packs) and row == active_pack

        if is_active_pack:
            color = (170, 255, 170)  # Light green for currently applied pack
        elif is_cursor:
            color = (120, 225, 160)
        else:
            color = (220, 220, 220)

        prefix = "> " if is_cursor else "  "
        suffix = " (applied)" if is_active_pack else ""
        display = asset_handling.get_pack_display_name(
            row) if i < len(packs) else row
        line = font.render(f"{prefix}{display}{suffix}", True, color)
        surface.blit(line, (60, start_y + i * line_height))

    # ── Preview panel ────────────────────────────────────────────────────────
    if 0 <= selected_index < len(packs):
        pack_path = packs[selected_index]
        pack_name = asset_handling.get_pack_display_name(pack_path)

        panel_x = min(460, surface.get_width() // 2 + 20)
        panel_y = 120
        panel_w = surface.get_width() - panel_x - 20
        panel_h = 310

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((12, 22, 18, 200))
        pygame.draw.rect(panel_surf, (80, 120, 95),
                         panel_surf.get_rect(), 2, border_radius=8)
        surface.blit(panel_surf, (panel_x, panel_y))

        name_surf = font.render(pack_name, True, (255, 255, 210))
        surface.blit(name_surf, (panel_x + 12, panel_y + 10))

        img_x = panel_x + 12
        img_y = panel_y + 44
        img_w = panel_w - 24
        img_h = panel_h - 56

        preview_img = asset_handling.load_pack_preview_image(pack_path)
        if preview_img is not None:
            scaled = pygame.transform.smoothscale(preview_img, (img_w, img_h))
            surface.blit(scaled, (img_x, img_y))
            pygame.draw.rect(surface, (80, 120, 95),
                             (img_x, img_y, img_w, img_h), 1, border_radius=4)
        else:
            pygame.draw.rect(surface, (20, 35, 28),
                             (img_x, img_y, img_w, img_h), border_radius=4)
            pygame.draw.rect(surface, (60, 90, 70),
                             (img_x, img_y, img_w, img_h), 1, border_radius=4)
            msg1 = font.render("No preview image found.",
                               True, (160, 185, 170))
            msg2 = font.render("Add preview.png to your",
                               True, (130, 155, 140))
            msg3 = font.render("pack folder to show one.",
                               True, (130, 155, 140))
            cy = img_y + img_h // 2 - 28
            for msg in (msg1, msg2, msg3):
                surface.blit(msg, (img_x + img_w // 2 -
                             msg.get_width() // 2, cy))
                cy += 22


def draw_level_complete(surface, font, title_font, level_name, coins, total_coins,
                        elapsed_secs, is_final):
    _draw_forest_bg(surface, (110, 165, 155))
    _ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    _ov.fill((8, 18, 10, 170))
    surface.blit(_ov, (0, 0))
    # Decorative border
    pygame.draw.rect(surface, (60, 110, 60),
                     surface.get_rect().inflate(-20, -20), 4, border_radius=12)

    cx = surface.get_width() // 2
    banner = title_font.render("Level Complete!", True, (245, 220, 80))
    surface.blit(banner, (cx - banner.get_width() // 2, 120))

    surface.blit(font.render(level_name, True, (180, 220, 160)),
                 (cx - font.size(level_name)[0] // 2, 200))

    mins = int(elapsed_secs) // 60
    secs = int(elapsed_secs) % 60
    time_str = f"Time:   {mins:02d}:{secs:02d}"
    coin_str = f"Acorns: {coins} / {total_coins}"
    surface.blit(font.render(time_str, True, (220, 220, 220)),
                 (cx - 80, 280))
    surface.blit(font.render(coin_str, True, (255, 210, 40)),
                 (cx - 80, 320))

    prompt = "Press ENTER to finish!" if is_final else "Press ENTER for next level"
    hint = font.render(prompt, True, (160, 200, 160))
    surface.blit(hint, (cx - hint.get_width() // 2, 420))


def draw_level_maker(surface, font, title_font, cursor_pos, tile_size, placed_tiles,
                     player_start, exit_pos, save_notice, saved_level_label, is_editing,
                     starting_acorns, starting_enemies):
    _draw_forest_bg(surface, (96, 140, 128))
    ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    ov.fill((8, 18, 10, 145))
    surface.blit(ov, (0, 0))

    title = title_font.render("Level Maker", True, (245, 235, 180))
    info = font.render(
        "Arrows: Move  P/Enter: Tile  1: Spawn  2: Exit  S: Save  N: New  ESC: Back",
        True,
        (210, 220, 210),
    )
    info2 = font.render(
        "Hold LMB: Paint  Hold RMB: Erase  A/D: Enemies -/+  Z/X: Acorns -/+",
        True,
        (190, 205, 190),
    )
    info3 = font.render(
        "Q/W: Pick Saved  E: Edit  DEL: Delete",
        True,
        (190, 205, 190),
    )
    surface.blit(title, (40, 24))
    surface.blit(info, (40, 72))
    surface.blit(info2, (40, 100))
    surface.blit(info3, (40, 128))

    w, h = surface.get_size()
    tile_w, tile_h = tile_size

    # Grid
    grid_top = 120
    for gx in range(0, w, tile_w):
        pygame.draw.line(surface, (70, 100, 92), (gx, grid_top), (gx, h), 1)
    for gy in range(grid_top, h, tile_h):
        pygame.draw.line(surface, (70, 100, 92), (0, gy), (w, gy), 1)

    # Placed platform tiles
    for tx, ty in placed_tiles:
        rect = pygame.Rect(tx, ty, tile_w, tile_h)
        pygame.draw.rect(surface, (55, 70, 75), rect, border_radius=2)
        pygame.draw.rect(surface, (95, 110, 115), rect, 2, border_radius=2)

    # Player start marker
    ps = pygame.Rect(player_start[0], player_start[1], 30, 42)
    pygame.draw.rect(surface, (100, 180, 255), ps, 2, border_radius=3)
    surface.blit(font.render("P", True, (120, 220, 255)), (ps.x + 7, ps.y + 8))

    # Exit marker
    ex = pygame.Rect(exit_pos[0], exit_pos[1], 34, 40)
    pygame.draw.rect(surface, (245, 220, 70), ex, 2, border_radius=3)
    surface.blit(font.render("E", True, (255, 240, 140)), (ex.x + 8, ex.y + 8))

    # Cursor
    cx, cy = cursor_pos
    cursor_rect = pygame.Rect(cx, cy, tile_w, tile_h)
    pygame.draw.rect(surface, (120, 245, 170), cursor_rect, 3, border_radius=2)

    if save_notice:
        msg = font.render(save_notice, True, (150, 255, 170))
        surface.blit(msg, (40, h - 36))

    status_prefix = "Editing" if is_editing else "Selected"
    status = font.render(
        f"{status_prefix}: {saved_level_label}", True, (215, 225, 215))
    surface.blit(status, (40, h - 68))
    counts = font.render(
        f"Starting Acorns: {starting_acorns}   Starting Enemies: {starting_enemies}",
        True,
        (215, 225, 215),
    )
    surface.blit(counts, (40, h - 100))


def main():
    global window

    clock = pygame.time.Clock()
    running = True
    menu_state = "main"

    font = pygame.font.SysFont("consolas", 24)
    title_font = pygame.font.SysFont("consolas", 42, bold=True)
    game_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
    fullscreen_scaling = getattr(
        settings, "window_mode", "window") == "fullscreen"
    viewport = _compute_viewport(
        window.get_size(), game_surface.get_size(), allow_upscale=fullscreen_scaling)
    main_options = ["Start Game", "Settings", "Exit"]
    main_selected_index = 0
    settings_selected_index = 0
    level_select_selected_index = 0
    texture_menu_selected_index = 0
    mods_selected_index = 0
    mods_panel_focus = "list"  # "list" or "settings"
    mods_setting_index = 0
    all_mods = []
    level_maker_mod_path = "mods/level_maker.py"
    level_maker_file = pathlib.Path(
        __file__).parent / "mods" / "custom_levels.json"
    lm_tile_size = (80, 20)
    lm_cursor = [0, 120]
    lm_tiles = set()
    lm_player_start = [60, 670]
    lm_exit_pos = [900, 80]
    lm_save_notice = ""
    lm_notice_until_ms = 0
    lm_saved_rows = []
    lm_saved_index = 0
    lm_editing_row_index = None
    lm_mouse_paint = False
    lm_mouse_erase = False
    lm_start_acorns = 3
    lm_start_enemies = 2
    screenshot_notice = ""
    screenshot_notice_until = 0

    # ── Gameplay state ──────────────────────────────────────────────────────
    current_level_index = 0
    player = None
    camera_x = 0
    player_history = collections.deque(maxlen=3600)  # ~60s at 60fps
    game_max_jumps = 2
    game_ms = 0  # game-clock in ms; does NOT advance while paused
    # Original bear counts — used to strip extra bears on reset
    _original_bear_counts = [len(lvl.bees) for lvl in LEVELS]
    base_player_color = player_module.Player.COLOR
    base_player_eye_color = player_module.Player.EYE_COLOR
    pack_style = {
        "background_color": None,
        "background_image": None,
        "platform_color": None,
        "platform_tile": None,
        "exit_color": None,
        "exit_frame_color": None,
    }

    # ── Level progress tracking ─────────────────────────────────────────────
    coins_this_level = 0
    _bears_spawned_extra = 0  # how many extra bears have been added this run
    level_start_time = 0.0   # pygame.time.get_ticks() when level began
    lc_coins = 0             # saved for the level_complete screen
    lc_total_coins = 0
    lc_elapsed = 0.0
    lc_is_final = False

    def get_main_options():
        opts = ["Start Game", "Settings"]
        if mod_manager.is_enabled(level_maker_mod_path):
            opts.append("Level Maker")
        opts.append("Exit")
        return opts

    def get_level_names():
        return [lvl.name for lvl in LEVELS] if LEVELS else ["No levels available"]

    def level_maker_reset():
        nonlocal lm_cursor, lm_tiles, lm_player_start, lm_exit_pos, lm_start_acorns, lm_start_enemies
        lm_cursor = [0, 120]
        lm_tiles = set()
        lm_player_start = [60, 670]
        lm_exit_pos = [900, 80]
        lm_start_acorns = 3
        lm_start_enemies = 2

    def _safe_int_local(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _auto_coin_points(platforms, desired_count=None):
        if not platforms:
            if desired_count is None:
                return [(120, 680)]
            return [] if desired_count <= 0 else [(120, 680)] * desired_count
        sorted_for_items = sorted(
            platforms, key=lambda p: (p.rect.top, p.rect.left))
        coin_platforms = sorted_for_items[:max(
            1, min(3, len(sorted_for_items)))]
        if desired_count is None:
            desired_count = len(coin_platforms)
        desired_count = max(0, min(30, int(desired_count)))

        points = []
        for i in range(desired_count):
            p = coin_platforms[i % len(coin_platforms)]
            stack = i // len(coin_platforms)
            x_offset = ((stack % 3) - 1) * 16
            y_offset = (stack // 3) * 10
            points.append((p.rect.centerx + x_offset,
                          p.rect.top - 20 - y_offset))
        return points

    def _auto_bee_delays(platforms, desired_count=None):
        if desired_count is None:
            desired_count = max(1, min(6, len(platforms) // 3 + 1))
        desired_count = max(0, min(30, int(desired_count)))
        return [2000 + i * 700 for i in range(desired_count)]

    def _read_level_rows():
        if not level_maker_file.exists():
            return []
        try:
            with open(level_maker_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                return [row for row in loaded if isinstance(row, dict)]
        except Exception:
            pass
        return []

    def _write_level_rows(rows):
        level_maker_file.parent.mkdir(parents=True, exist_ok=True)
        with open(level_maker_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=4)

    def _refresh_saved_rows():
        nonlocal lm_saved_rows, lm_saved_index
        lm_saved_rows = _read_level_rows()
        if lm_saved_rows:
            lm_saved_index = max(
                0, min(lm_saved_index, len(lm_saved_rows) - 1))
        else:
            lm_saved_index = 0

    def _row_to_level(row, idx):
        name = str(row.get("name", f"Custom Level {idx + 1}"))
        bg = row.get("bg_color", [95, 140, 125])
        if not isinstance(bg, (list, tuple)) or len(bg) < 3:
            bg = [95, 140, 125]
        bg_color = (_safe_int_local(bg[0], 95), _safe_int_local(
            bg[1], 140), _safe_int_local(bg[2], 125))

        player_start = row.get("player_start", [60, 670])
        if not isinstance(player_start, (list, tuple)) or len(player_start) < 2:
            player_start = [60, 670]

        exit_pos = row.get("exit_pos", [900, 80])
        if not isinstance(exit_pos, (list, tuple)) or len(exit_pos) < 2:
            exit_pos = [900, 80]

        platforms = []
        for p in row.get("platforms", []):
            if isinstance(p, (list, tuple)) and len(p) >= 4:
                x = _safe_int_local(p[0], 0)
                y = _safe_int_local(p[1], 0)
                w = max(8, _safe_int_local(p[2], 80))
                h = max(8, _safe_int_local(p[3], 20))
                platforms.append(Platform(x, y, w, h))
        if not platforms:
            platforms = [Platform(0, 720, 260, 80)]

        coins = []
        for c in row.get("coins", []):
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                coins.append(Coin(_safe_int_local(
                    c[0], 0), _safe_int_local(c[1], 0)))
        if not coins:
            coins = [Coin(x, y) for (x, y) in _auto_coin_points(platforms)]

        bees = []
        for delay in row.get("bees", []):
            bees.append(ShadyBear(delay_ms=max(
                500, _safe_int_local(delay, 2000))))
        if not bees:
            bees = [ShadyBear(delay_ms=d) for d in _auto_bee_delays(platforms)]

        lvl = Level(
            name=name,
            bg_color=bg_color,
            player_start=(_safe_int_local(
                player_start[0], 60), _safe_int_local(player_start[1], 670)),
            exit_pos=(_safe_int_local(
                exit_pos[0], 900), _safe_int_local(exit_pos[1], 80)),
            platforms=platforms,
            coins=coins,
            bees=bees,
        )
        lvl._mod_level_id = f"user_custom_{idx}"
        return lvl

    def _resync_runtime_custom_levels():
        for lvl in list(LEVELS):
            if str(getattr(lvl, "_mod_level_id", "")).startswith("user_custom_"):
                LEVELS.remove(lvl)
        rows = _read_level_rows()
        for i, row in enumerate(rows):
            LEVELS.append(_row_to_level(row, i))
        _sync_level_bookkeeping()

    def _load_row_into_editor(row):
        nonlocal lm_tiles, lm_player_start, lm_exit_pos, lm_cursor, lm_start_acorns, lm_start_enemies

        tile_w, tile_h = lm_tile_size
        lm_tiles = set()
        for p in row.get("platforms", []):
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                x = (_safe_int_local(p[0], 0) // tile_w) * tile_w
                y = (_safe_int_local(p[1], 120) // tile_h) * tile_h
                y = max(120, y)
                lm_tiles.add((x, y))

        ps = row.get("player_start", [60, 670])
        if isinstance(ps, (list, tuple)) and len(ps) >= 2:
            lm_player_start = [_safe_int_local(
                ps[0], 60), _safe_int_local(ps[1], 670)]
        else:
            lm_player_start = [60, 670]

        ex = row.get("exit_pos", [900, 80])
        if isinstance(ex, (list, tuple)) and len(ex) >= 2:
            lm_exit_pos = [_safe_int_local(
                ex[0], 900), _safe_int_local(ex[1], 80)]
        else:
            lm_exit_pos = [900, 80]

        lm_cursor = [0, 120]
        if lm_tiles:
            first = sorted(lm_tiles)[0]
            lm_cursor = [first[0], first[1]]

        temp_plats = [Platform(x, y, tile_w, tile_h)
                      for (x, y) in sorted(lm_tiles)]
        if not temp_plats:
            temp_plats = [Platform(0, 720, 260, 80)]

        raw_coins = row.get("coins", [])
        raw_bees = row.get("bees", [])
        default_acorns = len(_auto_coin_points(temp_plats))
        default_enemies = len(_auto_bee_delays(temp_plats))
        inferred_acorns = len(raw_coins) if isinstance(
            raw_coins, list) else default_acorns
        inferred_enemies = len(raw_bees) if isinstance(
            raw_bees, list) else default_enemies

        lm_start_acorns = max(0, min(30, _safe_int_local(
            row.get("starting_acorns", inferred_acorns), inferred_acorns)))
        lm_start_enemies = max(0, min(30, _safe_int_local(
            row.get("starting_enemies", inferred_enemies), inferred_enemies)))

    def level_from_level_maker(level_name):
        nonlocal lm_start_acorns, lm_start_enemies
        tile_w, tile_h = lm_tile_size
        plats = [Platform(x, y, tile_w, tile_h) for (x, y) in sorted(lm_tiles)]
        if not plats:
            # Keep at least one ground slab if user saved empty.
            plats.append(Platform(0, 720, 260, 80))

        # Auto-place a few acorns near the highest platforms.
        coin_points = _auto_coin_points(plats, lm_start_acorns)
        coins = [Coin(x, y) for (x, y) in coin_points]

        # Auto-spawn enemies with increasing delay; larger maps get more bears.
        bee_delays = _auto_bee_delays(plats, lm_start_enemies)
        bees = [ShadyBear(delay_ms=d) for d in bee_delays]

        lvl = Level(
            name=level_name,
            bg_color=(95, 140, 125),
            player_start=(lm_player_start[0], lm_player_start[1]),
            exit_pos=(lm_exit_pos[0], lm_exit_pos[1]),
            platforms=plats,
            coins=coins,
            bees=bees,
        )
        return lvl

    def save_level_maker_level():
        nonlocal lm_save_notice, lm_notice_until_ms, lm_editing_row_index

        rows = _read_level_rows()
        is_editing = lm_editing_row_index is not None and 0 <= lm_editing_row_index < len(
            rows)

        if is_editing:
            level_name = str(rows[lm_editing_row_index].get(
                "name", f"Custom Level {lm_editing_row_index + 1}"))
        else:
            level_name = f"Custom Level {len(rows) + 1}"

        lvl = level_from_level_maker(level_name)
        row_data = {
            "name": level_name,
            "bg_color": [95, 140, 125],
            "player_start": [lm_player_start[0], lm_player_start[1]],
            "exit_pos": [lm_exit_pos[0], lm_exit_pos[1]],
            "platforms": [[x, y, lm_tile_size[0], lm_tile_size[1]] for (x, y) in sorted(lm_tiles)],
            "starting_acorns": int(lm_start_acorns),
            "starting_enemies": int(lm_start_enemies),
            "coins": [[coin.rect.centerx, coin.rect.centery] for coin in lvl.coins],
            "bees": [bee.delay_ms for bee in lvl.bees],
        }

        if is_editing:
            rows[lm_editing_row_index] = row_data
        else:
            rows.append(row_data)

        _write_level_rows(rows)
        _resync_runtime_custom_levels()
        _refresh_saved_rows()

        if is_editing:
            lm_save_notice = f"Updated {level_name}"
        else:
            lm_save_notice = f"Saved {level_name}"
        lm_editing_row_index = None
        lm_notice_until_ms = pygame.time.get_ticks() + 2200

    def edit_selected_level():
        nonlocal lm_save_notice, lm_notice_until_ms, lm_editing_row_index

        _refresh_saved_rows()
        if not lm_saved_rows:
            lm_save_notice = "No saved custom levels to edit"
            lm_notice_until_ms = pygame.time.get_ticks() + 2000
            return

        idx = max(0, min(lm_saved_index, len(lm_saved_rows) - 1))
        row = lm_saved_rows[idx]
        _load_row_into_editor(row)
        lm_editing_row_index = idx
        lm_save_notice = f"Editing {row.get('name', f'Custom Level {idx + 1}')}"
        lm_notice_until_ms = pygame.time.get_ticks() + 2200

    def delete_selected_level():
        nonlocal lm_save_notice, lm_notice_until_ms, lm_editing_row_index, lm_saved_index

        rows = _read_level_rows()
        if not rows:
            lm_save_notice = "No saved custom levels to delete"
            lm_notice_until_ms = pygame.time.get_ticks() + 2000
            return

        idx = max(0, min(lm_saved_index, len(rows) - 1))
        removed = rows.pop(idx)
        _write_level_rows(rows)
        _resync_runtime_custom_levels()
        _refresh_saved_rows()
        lm_saved_index = max(0, min(idx, max(0, len(lm_saved_rows) - 1)))
        lm_editing_row_index = None
        level_maker_reset()
        lm_save_notice = f"Deleted {removed.get('name', f'Custom Level {idx + 1}')}"
        lm_notice_until_ms = pygame.time.get_ticks() + 2200

    def apply_texture_pack_settings(pack_reference):
        nonlocal pack_style

        pack_data = asset_handling.load_texture_pack(pack_reference)
        if pack_data is None:
            pack_data = asset_handling.fallback_texture_pack() or {}

        colors = pack_data.get("colors", {})
        player_section = pack_data.get("player", {})
        bg_section = pack_data.get("background", {})
        items_section = pack_data.get("items", {})

        # Visual overrides — colors
        player_module.Player.COLOR = _parse_color(
            colors.get("player"), base_player_color)
        player_module.Player.EYE_COLOR = _parse_color(
            colors.get("player_eye"), base_player_eye_color)

        # PNG sprites (optional — fall back to color drawing if not found)
        player_module.Player.ANIM_IDLE = asset_handling.load_pack_animation(
            player_section.get("idle"))
        player_module.Player.ANIM_WALK = asset_handling.load_pack_animation(
            player_section.get("walk"))
        player_module.Player.ANIM_JUMP = asset_handling.load_pack_animation(
            player_section.get("jump"))
        player_module.Player.ANIM_FPS = int(player_section.get("fps", 8))

        pack_style = {
            "background_color": _parse_color(colors.get("background"), None),
            "background_image": asset_handling.load_pack_image(bg_section.get("day")),
            "platform_color": _parse_color(colors.get("platform"), None),
            "platform_tile": asset_handling.load_pack_image(items_section.get("platform")),
            "exit_color": _parse_color(colors.get("exit"), None),
            "exit_frame_color": _parse_color(colors.get("exit_frame"), None),
        }

    def reset_level(idx):
        nonlocal player, camera_x, coins_this_level, level_start_time, _bears_spawned_extra, game_ms
        _sync_level_bookkeeping()
        if idx < 0 or idx >= len(LEVELS):
            return
        lvl = LEVELS[idx]
        coins_this_level = 0
        _bears_spawned_extra = 0
        game_ms = 0
        # Remove any dynamically-added bears, restore original set
        del lvl.bees[_original_bear_counts[idx]:]
        level_start_time = pygame.time.get_ticks()
        player = Player(*lvl.player_start, max_jumps=game_max_jumps)
        player_history.clear()
        for bear in lvl.bees:
            bear.reset(*lvl.player_start)
        camera_x = 0
        mod_manager.on_level_start(lvl, player)

    def _sync_level_bookkeeping():
        nonlocal _original_bear_counts
        if len(_original_bear_counts) < len(LEVELS):
            for i in range(len(_original_bear_counts), len(LEVELS)):
                _original_bear_counts.append(len(LEVELS[i].bees))
        elif len(_original_bear_counts) > len(LEVELS):
            _original_bear_counts = _original_bear_counts[:len(LEVELS)]

    # Load mods listed in settings on startup
    mod_manager.load_enabled_from_settings()
    mod_manager.preload_all_metadata()
    _refresh_saved_rows()
    _sync_level_bookkeeping()
    main_options = get_main_options()
    apply_texture_pack_settings(settings.texture_pack)

    # Apply saved window mode
    window = _apply_window_mode(
        getattr(settings, "window_mode", "window"),
        settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)

    refresh_rates = [30, 60, 120, 144, 240]
    resolutions = [(800, 600), (1000, 800), (1280, 720),
                   (1366, 768), (1920, 1080)]

    packs = asset_handling.list_texture_packs()
    if settings.texture_pack in packs:
        pack_selected_index = packs.index(settings.texture_pack)
    else:
        pack_selected_index = 0

    if settings.refresh_rate in refresh_rates:
        refresh_index = refresh_rates.index(settings.refresh_rate)
    else:
        refresh_index = 1

    current_resolution = (settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
    if current_resolution in resolutions:
        resolution_index = resolutions.index(current_resolution)
    else:
        resolution_index = 1

    while running:
        main_options = get_main_options()
        if main_selected_index >= len(main_options):
            main_selected_index = max(0, len(main_options) - 1)

        if lm_notice_until_ms and pygame.time.get_ticks() > lm_notice_until_ms:
            lm_save_notice = ""
            lm_notice_until_ms = 0

        fullscreen_scaling = getattr(
            settings, "window_mode", "window") == "fullscreen"
        viewport = _compute_viewport(
            window.get_size(), game_surface.get_size(), allow_upscale=fullscreen_scaling)
        # dt normalised to 1.0 at 60 FPS — keeps physics speed constant across all refresh rates
        dt = clock.tick(settings.refresh_rate) / (1000 / 60)
        dt = min(dt, 3.0)  # cap spike frames
        if not mod_manager.paused:
            game_ms += int(clock.get_time())

        for event in pygame.event.get():
            mod_manager.on_event(event)
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.VIDEORESIZE and getattr(settings, "window_mode", "window") == "window":
                new_w = max(640, int(event.w))
                new_h = max(480, int(event.h))
                window = pygame.display.set_mode(
                    (new_w, new_h), pygame.RESIZABLE)
                # Keep settings in sync with manual drag-resize.
                settings.change_setting("WINDOW_WIDTH", new_w)
                settings.change_setting("WINDOW_HEIGHT", new_h)

            if event.type == pygame.KEYDOWN:
                # Global hotkeys — work in any menu/game state
                if event.key == pygame.K_F2 and menu_state == "game":
                    pack = getattr(settings, "texture_pack", "")
                    if not pack:
                        screenshot_notice = "No texture pack active."
                    else:
                        ok, info = asset_handling.save_pack_preview(
                            pack, game_surface)
                        if ok:
                            import os
                            if "screenshots" + os.sep in info or "/screenshots/" in info or "\\screenshots\\" in info:
                                screenshot_notice = "Saved to screenshots folder."
                            else:
                                screenshot_notice = "Preview saved!"
                        else:
                            screenshot_notice = f"Skipped: {info}"
                    screenshot_notice_until = pygame.time.get_ticks() + 3000
                elif event.key == pygame.K_F5:
                    mod_manager.reload_all()
                    all_mods = mod_manager.list_available_mods()
                elif event.key == pygame.K_F6:
                    packs = asset_handling.list_texture_packs()
                    reloaded = asset_handling.load_texture_pack(
                        settings.texture_pack)
                    if reloaded is not None:
                        apply_texture_pack_settings(settings.texture_pack)
                    if settings.texture_pack in packs:
                        pack_selected_index = packs.index(
                            settings.texture_pack)
                        texture_menu_selected_index = pack_selected_index
                    print("[hotkey] Texture packs reloaded.")

                if menu_state == "main":
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_UP:
                        main_selected_index = (
                            main_selected_index - 1) % len(main_options)
                    elif event.key == pygame.K_DOWN:
                        main_selected_index = (
                            main_selected_index + 1) % len(main_options)
                    elif event.key == pygame.K_RETURN:
                        selected_option = main_options[main_selected_index]
                        if selected_option == "Start Game":
                            apply_texture_pack_settings(settings.texture_pack)
                            if mod_manager.is_enabled(level_maker_mod_path):
                                level_select_selected_index = 0
                                menu_state = "level_select"
                            else:
                                current_level_index = 0
                                reset_level(current_level_index)
                                menu_state = "game"
                        elif selected_option == "Settings":
                            packs = asset_handling.list_texture_packs()
                            if settings.texture_pack in packs:
                                pack_selected_index = packs.index(
                                    settings.texture_pack)
                            else:
                                pack_selected_index = 0
                            texture_menu_selected_index = pack_selected_index
                            menu_state = "settings"
                        elif selected_option == "Level Maker":
                            level_maker_reset()
                            _refresh_saved_rows()
                            lm_editing_row_index = None
                            menu_state = "level_maker"
                        elif selected_option == "Exit":
                            running = False

                elif menu_state == "level_maker":
                    step_x, step_y = lm_tile_size
                    max_x = max(0, game_surface.get_width() - step_x)
                    max_y = max(120, game_surface.get_height() - step_y)

                    if event.key == pygame.K_ESCAPE:
                        menu_state = "main"
                    elif event.key == pygame.K_LEFT:
                        lm_cursor[0] = max(0, lm_cursor[0] - step_x)
                    elif event.key == pygame.K_RIGHT:
                        lm_cursor[0] = min(max_x, lm_cursor[0] + step_x)
                    elif event.key == pygame.K_UP:
                        lm_cursor[1] = max(120, lm_cursor[1] - step_y)
                    elif event.key == pygame.K_DOWN:
                        lm_cursor[1] = min(max_y, lm_cursor[1] + step_y)
                    elif event.key in (pygame.K_RETURN, pygame.K_p):
                        key = (lm_cursor[0], lm_cursor[1])
                        if key in lm_tiles:
                            lm_tiles.remove(key)
                        else:
                            lm_tiles.add(key)
                    elif event.key == pygame.K_1:
                        lm_player_start = [lm_cursor[0], lm_cursor[1] - 48]
                    elif event.key == pygame.K_2:
                        lm_exit_pos = [lm_cursor[0], lm_cursor[1] - 46]
                    elif event.key == pygame.K_n:
                        level_maker_reset()
                        lm_editing_row_index = None
                        lm_save_notice = "Started new custom level"
                        lm_notice_until_ms = pygame.time.get_ticks() + 1800
                    elif event.key == pygame.K_c:
                        lm_tiles.clear()
                        lm_save_notice = "Cleared all tiles"
                        lm_notice_until_ms = pygame.time.get_ticks() + 1800
                    elif event.key == pygame.K_a:
                        lm_start_enemies = max(0, lm_start_enemies - 1)
                    elif event.key == pygame.K_d:
                        lm_start_enemies = min(30, lm_start_enemies + 1)
                    elif event.key == pygame.K_z:
                        lm_start_acorns = max(0, lm_start_acorns - 1)
                    elif event.key == pygame.K_x:
                        lm_start_acorns = min(30, lm_start_acorns + 1)
                    elif event.key == pygame.K_q:
                        _refresh_saved_rows()
                        if lm_saved_rows:
                            lm_saved_index = (
                                lm_saved_index - 1) % len(lm_saved_rows)
                    elif event.key == pygame.K_w:
                        _refresh_saved_rows()
                        if lm_saved_rows:
                            lm_saved_index = (
                                lm_saved_index + 1) % len(lm_saved_rows)
                    elif event.key == pygame.K_e:
                        edit_selected_level()
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        delete_selected_level()
                    elif event.key == pygame.K_s:
                        save_level_maker_level()

                elif menu_state == "level_select":
                    level_names = get_level_names()
                    total_rows = len(level_names) + 1
                    if event.key == pygame.K_ESCAPE:
                        menu_state = "main"
                    elif event.key == pygame.K_UP and total_rows > 0:
                        level_select_selected_index = (
                            level_select_selected_index - 1) % total_rows
                    elif event.key == pygame.K_DOWN and total_rows > 0:
                        level_select_selected_index = (
                            level_select_selected_index + 1) % total_rows
                    elif event.key == pygame.K_RETURN:
                        if level_select_selected_index == len(level_names):
                            menu_state = "main"
                        elif LEVELS:
                            current_level_index = max(
                                0, min(level_select_selected_index, len(LEVELS) - 1))
                            reset_level(current_level_index)
                            menu_state = "game"

                elif menu_state == "settings":
                    if event.key == pygame.K_ESCAPE:
                        menu_state = "main"
                    elif event.key == pygame.K_UP:
                        settings_selected_index = (
                            settings_selected_index - 1) % 6
                    elif event.key == pygame.K_DOWN:
                        settings_selected_index = (
                            settings_selected_index + 1) % 6
                    elif event.key == pygame.K_LEFT:
                        if settings_selected_index == 0:
                            refresh_index = (
                                refresh_index - 1) % len(refresh_rates)
                            settings.change_setting(
                                "refresh_rate", refresh_rates[refresh_index])
                        elif settings_selected_index == 1:
                            resolution_index = (
                                resolution_index - 1) % len(resolutions)
                            width, height = resolutions[resolution_index]
                            settings.change_setting("WINDOW_WIDTH", width)
                            settings.change_setting("WINDOW_HEIGHT", height)
                            window = _apply_window_mode(
                                getattr(settings, "window_mode", "window"), width, height)
                        elif settings_selected_index == 2:
                            mode_index = (_WINDOW_MODES.index(
                                getattr(settings, "window_mode", "window")) - 1) % len(_WINDOW_MODES)
                            settings.change_setting(
                                "window_mode", _WINDOW_MODES[mode_index])
                            window = _apply_window_mode(
                                _WINDOW_MODES[mode_index], settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
                    elif event.key == pygame.K_RIGHT:
                        if settings_selected_index == 0:
                            refresh_index = (
                                refresh_index + 1) % len(refresh_rates)
                            settings.change_setting(
                                "refresh_rate", refresh_rates[refresh_index])
                        elif settings_selected_index == 1:
                            resolution_index = (
                                resolution_index + 1) % len(resolutions)
                            width, height = resolutions[resolution_index]
                            settings.change_setting("WINDOW_WIDTH", width)
                            settings.change_setting("WINDOW_HEIGHT", height)
                            window = _apply_window_mode(
                                getattr(settings, "window_mode", "window"), width, height)
                        elif settings_selected_index == 2:
                            mode_index = (_WINDOW_MODES.index(
                                getattr(settings, "window_mode", "window")) + 1) % len(_WINDOW_MODES)
                            settings.change_setting(
                                "window_mode", _WINDOW_MODES[mode_index])
                            window = _apply_window_mode(
                                _WINDOW_MODES[mode_index], settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
                    elif event.key == pygame.K_RETURN:
                        if settings_selected_index == 3:
                            packs = asset_handling.list_texture_packs()
                            if settings.texture_pack in packs:
                                pack_selected_index = packs.index(
                                    settings.texture_pack)
                            else:
                                pack_selected_index = 0
                            texture_menu_selected_index = pack_selected_index
                            menu_state = "settings_texture_packs"
                        elif settings_selected_index == 4:
                            all_mods = mod_manager.list_available_mods()
                            mods_selected_index = 0
                            mods_panel_focus = "list"
                            mods_setting_index = 0
                            menu_state = "settings_mods"
                        elif settings_selected_index == 5:
                            menu_state = "main"

                elif menu_state == "settings_texture_packs":
                    total_rows = len(packs) + 1
                    if event.key == pygame.K_ESCAPE:
                        menu_state = "settings"
                    elif event.key == pygame.K_UP and total_rows > 0:
                        texture_menu_selected_index = (
                            texture_menu_selected_index - 1) % total_rows
                    elif event.key == pygame.K_DOWN and total_rows > 0:
                        texture_menu_selected_index = (
                            texture_menu_selected_index + 1) % total_rows
                    elif event.key == pygame.K_RETURN:
                        if texture_menu_selected_index == len(packs):
                            menu_state = "settings"
                        elif packs:
                            selected_pack = packs[texture_menu_selected_index]
                            loaded_pack = asset_handling.load_texture_pack(
                                selected_pack)
                            if loaded_pack is not None:
                                settings.change_setting(
                                    "texture_pack", selected_pack)
                                apply_texture_pack_settings(selected_pack)
                                pack_selected_index = texture_menu_selected_index

                elif menu_state == "game":
                    if event.key in (pygame.K_m, pygame.K_ESCAPE):
                        menu_state = "main"

                elif menu_state == "settings_mods":
                    total_rows = len(all_mods) + 1
                    selected_mod_path = all_mods[mods_selected_index] if 0 <= mods_selected_index < len(
                        all_mods) else None
                    selected_mod_settings = _get_mod_setting_entries(
                        selected_mod_path) if selected_mod_path else []

                    if event.key == pygame.K_ESCAPE:
                        menu_state = "settings"
                    elif event.key == pygame.K_TAB and selected_mod_path:
                        mods_panel_focus = "settings" if mods_panel_focus == "list" else "list"
                        mods_setting_index = 0
                    elif mods_panel_focus == "settings" and selected_mod_path:
                        if event.key == pygame.K_UP and selected_mod_settings:
                            mods_setting_index = (
                                mods_setting_index - 1) % len(selected_mod_settings)
                        elif event.key == pygame.K_DOWN and selected_mod_settings:
                            mods_setting_index = (
                                mods_setting_index + 1) % len(selected_mod_settings)
                        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN):
                            if selected_mod_settings:
                                active = selected_mod_settings[max(
                                    0, min(mods_setting_index, len(selected_mod_settings) - 1))]
                                direction = -1 if event.key == pygame.K_LEFT else 1
                                _change_mod_setting(
                                    selected_mod_path, active, direction)
                        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                            if selected_mod_settings:
                                active = selected_mod_settings[max(
                                    0, min(mods_setting_index, len(selected_mod_settings) - 1))]
                                mod_manager.remove_mod_setting(
                                    selected_mod_path, active["key"])
                        elif event.key == pygame.K_SPACE:
                            mods_panel_focus = "list"
                    elif event.key == pygame.K_UP and total_rows > 0:
                        mods_selected_index = (
                            mods_selected_index - 1) % total_rows
                        mods_setting_index = 0
                    elif event.key == pygame.K_DOWN and total_rows > 0:
                        mods_selected_index = (
                            mods_selected_index + 1) % total_rows
                        mods_setting_index = 0
                    elif event.key == pygame.K_RIGHT and selected_mod_path:
                        mods_panel_focus = "settings"
                        mods_setting_index = 0
                    elif event.key == pygame.K_RETURN:
                        if mods_selected_index == len(all_mods):
                            menu_state = "settings"
                        elif all_mods:
                            mod_manager.toggle(all_mods[mods_selected_index])

                elif menu_state == "win":
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_m):
                        menu_state = "main"

                elif menu_state == "level_complete":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if lc_is_final:
                            menu_state = "win"
                        else:
                            menu_state = "game"

            # ── Mouse: hover to highlight ────────────────────────────────
            if event.type == pygame.MOUSEMOTION:
                game_pos = _window_to_game_pos(
                    event.pos, viewport, game_surface.get_size())
                if game_pos is None:
                    continue
                mx, my = game_pos
                if menu_state == "main":
                    hit = _hit_row(my, 210, 48, len(main_options))
                    if hit >= 0:
                        main_selected_index = hit
                elif menu_state == "settings":
                    hit = _hit_row(my, 150, 42, 6)
                    if hit >= 0:
                        settings_selected_index = hit
                elif menu_state == "settings_texture_packs":
                    hit = _hit_row(my, 130, 36, len(packs) + 1)
                    if hit >= 0:
                        texture_menu_selected_index = hit
                elif menu_state == "level_select":
                    level_names = get_level_names()
                    hit = _hit_row(my, 170, 40, len(level_names) + 1)
                    if hit >= 0:
                        level_select_selected_index = hit
                elif menu_state == "settings_mods":
                    hit = _hit_row(my, 130, 36, len(all_mods) + 1)
                    if hit >= 0:
                        mods_selected_index = hit
                        mods_panel_focus = "list"
                        mods_setting_index = 0
                elif menu_state == "level_maker":
                    step_x, step_y = lm_tile_size
                    max_x = max(0, game_surface.get_width() - step_x)
                    max_y = max(120, game_surface.get_height() - step_y)
                    gx = max(0, min(max_x, (mx // step_x) * step_x))
                    gy = max(120, min(max_y, (my // step_y) * step_y))
                    lm_cursor[0], lm_cursor[1] = gx, gy
                    key = (gx, gy)
                    if lm_mouse_paint:
                        lm_tiles.add(key)
                    elif lm_mouse_erase and key in lm_tiles:
                        lm_tiles.remove(key)

            # ── Mouse: left-click to activate ────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN:
                game_pos = _window_to_game_pos(
                    event.pos, viewport, game_surface.get_size())
                if game_pos is None:
                    continue
                mx, my = game_pos
                if menu_state == "level_maker":
                    step_x, step_y = lm_tile_size
                    max_x = max(0, game_surface.get_width() - step_x)
                    max_y = max(120, game_surface.get_height() - step_y)
                    gx = max(0, min(max_x, (mx // step_x) * step_x))
                    gy = max(120, min(max_y, (my // step_y) * step_y))
                    lm_cursor[0], lm_cursor[1] = gx, gy
                    key = (gx, gy)
                    if event.button == 1:
                        lm_mouse_paint = True
                        lm_tiles.add(key)
                        continue
                    elif event.button == 3:
                        lm_mouse_erase = True
                        if key in lm_tiles:
                            lm_tiles.remove(key)
                        continue

                if event.button != 1:
                    continue

                if menu_state == "main":
                    hit = _hit_row(my, 210, 48, len(main_options))
                    if hit >= 0:
                        main_selected_index = hit
                        selected_option = main_options[hit]
                        if selected_option == "Start Game":
                            apply_texture_pack_settings(settings.texture_pack)
                            if mod_manager.is_enabled(level_maker_mod_path):
                                level_select_selected_index = 0
                                menu_state = "level_select"
                            else:
                                current_level_index = 0
                                reset_level(current_level_index)
                                menu_state = "game"
                        elif selected_option == "Settings":
                            packs = asset_handling.list_texture_packs()
                            if settings.texture_pack in packs:
                                pack_selected_index = packs.index(
                                    settings.texture_pack)
                            else:
                                pack_selected_index = 0
                            texture_menu_selected_index = pack_selected_index
                            menu_state = "settings"
                        elif selected_option == "Level Maker":
                            level_maker_reset()
                            _refresh_saved_rows()
                            lm_editing_row_index = None
                            menu_state = "level_maker"
                        elif selected_option == "Exit":
                            running = False

                elif menu_state == "level_maker":
                    step_x, step_y = lm_tile_size
                    gx = (mx // step_x) * step_x
                    gy = max(120, (my // step_y) * step_y)
                    key = (gx, gy)
                    lm_tiles.add(key)
                    lm_cursor[0], lm_cursor[1] = gx, gy

                elif menu_state == "level_select":
                    level_names = get_level_names()
                    hit = _hit_row(my, 170, 40, len(level_names) + 1)
                    if hit >= 0:
                        level_select_selected_index = hit
                        if hit == len(level_names):
                            menu_state = "main"
                        elif LEVELS:
                            current_level_index = max(
                                0, min(hit, len(LEVELS) - 1))
                            reset_level(current_level_index)
                            menu_state = "game"

                elif menu_state == "settings":
                    hit = _hit_row(my, 150, 42, 6)
                    if hit >= 0:
                        settings_selected_index = hit
                        if hit == 0:
                            # cycle refresh rate forward
                            refresh_index = (
                                refresh_index + 1) % len(refresh_rates)
                            settings.change_setting(
                                "refresh_rate", refresh_rates[refresh_index])
                        elif hit == 1:
                            # cycle resolution forward
                            resolution_index = (
                                resolution_index + 1) % len(resolutions)
                            width, height = resolutions[resolution_index]
                            settings.change_setting("WINDOW_WIDTH", width)
                            settings.change_setting("WINDOW_HEIGHT", height)
                            window = _apply_window_mode(
                                getattr(settings, "window_mode", "window"), width, height)
                        elif hit == 2:
                            # cycle window mode forward
                            mode_index = (_WINDOW_MODES.index(
                                getattr(settings, "window_mode", "window")) + 1) % len(_WINDOW_MODES)
                            settings.change_setting(
                                "window_mode", _WINDOW_MODES[mode_index])
                            window = _apply_window_mode(
                                _WINDOW_MODES[mode_index], settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
                        elif hit == 3:
                            packs = asset_handling.list_texture_packs()
                            if settings.texture_pack in packs:
                                pack_selected_index = packs.index(
                                    settings.texture_pack)
                            else:
                                pack_selected_index = 0
                            texture_menu_selected_index = pack_selected_index
                            menu_state = "settings_texture_packs"
                        elif hit == 4:
                            all_mods = mod_manager.list_available_mods()
                            mods_selected_index = 0
                            mods_panel_focus = "list"
                            mods_setting_index = 0
                            menu_state = "settings_mods"
                        elif hit == 5:
                            menu_state = "main"

                elif menu_state == "settings_texture_packs":
                    total_rows = len(packs) + 1
                    hit = _hit_row(my, 130, 36, total_rows)
                    if hit >= 0:
                        texture_menu_selected_index = hit
                        if hit == len(packs):
                            menu_state = "settings"
                        elif packs:
                            selected_pack = packs[hit]
                            loaded_pack = asset_handling.load_texture_pack(
                                selected_pack)
                            if loaded_pack is not None:
                                settings.change_setting(
                                    "texture_pack", selected_pack)
                                apply_texture_pack_settings(selected_pack)
                                pack_selected_index = hit

                elif menu_state == "settings_mods":
                    total_rows = len(all_mods) + 1
                    hit = _hit_row(my, 130, 36, total_rows)
                    if hit >= 0:
                        mods_selected_index = hit
                        mods_panel_focus = "list"
                        mods_setting_index = 0
                        if hit == len(all_mods):
                            menu_state = "settings"
                        elif all_mods:
                            mod_manager.toggle(all_mods[hit])

                elif menu_state == "win":
                    menu_state = "main"

                elif menu_state == "level_complete":
                    if lc_is_final:
                        menu_state = "win"
                    else:
                        menu_state = "game"

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    lm_mouse_paint = False
                elif event.button == 3:
                    lm_mouse_erase = False

        if menu_state == "main":
            draw_main_menu(game_surface, font, title_font,
                           main_options, main_selected_index)
        elif menu_state == "level_select":
            draw_level_select_menu(
                game_surface,
                font,
                title_font,
                level_select_selected_index,
                get_level_names(),
            )
        elif menu_state == "level_maker":
            if lm_saved_rows:
                selected_name = str(lm_saved_rows[max(0, min(lm_saved_index, len(
                    lm_saved_rows) - 1))].get("name", f"Custom Level {lm_saved_index + 1}"))
            else:
                selected_name = "(none)"
            draw_level_maker(
                game_surface,
                font,
                title_font,
                lm_cursor,
                lm_tile_size,
                lm_tiles,
                lm_player_start,
                lm_exit_pos,
                lm_save_notice,
                selected_name,
                lm_editing_row_index is not None,
                lm_start_acorns,
                lm_start_enemies,
            )
        elif menu_state == "settings":
            draw_settings_menu(
                game_surface, font, title_font, settings_selected_index, packs, pack_selected_index)
        elif menu_state == "settings_texture_packs":
            draw_texture_pack_submenu(
                game_surface, font, title_font, packs, texture_menu_selected_index, settings.texture_pack)
        elif menu_state == "settings_mods":
            draw_mods_submenu(game_surface, font, title_font,
                              mods_selected_index, all_mods,
                              mods_panel_focus, mods_setting_index)
        elif menu_state == "game" and player is not None:
            _sync_level_bookkeeping()
            if not LEVELS:
                menu_state = "main"
                continue
            if current_level_index >= len(LEVELS):
                current_level_index = len(LEVELS) - 1
            level = LEVELS[current_level_index]
            # Single-screen game — no horizontal scrolling
            camera_x = 0
            # Let mods run first so they can set paused / god_mode flags
            mod_manager.on_update(level, player, dt)
            # Handle set_enemy_count outside the pause check so it works from the cheat menu
            if mod_manager.set_enemy_count >= 0:
                target = mod_manager.set_enemy_count
                mod_manager.set_enemy_count = -1
                orig = _original_bear_counts[current_level_index]
                while len(level.bees) > orig + target:
                    level.bees.pop()
                    _bears_spawned_extra = max(0, _bears_spawned_extra - 1)
                while _bears_spawned_extra < target:
                    base_delay = 1000 + (_bears_spawned_extra % 100) * 500
                    nb = ShadyBear(delay_ms=base_delay)
                    nb.reset(*level.player_start)
                    level.bees.append(nb)
                    _bears_spawned_extra += 1
            if not mod_manager.paused:
                # Update (dt normalised to 1.0 at 60 FPS)
                player.update(level.platforms, dt)
                # Record player position for enemy path-replay
                now_ms = game_ms
                player_history.append(
                    (now_ms, player.rect.centerx, player.rect.centery))
                # Update bears (replay player history with delay)
                for bee in level.bees:
                    bee.update(player_history, now_ms, dt)
                # Update and collect coins
                # Drain mod-requested acorn additions
                if mod_manager.add_acorns > 0:
                    coins_this_level += mod_manager.add_acorns
                    mod_manager.add_acorns = 0
                # Drain mod-requested bear spawns
                while mod_manager.spawn_bear > 0:
                    base_delay = 1000 + (_bears_spawned_extra % 100) * 500
                    nb = ShadyBear(delay_ms=base_delay)
                    nb.reset(*level.player_start)
                    level.bees.append(nb)
                    _bears_spawned_extra += 1
                    mod_manager.spawn_bear -= 1
                for coin in level.coins:
                    coin.update(dt)
                    if player.rect.colliderect(coin.rect):
                        coins_this_level += 1
                        # Spawn an extra bear every ACORNS_PER_BEAR acorns
                        desired_extra = coins_this_level // ACORNS_PER_BEAR
                        while _bears_spawned_extra < desired_extra:
                            base_delay = 1000 + \
                                (_bears_spawned_extra % 100) * 500
                            new_bear = ShadyBear(delay_ms=base_delay)
                            new_bear.reset(*level.player_start)
                            level.bees.append(new_bear)
                            _bears_spawned_extra += 1
                        # Teleport to a random spot above a random platform
                        plat = random.choice(level.platforms)
                        nx = random.randint(
                            plat.rect.left + 10, max(plat.rect.left + 11, plat.rect.right - 10))
                        ny = plat.rect.top - 20
                        coin.rect.centerx = nx
                        coin.rect.centery = ny
                # Death: fell off bottom
                if player.rect.top > game_surface.get_height() + 150:
                    reset_level(current_level_index)
                # Death: bear collision (skipped when god mode is on)
                elif not mod_manager.god_mode and any(
                        b._spawned and player.rect.colliderect(b.rect)
                        for b in level.bees):
                    reset_level(current_level_index)
            # Draw
            bg_color = pack_style["background_color"] or level.bg_color
            bg_img = pack_style["background_image"]
            if bg_img is not None:
                game_surface.fill(bg_color)
                scaled_bg = pygame.transform.smoothscale(
                    bg_img, game_surface.get_size())
                game_surface.blit(scaled_bg, (0, 0))
            else:
                _draw_forest_bg(game_surface, bg_color)
            for plat in level.platforms:
                plat_tile = pack_style["platform_tile"]
                if plat_tile is not None:
                    # tile the image across the platform rect
                    r = plat.rect.move(-camera_x, 0)
                    tw, th = plat_tile.get_size()
                    for tx in range(r.left, r.right, tw):
                        for ty in range(r.top, r.bottom, th):
                            clip = pygame.Rect(0, 0,
                                               min(tw, r.right - tx),
                                               min(th, r.bottom - ty))
                            game_surface.blit(plat_tile, (tx, ty), clip)
                else:
                    plat.draw(game_surface, camera_x,
                              override_color=pack_style["platform_color"])
            for coin in level.coins:
                coin.draw(game_surface, camera_x)
            for bee in level.bees:
                bee.draw(game_surface, camera_x)
            player.draw(game_surface, camera_x)
            # HUD
            hud = font.render(
                f"{level.name}  |  Acorns: {coins_this_level}  |  ESC / M: Menu",
                True, (220, 220, 220))
            game_surface.blit(hud, (10, 10))
            # F2 screenshot notice
            if screenshot_notice and pygame.time.get_ticks() < screenshot_notice_until:
                n_surf = font.render(
                    f"[F2] {screenshot_notice}", True, (255, 240, 140))
                game_surface.blit(n_surf, (
                    game_surface.get_width() // 2 - n_surf.get_width() // 2,
                    game_surface.get_height() - 36))
            mod_manager.on_draw(game_surface, level, player, camera_x)
        elif menu_state == "level_complete":
            draw_level_complete(game_surface, font, title_font,
                                LEVELS[current_level_index].name,
                                lc_coins, lc_total_coins, lc_elapsed, lc_is_final)
        elif menu_state == "win":
            _draw_forest_bg(game_surface, (110, 165, 155))
            overlay = pygame.Surface(game_surface.get_size(), pygame.SRCALPHA)
            overlay.fill((8, 18, 10, 145))
            game_surface.blit(overlay, (0, 0))
            win_text = title_font.render("You Win!", True, (245, 235, 160))
            sub_text = font.render("Press ENTER or ESC to return to menu",
                                   True, (190, 215, 195))
            wx = game_surface.get_width() // 2
            wy = game_surface.get_height() // 2
            game_surface.blit(
                win_text,  (wx - win_text.get_width() // 2, wy - 60))
            game_surface.blit(
                sub_text,  (wx - sub_text.get_width() // 2, wy + 10))

        _present_scaled(game_surface, window, allow_upscale=fullscreen_scaling)
        pygame.display.flip()  # Update the display

    pygame.quit()
