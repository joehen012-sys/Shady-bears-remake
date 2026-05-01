import json
import pathlib

project_root = pathlib.Path(__file__).parent
assets_path = project_root / "assets"
texture_packs_path = project_root / "texture_packs"

current_texture_pack = {}
_current_pack_folder = None  # folder containing the active pack's JSON


def load_pack_image(filename):
    """Load a PNG (or other image) from the active pack's folder.
    filename is the value stored in the JSON, e.g. 'player_idle.png'.
    Returns a pygame.Surface or None if the file doesn't exist / pygame not init'd.
    """
    if not filename or _current_pack_folder is None:
        return None
    path = _current_pack_folder / filename
    if not path.exists():
        return None
    try:
        import pygame
        return pygame.image.load(str(path)).convert_alpha()
    except Exception as e:
        print(f"[asset_handling] Could not load image '{path}': {e}")
        return None


def load_pack_animation(value):
    """Load an animation from the pack.
    value can be:
      - a string  -> single-frame animation, returns [Surface] or []
      - a list    -> multi-frame animation, returns [Surface, ...]
    Missing / unloadable frames are skipped.
    """
    if not value:
        return []
    if isinstance(value, str):
        frames = [value]
    else:
        frames = list(value)
    result = []
    for fname in frames:
        surf = load_pack_image(fname)
        if surf is not None:
            result.append(surf)
    return result


def _resolve_texture_pack_path(texture_pack_reference):
    ref = pathlib.Path(texture_pack_reference)
    candidates = []

    if ref.suffix.lower() == ".json":
        candidates.append(ref)
        candidates.append(project_root / ref)
        candidates.append(texture_packs_path / ref)
    else:
        candidates.append(texture_packs_path / ref / f"{ref.name}.json")
        candidates.append(texture_packs_path /
                          f"{texture_pack_reference}.json")
        candidates.append(project_root / ref)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def load_asset(asset_name):
    asset_path = assets_path / asset_name
    if asset_path.exists():
        with open(asset_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"Asset '{asset_name}' not found.")
        return None


def load_texture_pack(texture_pack_name):
    global current_texture_pack, _current_pack_folder

    texture_pack_path = _resolve_texture_pack_path(texture_pack_name)
    if texture_pack_path is not None and texture_pack_path.exists():
        with open(texture_pack_path, "r", encoding="utf-8") as f:
            current_texture_pack = json.load(f)
            _current_pack_folder = texture_pack_path.parent
            return current_texture_pack
    else:
        print(f"Texture pack '{texture_pack_name}' not found.")
        return None


def get_texture(category, key, fallback=None):
    if not current_texture_pack:
        return fallback

    return current_texture_pack.get(category, {}).get(key, fallback)


def list_texture_packs():
    packs = []
    for pack_file in texture_packs_path.rglob("*.json"):
        packs.append(str(pack_file.relative_to(project_root).as_posix()))
    return sorted(packs)


def create_texture_pack(pack_name, base_pack=None):
    pack_folder = texture_packs_path / pack_name
    pack_folder.mkdir(parents=True, exist_ok=True)
    pack_file = pack_folder / f"{pack_name}.json"

    if base_pack:
        source_data = load_texture_pack(base_pack)
        if source_data is None:
            source_data = {
                "player": {},
                "background": {},
                "items": {},
                "colors": {}
            }
    else:
        source_data = {
            "player": {},
            "background": {},
            "items": {},
            "colors": {}
        }

    with open(pack_file, "w", encoding="utf-8") as f:
        json.dump(source_data, f, indent=2)

    return str(pack_file.relative_to(project_root).as_posix())


def fallback_texture_pack():
    for fallback_name in ["default", "default_pack", "defualt_pack"]:
        data = load_texture_pack(fallback_name)
        if data is not None:
            return data
    return None
