"""Runtime mod loader with a cleaner class/object mod layout.

Preferred mod layout:
    MOD_INFO = {...}

    class Mod:
        def load(self, context):
            ...
        def level_start(self, level, player):
            ...
        def update(self, level, player, dt):
            ...
        def event(self, event):
            ...
        def draw(self, surface, level, player, camera_x):
            ...
        def unload(self):
            ...

    # Optional explicit instance:
    MOD = Mod()

Backward compatibility:
- Legacy function hooks (on_load, on_update, ...) still work.
- Existing settings.mods entries continue to work.
"""

from dataclasses import dataclass, field
import hashlib
import importlib.util
import inspect
import json
import pathlib
import sys
import traceback
import typing as t

import settings

_ROOT = pathlib.Path(__file__).parent
_MODS_PATH = _ROOT / "mods"
_MOD_SETTINGS_PATH = _ROOT / "mod_settings.json"
_MAX_META_LEN = 200

_HOOK_ALIASES = {
    "on_load": ("load", "on_load", "start", "on_start"),
    "on_level_start": ("level_start", "on_level_start"),
    "on_update": ("update", "on_update"),
    "on_event": ("event", "on_event", "handle_event"),
    "on_draw": ("draw", "on_draw"),
    "on_unload": ("unload", "on_unload", "stop", "on_stop"),
}


@dataclass
class ModRecord:
    path: str
    module: t.Any = None
    entry: t.Any = None
    module_name: str = ""
    enabled: bool = False
    load_error: str | None = None
    metadata: dict = field(default_factory=dict)


class ModAPI:
    """Stable API surface exposed to mods via register(api) and load context."""

    def __init__(self, manager, mod_path, metadata_getter):
        self._manager = manager
        self.mod_path = mod_path
        self._metadata_getter = metadata_getter

    @property
    def metadata(self):
        return dict(self._metadata_getter())

    def log(self, message):
        print(f"[mod:{self.mod_path}] {message}")

    def get_setting(self, key, default=None):
        return self._manager.get_mod_setting(self.mod_path, key, default)

    def set_setting(self, key, value, save=True):
        return self._manager.set_mod_setting(self.mod_path, key, value, save=save)

    def update_settings(self, values, save=True):
        return self._manager.update_mod_settings(self.mod_path, values, save=save)

    def remove_setting(self, key, save=True):
        return self._manager.remove_mod_setting(self.mod_path, key, save=save)

    def clear_settings(self):
        return self._manager.clear_mod_settings(self.mod_path)

    def save_settings(self):
        return self._manager.save_mod_settings()

    def set_virtual_key(self, keycode, pressed):
        self._manager.set_virtual_key(keycode, pressed)

    def is_virtual_key_down(self, keycode):
        return self._manager.is_virtual_key_down(keycode)


def list_available_mods():
    """Return sorted list of mod paths relative to project root."""
    if not _MODS_PATH.exists():
        return []

    found = []
    for p in _MODS_PATH.rglob("*.py"):
        if p.name.startswith("_"):
            continue
        found.append(str(p.relative_to(_ROOT).as_posix()))

    return sorted(found, key=lambda s: s.lower())


def _module_name_for_path(mod_path_str):
    digest = hashlib.sha1(mod_path_str.encode("utf-8")).hexdigest()[:12]
    stem = pathlib.Path(mod_path_str).stem
    return f"sb_mod_{stem}_{digest}"


def _clean_text(value, fallback):
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if not value:
        return fallback
    return value[:_MAX_META_LEN]


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_metadata(module, mod_path_str):
    info = getattr(module, "MOD_INFO", {})
    if not isinstance(info, dict):
        info = {}

    schema = info.get("settings_schema", {})
    if not isinstance(schema, dict):
        schema = {}

    display_name = _clean_text(
        info.get("name"), pathlib.Path(mod_path_str).stem)
    metadata = {
        "id": mod_path_str,
        "name": display_name,
        "version": _clean_text(info.get("version"), "0.0.0"),
        "author": _clean_text(info.get("author"), "unknown"),
        "description": _clean_text(info.get("description"), ""),
        "api_version": _safe_int(info.get("api_version"), 2),
        "load_priority": _safe_int(info.get("load_priority"), 0),
    }

    cleaned_schema = {}
    for key, rule in schema.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(rule, dict):
            cleaned_schema[key] = dict(rule)

    if cleaned_schema:
        metadata["settings_schema"] = cleaned_schema

    return metadata


def _normalize_mod_path(mod_path_str):
    raw = str(mod_path_str or "").replace("\\", "/").strip("/")
    if not raw:
        return ""

    candidate = raw if raw.startswith("mods/") else f"mods/{raw}"
    if not candidate.endswith(".py"):
        candidate = f"{candidate}.py"

    try:
        full = (_ROOT / candidate).resolve(strict=False)
    except OSError:
        return ""

    try:
        full.relative_to(_MODS_PATH.resolve(strict=False))
    except ValueError:
        return ""

    return str(pathlib.Path(candidate).as_posix())


