import pygame
import random
import collections
import asset_handling
import settings
import player as player_module
from player import Player
from level import LEVELS, ShadyBear
from mod_manager import mod_manager

ACORNS_PER_BEAR = 5   # collect this many acorns → one extra enemy spawns


pygame.init()

window_width = settings.WINDOW_WIDTH
window_height = settings.WINDOW_HEIGHT
texture_pack_data = asset_handling.load_texture_pack(settings.texture_pack)
if texture_pack_data is None:
    texture_pack_data = asset_handling.fallback_texture_pack()


# replaced by _apply_window_mode after init
window = pygame.display.set_mode((window_width, window_height))
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
        return pygame.display.set_mode((width, height), pygame.FULLSCREEN)
    elif mode == "borderless":
        return pygame.display.set_mode((width, height), pygame.NOFRAME)
    else:
        return pygame.display.set_mode((width, height))


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


def draw_mods_submenu(surface, font, title_font, selected_index, all_mods):
    _draw_forest_bg(surface, (110, 165, 155))
    _ov = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    _ov.fill((8, 18, 10, 170))
    surface.blit(_ov, (0, 0))

    title = title_font.render("Mod Manager", True, (245, 235, 180))
    info = font.render(
        "UP/DOWN: Select  ENTER: Toggle  ESC: Back", True, (210, 210, 210))

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
                surface.blit(font.render(f"{prefix}{row}", True, color),
                             (60, start_y + i * line_height))
                surface.blit(font.render(status, True, status_color),
                             (surface.get_width() - 100, start_y + i * line_height))
            else:
                surface.blit(font.render(f"{prefix}{row}", True, color),
                             (60, start_y + i * line_height))


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
        line = font.render(f"{prefix}{row}{suffix}", True, color)
        surface.blit(line, (60, start_y + i * line_height))


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


def main():
    global window

    clock = pygame.time.Clock()
    running = True
    menu_state = "main"

    font = pygame.font.SysFont("consolas", 24)
    title_font = pygame.font.SysFont("consolas", 42, bold=True)
    main_options = ["Start Game", "Settings", "Exit"]
    main_selected_index = 0
    settings_selected_index = 0
    texture_menu_selected_index = 0
    mods_selected_index = 0
    all_mods = []

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

    # Load mods listed in settings on startup
    mod_manager.load_enabled_from_settings()
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
        # dt normalised to 1.0 at 60 FPS — keeps physics speed constant across all refresh rates
        dt = clock.tick(settings.refresh_rate) / (1000 / 60)
        dt = min(dt, 3.0)  # cap spike frames
        if not mod_manager.paused:
            game_ms += int(clock.get_time())

        for event in pygame.event.get():
            mod_manager.on_event(event)
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                # Global hotkeys — work in any menu/game state
                if event.key == pygame.K_F5:
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
                        elif selected_option == "Exit":
                            running = False

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
                    if event.key == pygame.K_ESCAPE:
                        menu_state = "settings"
                    elif event.key == pygame.K_UP and total_rows > 0:
                        mods_selected_index = (
                            mods_selected_index - 1) % total_rows
                    elif event.key == pygame.K_DOWN and total_rows > 0:
                        mods_selected_index = (
                            mods_selected_index + 1) % total_rows
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
                mx, my = event.pos
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
                elif menu_state == "settings_mods":
                    hit = _hit_row(my, 130, 36, len(all_mods) + 1)
                    if hit >= 0:
                        mods_selected_index = hit

            # ── Mouse: left-click to activate ────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if menu_state == "main":
                    hit = _hit_row(my, 210, 48, len(main_options))
                    if hit >= 0:
                        main_selected_index = hit
                        selected_option = main_options[hit]
                        if selected_option == "Start Game":
                            apply_texture_pack_settings(settings.texture_pack)
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
                        elif selected_option == "Exit":
                            running = False

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

        if menu_state == "main":
            draw_main_menu(window, font, title_font,
                           main_options, main_selected_index)
        elif menu_state == "settings":
            draw_settings_menu(
                window, font, title_font, settings_selected_index, packs, pack_selected_index)
        elif menu_state == "settings_texture_packs":
            draw_texture_pack_submenu(
                window, font, title_font, packs, texture_menu_selected_index, settings.texture_pack)
        elif menu_state == "settings_mods":
            draw_mods_submenu(window, font, title_font,
                              mods_selected_index, all_mods)
        elif menu_state == "game" and player is not None:
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
                if player.rect.top > settings.WINDOW_HEIGHT + 150:
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
                window.fill(bg_color)
                scaled_bg = pygame.transform.scale(bg_img, window.get_size())
                window.blit(scaled_bg, (0, 0))
            else:
                _draw_forest_bg(window, bg_color)
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
                            window.blit(plat_tile, (tx, ty), clip)
                else:
                    plat.draw(window, camera_x,
                              override_color=pack_style["platform_color"])
            for coin in level.coins:
                coin.draw(window, camera_x)
            for bee in level.bees:
                bee.draw(window, camera_x)
            player.draw(window, camera_x)
            # HUD
            hud = font.render(
                f"{level.name}  |  Acorns: {coins_this_level}  |  ESC / M: Menu",
                True, (220, 220, 220))
            window.blit(hud, (10, 10))
            mod_manager.on_draw(window, level, player, camera_x)
        elif menu_state == "level_complete":
            draw_level_complete(window, font, title_font,
                                LEVELS[current_level_index].name,
                                lc_coins, lc_total_coins, lc_elapsed, lc_is_final)
        elif menu_state == "win":
            _draw_forest_bg(window, (110, 165, 155))
            overlay = pygame.Surface(window.get_size(), pygame.SRCALPHA)
            overlay.fill((8, 18, 10, 145))
            window.blit(overlay, (0, 0))
            win_text = title_font.render("You Win!", True, (245, 235, 160))
            sub_text = font.render("Press ENTER or ESC to return to menu",
                                   True, (190, 215, 195))
            wx = settings.WINDOW_WIDTH // 2
            wy = settings.WINDOW_HEIGHT // 2
            window.blit(win_text,  (wx - win_text.get_width() // 2, wy - 60))
            window.blit(sub_text,  (wx - sub_text.get_width() // 2, wy + 10))

        pygame.display.flip()  # Update the display

    pygame.quit()
