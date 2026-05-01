"""
Mod Manager
-----------
Mods are .py files inside the  mods/  folder.
A mod file may define any of the following optional hooks:

    on_load(context: dict)          called once when the mod is first loaded
    on_level_start(level, player)   called each time a level begins
    on_update(level, player, dt)    called every game-logic frame
    on_draw(surface, level, player, camera_x)  called after the main draw
    on_unload()                     called when the mod is disabled/unloaded

context passed to on_load contains:
    { "settings": <settings module>, "asset_handling": <asset_handling module> }
"""

import importlib.util
import pathlib
import traceback
import settings

_mods_path = pathlib.Path(__file__).parent / "mods"


def list_available_mods():
    """Return sorted list of mod paths relative to the project root."""
    if not _mods_path.exists():
        return []
    return sorted(
        str(p.relative_to(pathlib.Path(__file__).parent).as_posix())
        for p in _mods_path.rglob("*.py")
        if not p.name.startswith("_")
    )


def _load_module(mod_path_str):
    """Load a mod .py file as a module. Returns module or None on error."""
    full = pathlib.Path(__file__).parent / mod_path_str
    if not full.exists():
        print(f"[ModManager] File not found: {full}")
        return None
    spec = importlib.util.spec_from_file_location(full.stem, full)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        print(f"[ModManager] Error loading {mod_path_str}:")
        traceback.print_exc()
        return None
    return module


class ModManager:
    def __init__(self):
        # { mod_path_str: module_or_None }
        self._loaded: dict = {}
        # Flags mods can set to influence core game behaviour
        self.paused = False   # True → skip physics/updates this frame
        self.god_mode = False  # True → bear collisions don't kill the player
        self.add_acorns = 0    # Game.py adds this many acorns then resets to 0
        self.spawn_bear = 0    # Game.py spawns this many extra bears then resets to 0
        self.set_enemy_count = -1   # when >= 0, Game.py sets total extra bears to this value

    def list_available_mods(self):
        """Return available mod paths for the in-game mod menu."""
        return list_available_mods()

    # ── Enable / Disable ────────────────────────────────────────────────────

    def enable(self, mod_path_str):
        """Enable a mod and call its on_load hook. Saves to settings."""
        if mod_path_str in self._loaded:
            return  # already loaded
        module = _load_module(mod_path_str)
        self._loaded[mod_path_str] = module
        if module and hasattr(module, "on_load"):
            try:
                import asset_handling
                module.on_load({"settings": settings,
                                "asset_handling": asset_handling})
            except Exception:
                print(f"[ModManager] on_load error in {mod_path_str}:")
                traceback.print_exc()
        # Persist to settings
        if mod_path_str not in settings.mods:
            settings.mods = list(settings.mods) + [mod_path_str]
            import settings as s_mod
            s_mod.save_settings()

    def disable(self, mod_path_str):
        """Disable a mod and call its on_unload hook. Saves to settings."""
        module = self._loaded.pop(mod_path_str, None)
        if module and hasattr(module, "on_unload"):
            try:
                module.on_unload()
            except Exception:
                print(f"[ModManager] on_unload error in {mod_path_str}:")
                traceback.print_exc()
        # Persist to settings
        if mod_path_str in settings.mods:
            settings.mods = [m for m in settings.mods if m != mod_path_str]
            import settings as s_mod
            s_mod.save_settings()

    def toggle(self, mod_path_str):
        if mod_path_str in self._loaded:
            self.disable(mod_path_str)
        else:
            self.enable(mod_path_str)

    def is_enabled(self, mod_path_str):
        return mod_path_str in self._loaded

    def load_enabled_from_settings(self):
        """Load all mods listed in settings.mods on game startup."""
        for mod_path_str in list(settings.mods):
            self.enable(mod_path_str)

    def reload_all(self):
        """Unload all active mods, re-read settings from disk, then reload."""
        for mod_path_str in list(self._loaded):
            self.disable(mod_path_str)
        settings.load_settings()  # re-read settings.json
        self.load_enabled_from_settings()
        print("[ModManager] All mods reloaded.")

    # ── Hooks ───────────────────────────────────────────────────────────────

    def _call(self, hook, *args, **kwargs):
        for path, module in list(self._loaded.items()):
            if module and hasattr(module, hook):
                try:
                    getattr(module, hook)(*args, **kwargs)
                except Exception:
                    print(f"[ModManager] {hook} error in {path}:")
                    traceback.print_exc()

    def on_level_start(self, level, player):
        self._call("on_level_start", level, player)

    def on_update(self, level, player, dt):
        self._call("on_update", level, player, dt)

    def on_event(self, event):
        self._call("on_event", event)

    def on_draw(self, surface, level, player, camera_x):
        self._call("on_draw", surface, level, player, camera_x)


# Singleton used by the rest of the game
mod_manager = ModManager()