def _resolve_entry(module):
    # Prefer explicit singleton object.
    if hasattr(module, "MOD"):
        mod_obj = getattr(module, "MOD")
        if mod_obj is None:
            raise TypeError("MOD is None")
        return mod_obj

    # Then a class-based layout.
    cls = getattr(module, "Mod", None)
    if inspect.isclass(cls):
        try:
            return cls()
        except Exception as exc:
            raise TypeError(f"Failed to instantiate Mod class: {exc}") from exc

    # Legacy module-level functions.
    return module


def _find_hook_callable(entry, canonical_hook):
    for hook_name in _HOOK_ALIASES[canonical_hook]:
        if hasattr(entry, hook_name):
            maybe = getattr(entry, hook_name)
            if callable(maybe):
                return maybe
            raise TypeError(f"Hook '{hook_name}' exists but is not callable")
    return None


def _validate_entry(entry, mod_path_str):
    for canonical in _HOOK_ALIASES:
        _find_hook_callable(entry, canonical)

    supported_names = set(name for names in _HOOK_ALIASES.values()
                          for name in names)
    unknown = []
    for attr in dir(entry):
        if attr.startswith("on_") and attr not in supported_names:
            unknown.append(attr)
    if unknown:
        print(
            f"[ModManager] Warning: {mod_path_str} has unknown hooks: {', '.join(sorted(unknown))}")


