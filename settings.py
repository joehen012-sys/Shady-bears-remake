import json
import settings
import pathlib

settings_path = pathlib.Path(__file__).parent / "settings.json"


def load_settings():
    with open(settings_path, "r") as f:
        data = json.load(f)
        settings.WINDOW_WIDTH = data["WINDOW_WIDTH"]
        settings.WINDOW_HEIGHT = data["WINDOW_HEIGHT"]
        settings.refresh_rate = data["refresh_rate"]
        settings.texture_pack = data["texture_pack"]
        settings.mods = data["mods"]
        settings.key_bindings = data["key_bindings"]
        settings.window_mode = data.get("window_mode", "window")


def save_settings():
    data = {
        "WINDOW_WIDTH": settings.WINDOW_WIDTH,
        "WINDOW_HEIGHT": settings.WINDOW_HEIGHT,
        "refresh_rate": settings.refresh_rate,
        "texture_pack": settings.texture_pack,
        "mods": settings.mods,
        "key_bindings": settings.key_bindings,
        "window_mode": getattr(settings, "window_mode", "window")
    }
    with open(settings_path, "w") as f:
        json.dump(data, f, indent=4)


def change_setting(key, value):
    if hasattr(settings, key):
        setattr(settings, key, value)
        save_settings()
    else:
        print(f"Setting '{key}' does not exist.")


load_settings()