def _call_hook(entry, canonical_hook, *args):
    func = _find_hook_callable(entry, canonical_hook)
    if func is None:
        return

    try:
        signature = inspect.signature(func)
        positional_params = [
            p for p in signature.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(
            p.kind == p.VAR_POSITIONAL for p in signature.parameters.values())

        if has_varargs:
            func(*args)
            return

        max_args = len(positional_params)
        func(*args[:max_args])
    except (TypeError, ValueError):
        # Dynamic callables or weird signatures: best-effort full args.
        func(*args)


def _call_register(module, api, context):
    register_fn = getattr(module, "register", None)
    if not callable(register_fn):
        return None

    try:
        signature = inspect.signature(register_fn)
        positional_params = [
            p for p in signature.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(
            p.kind == p.VAR_POSITIONAL for p in signature.parameters.values())

        if has_varargs:
            return register_fn(api, context)

        argc = len(positional_params)
        if argc >= 2:
            return register_fn(api, context)
        if argc == 1:
            return register_fn(api)
        return register_fn()
    except (TypeError, ValueError):
        # Unknown callable shape: try api first.
        return register_fn(api)


class ModManager:
    def __init__(self):
        # { mod_path_str: ModRecord }
        self._records: dict[str, ModRecord] = {}
        self._mod_settings: dict[str, dict] = self._load_mod_settings_file()
        self._virtual_keys_down: set[int] = set()
        # Flags mods can set to influence core game behavior
        self.paused = False
        self.god_mode = False
        self.add_acorns = 0
        self.spawn_bear = 0
        self.set_enemy_count = -1

    def set_virtual_key(self, keycode, pressed):
        """Set synthetic key state from mods (for touch / on-screen controls)."""
        try:
            keycode = int(keycode)
        except (TypeError, ValueError):
            return

        if pressed:
            self._virtual_keys_down.add(keycode)
        else:
            self._virtual_keys_down.discard(keycode)

    def is_virtual_key_down(self, keycode):
        try:
            keycode = int(keycode)
        except (TypeError, ValueError):
            return False
        return keycode in self._virtual_keys_down

    def clear_virtual_keys(self):
        self._virtual_keys_down.clear()

    def _load_mod_settings_file(self):
        if not _MOD_SETTINGS_PATH.exists():
            return {}
        try:
            with open(_MOD_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}

            cleaned = {}
            for mod_path, values in data.items():
                normalized = _normalize_mod_path(mod_path)
                if not normalized:
                    continue
                cleaned[normalized] = values if isinstance(
                    values, dict) else {}
            return cleaned
        except Exception:
            print(
                "[ModManager] Failed reading mod_settings.json, using empty settings.")
            traceback.print_exc()
            return {}

    def _save_mod_settings_file(self):
        try:
            with open(_MOD_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._mod_settings, f, indent=4)
            return True
        except Exception:
            print("[ModManager] Failed writing mod_settings.json.")
            traceback.print_exc()
            return False

    def save_mod_settings(self):
        """Persist all per-mod settings to disk."""
        return self._save_mod_settings_file()

    def _bucket_for(self, mod_path_str, create=False):
        normalized = _normalize_mod_path(mod_path_str)
        if not normalized:
            return None
        if normalized not in self._mod_settings and create:
            self._mod_settings[normalized] = {}
        return self._mod_settings.get(normalized)

    def get_mod_settings(self, mod_path_str):
        bucket = self._bucket_for(mod_path_str, create=False)
        return dict(bucket or {})

    def get_mod_setting(self, mod_path_str, key, default=None):
        bucket = self._bucket_for(mod_path_str, create=False)
        if not isinstance(bucket, dict):
            return default
        return bucket.get(key, default)

    def set_mod_setting(self, mod_path_str, key, value, save=True):
        bucket = self._bucket_for(mod_path_str, create=True)
        if bucket is None:
            return False
        bucket[key] = value
        if save:
            return self._save_mod_settings_file()
        return True

    def update_mod_settings(self, mod_path_str, values: dict, save=True):
        if not isinstance(values, dict):
            return False
        bucket = self._bucket_for(mod_path_str, create=True)
        if bucket is None:
            return False
        bucket.update(values)
        if save:
            return self._save_mod_settings_file()
        return True

    def clear_mod_settings(self, mod_path_str):
        normalized = _normalize_mod_path(mod_path_str)
        if not normalized:
            return False
        if normalized in self._mod_settings:
            del self._mod_settings[normalized]
            return self._save_mod_settings_file()
        return True

    def remove_mod_setting(self, mod_path_str, key, save=True):
        bucket = self._bucket_for(mod_path_str, create=False)
        if not isinstance(bucket, dict):
            return False
        if key not in bucket:
            return True
        del bucket[key]
        if save:
            return self._save_mod_settings_file()
        return True

    def list_available_mods(self):
        """Return available mod paths for in-game mod menus."""
        return list_available_mods()

    def _get_record(self, mod_path_str):
        mod_path_str = _normalize_mod_path(mod_path_str)
        if not mod_path_str:
            return None
        if mod_path_str not in self._records:
            self._records[mod_path_str] = ModRecord(path=mod_path_str)
        return self._records[mod_path_str]

    def _load_module(self, mod_path_str):
        record = self._get_record(mod_path_str)
        if record is None:
            print(f"[ModManager] Invalid mod path: {mod_path_str}")
            return None, None

        full = _ROOT / record.path
        if not full.exists():
            record.load_error = f"File not found: {full}"
            print(f"[ModManager] {record.load_error}")
            return None, None

        module_name = _module_name_for_path(record.path)
        record.module_name = module_name

        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, full)
        if spec is None or spec.loader is None:
            record.load_error = "Could not create import spec"
            print(
                f"[ModManager] Failed loading {record.path}: {record.load_error}")
            return None, None

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            entry = _resolve_entry(module)
            _validate_entry(entry, record.path)
            record.metadata = _extract_metadata(module, record.path)
            record.load_error = None
            return module, entry
        except Exception as exc:
            record.load_error = str(exc)
            print(f"[ModManager] Error loading {record.path}:")
            traceback.print_exc()
            return None, None

    def _persist_enabled_mods(self):
        enabled = sorted(
            (path for path, rec in self._records.items() if rec.enabled),
            key=lambda s: s.lower(),
        )
        if list(settings.mods) != enabled:
            settings.mods = enabled
            import settings as s_mod
            s_mod.save_settings()

    def enable(self, mod_path_str):
        """Enable a mod and call load/on_load if available."""
        record = self._get_record(mod_path_str)
        if record is None:
            return False
        if record.enabled:
            return True

        module, entry = self._load_module(record.path)
        record.module = module
        record.entry = entry
        if module is None or entry is None:
            record.enabled = False
            self._persist_enabled_mods()
            return False

        try:
            import asset_handling

            api = ModAPI(self, record.path, lambda: dict(record.metadata))

            context = {
                "api": api,
                "settings": settings,
                "asset_handling": asset_handling,
                "mod_manager": self,
                "mod_path": record.path,
                "mod_id": record.path,
                "mod_metadata": dict(record.metadata),
                "mod_settings": self.get_mod_settings(record.path),
                "get_setting": (lambda key, default=None, _path=record.path:
                                self.get_mod_setting(_path, key, default)),
                "set_setting": (lambda key, value, _path=record.path:
                                self.set_mod_setting(_path, key, value, save=True)),
                "save_mod_settings": self.save_mod_settings,
            }

            registered_entry = _call_register(module, api, context)
            if registered_entry is not None:
                record.entry = registered_entry
                _validate_entry(record.entry, record.path)

            _call_hook(record.entry, "on_load", context)
        except Exception as exc:
            record.enabled = False
            record.module = None
            record.entry = None
            record.load_error = f"load failed: {exc}"
            print(f"[ModManager] load/on_load error in {record.path}:")
            traceback.print_exc()
            self._persist_enabled_mods()
            return False

        record.enabled = True
        self._persist_enabled_mods()
        print(f"[ModManager] Enabled: {record.path}")
        return True

    def disable(self, mod_path_str):
        """Disable a mod and call unload/on_unload if available."""
        record = self._get_record(mod_path_str)
        if record is None or not record.enabled:
            return

        if record.entry is not None:
            try:
                _call_hook(record.entry, "on_unload")
            except Exception:
                print(f"[ModManager] unload/on_unload error in {record.path}:")
                traceback.print_exc()

        if record.module_name and record.module_name in sys.modules:
            del sys.modules[record.module_name]

        record.enabled = False
        record.module = None
        record.entry = None
        self._persist_enabled_mods()
        print(f"[ModManager] Disabled: {record.path}")

    def toggle(self, mod_path_str):
        record = self._get_record(mod_path_str)
        if record is None:
            return
        if record.enabled:
            self.disable(record.path)
        else:
            self.enable(record.path)

    def is_enabled(self, mod_path_str):
        record = self._get_record(mod_path_str)
        return bool(record and record.enabled)

    def get_mod_status(self, mod_path_str):
        """Return status dict for UI/debugging."""
        record = self._get_record(mod_path_str)
        if record is None:
            return None
        return {
            "path": record.path,
            "enabled": record.enabled,
            "error": record.load_error,
            "metadata": dict(record.metadata),
        }

    def list_loaded(self):
        """Return enabled mods sorted by priority then path."""
        records = [r for r in self._records.values() if r.enabled]
        records.sort(key=lambda r: (r.metadata.get(
            "load_priority", 0), r.path.lower()))
        return [r.path for r in records]

    def preload_all_metadata(self):
        """Import every discovered mod just enough to read its MOD_INFO name.
        Already-enabled mods are skipped (they already have metadata)."""
        for mod_path_str in list_available_mods():
            record = self._get_record(mod_path_str)
            if record is None or record.metadata:
                continue  # already has metadata from enable()
            try:
                full = _ROOT / record.path
                module_name = _module_name_for_path(record.path) + "_meta"
                spec = importlib.util.spec_from_file_location(
                    module_name, full)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                record.metadata = _extract_metadata(module, record.path)
                # Don't keep the module in sys.modules
                sys.modules.pop(module_name, None)
            except Exception:
                pass  # bad mod file — silently skip

    def load_enabled_from_settings(self):
        """Load all mods listed in settings.mods on game startup."""
        requested = []
        for item in list(settings.mods):
            normalized = _normalize_mod_path(item)
            if normalized:
                requested.append(normalized)
            else:
                print(
                    f"[ModManager] Skipping invalid mod entry in settings: {item}")

        for mod_path_str in requested:
            self.enable(mod_path_str)

        enabled_records = [
            rec for rec in self._records.values() if rec.enabled and rec.path in requested
        ]
        enabled_records.sort(key=lambda r: (
            r.metadata.get("load_priority", 0), r.path.lower()))

        reordered = {rec.path: rec for rec in enabled_records}
        for path, rec in self._records.items():
            if path not in reordered:
                reordered[path] = rec
        self._records = reordered
        self._persist_enabled_mods()

    def reload_all(self):
        """Unload active mods, re-read settings from disk, then reload."""
        active = [path for path, rec in self._records.items() if rec.enabled]
        for mod_path_str in active:
            self.disable(mod_path_str)

        self.paused = False
        self.god_mode = False
        self.add_acorns = 0
        self.spawn_bear = 0
        self.set_enemy_count = -1
        self.clear_virtual_keys()

        settings.load_settings()
        self.load_enabled_from_settings()
        print("[ModManager] All mods reloaded.")

    def _call(self, canonical_hook, *args):
        enabled_records = [
            rec for rec in self._records.values()
            if rec.enabled and rec.entry is not None
        ]
        enabled_records.sort(key=lambda r: (
            r.metadata.get("load_priority", 0), r.path.lower()))

        for rec in enabled_records:
            try:
                _call_hook(rec.entry, canonical_hook, *args)
            except Exception as exc:
                rec.load_error = f"{canonical_hook} failed: {exc}"
                print(f"[ModManager] {canonical_hook} error in {rec.path}:")
                traceback.print_exc()

    def on_level_start(self, level, player):
        self._call("on_level_start", level, player)

    def on_update(self, level, player, dt):
        self._call("on_update", level, player, dt)

    def on_event(self, event):
        self._call("on_event", event)

    def on_draw(self, surface, level, player, camera_x):
        self._call("on_draw", surface, level, player, camera_x)


mod_manager = ModManager()
