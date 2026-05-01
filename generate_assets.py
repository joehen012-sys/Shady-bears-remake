"""
Generates PNG assets for each texture pack.
Run once from the project root: python generate_assets.py
"""
import os
import math
import pygame

pygame.init()

ROOT = os.path.dirname(os.path.abspath(__file__))


def save(surface, *path_parts):
    path = os.path.join(ROOT, *path_parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(surface, path)
    print(f"  saved: {os.path.relpath(path, ROOT)}")


# ── helpers ────────────────────────────────────────────────────────────────

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_surface(w, h, top_color, bottom_color):
    surf = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        surf.fill(lerp_color(top_color, bottom_color, t), (0, y, w, 1))
    return surf


def noise_rect(surf, rect, color, variance=20):
    """Draw a solid rect with subtle per-pixel brightness variation."""
    import random
    rng = random.Random(rect.x * 31 + rect.y * 17)
    for x in range(rect.left, rect.right):
        for y in range(rect.top, rect.bottom):
            v = rng.randint(-variance, variance)
            c = tuple(max(0, min(255, color[i] + v)) for i in range(3))
            surf.set_at((x, y), c)


# ── player sprite ──────────────────────────────────────────────────────────

def make_player(body, eye, shine=(255, 255, 255), ear=None):
    """Draw a cute bear-like character, 36×48, RGBA."""
    W, H = 36, 48
    s = pygame.Surface((W, H), pygame.SRCALPHA)

    ear_color = ear or body

    # Ears (circles behind head)
    pygame.draw.circle(s, ear_color, (8, 10), 7)
    pygame.draw.circle(s, ear_color, (28, 10), 7)
    # Inner ear
    inner = lerp_color(ear_color, (255, 200, 200), 0.4)
    pygame.draw.circle(s, inner, (8, 10), 4)
    pygame.draw.circle(s, inner, (28, 10), 4)

    # Body
    pygame.draw.ellipse(s, body, (4, 24, 28, 22))

    # Head
    pygame.draw.ellipse(s, body, (4, 6, 28, 26))

    # Snout
    snout = lerp_color(body, (255, 220, 180), 0.4)
    pygame.draw.ellipse(s, snout, (10, 21, 16, 10))

    # Nose
    pygame.draw.ellipse(s, (60, 20, 20), (15, 20, 6, 4))

    # Eyes
    pygame.draw.circle(s, eye, (12, 17), 4)
    pygame.draw.circle(s, eye, (24, 17), 4)
    # Shine
    pygame.draw.circle(s, shine, (13, 15), 2)
    pygame.draw.circle(s, shine, (25, 15), 2)

    # Legs
    pygame.draw.rect(s, body, pygame.Rect(7, 38, 9, 9), border_radius=3)
    pygame.draw.rect(s, body, pygame.Rect(20, 38, 9, 9), border_radius=3)

    # Paw toes
    toe = lerp_color(body, (0, 0, 0), 0.25)
    for dx in range(3):
        pygame.draw.circle(s, toe, (9 + dx * 3, 47), 1)
        pygame.draw.circle(s, toe, (22 + dx * 3, 47), 1)

    return s


def make_player_walk(body, eye, frame, shine=(255, 255, 255), ear=None):
    """Walk cycle: 4 frames (frame 0-3). Legs alternate forward/back."""
    W, H = 36, 48
    s = pygame.Surface((W, H), pygame.SRCALPHA)

    ear_color = ear or body
    # leg offsets: frame drives a sine-like swing
    offsets = [(0, -4), (4, 0), (0, 4), (-4, 0)]
    lo = offsets[frame % 4]

    # Ears
    pygame.draw.circle(s, ear_color, (8, 10), 7)
    pygame.draw.circle(s, ear_color, (28, 10), 7)
    inner = lerp_color(ear_color, (255, 200, 200), 0.4)
    pygame.draw.circle(s, inner, (8, 10), 4)
    pygame.draw.circle(s, inner, (28, 10), 4)

    # Body (slight bob: up on frames 0&2, normal on 1&3)
    bob = -2 if frame % 2 == 0 else 0
    pygame.draw.ellipse(s, body, (4, 24 + bob, 28, 22))
    pygame.draw.ellipse(s, body, (4, 6 + bob, 28, 26))

    # Snout
    snout = lerp_color(body, (255, 220, 180), 0.4)
    pygame.draw.ellipse(s, snout, (10, 21 + bob, 16, 10))
    pygame.draw.ellipse(s, (60, 20, 20), (15, 20 + bob, 6, 4))

    # Eyes
    pygame.draw.circle(s, eye, (12, 17 + bob), 4)
    pygame.draw.circle(s, eye, (24, 17 + bob), 4)
    pygame.draw.circle(s, shine, (13, 15 + bob), 2)
    pygame.draw.circle(s, shine, (25, 15 + bob), 2)

    # Legs: alternate swing
    pygame.draw.rect(s, body, pygame.Rect(
        7 + lo[0],  38 + bob - lo[1], 9, 9), border_radius=3)
    pygame.draw.rect(s, body, pygame.Rect(
        20 - lo[0], 38 + bob + lo[1], 9, 9), border_radius=3)

    toe = lerp_color(body, (0, 0, 0), 0.25)
    for dx in range(3):
        pygame.draw.circle(s, toe, (9 + dx * 3 + lo[0],  47 + bob), 1)
        pygame.draw.circle(s, toe, (22 + dx * 3 - lo[0], 47 + bob), 1)

    return s


def make_player_jump(body, eye, shine=(255, 255, 255), ear=None):
    """Jump pose: arms raised, legs tucked."""
    W, H = 36, 48
    s = pygame.Surface((W, H), pygame.SRCALPHA)

    ear_color = ear or body
    pygame.draw.circle(s, ear_color, (8, 8), 7)
    pygame.draw.circle(s, ear_color, (28, 8), 7)
    inner = lerp_color(ear_color, (255, 200, 200), 0.4)
    pygame.draw.circle(s, inner, (8, 8), 4)
    pygame.draw.circle(s, inner, (28, 8), 4)

    # Body raised
    pygame.draw.ellipse(s, body, (4, 20, 28, 22))
    pygame.draw.ellipse(s, body, (4, 2, 28, 26))

    snout = lerp_color(body, (255, 220, 180), 0.4)
    pygame.draw.ellipse(s, snout, (10, 17, 16, 10))
    pygame.draw.ellipse(s, (60, 20, 20), (15, 16, 6, 4))

    pygame.draw.circle(s, eye, (12, 13), 4)
    pygame.draw.circle(s, eye, (24, 13), 4)
    pygame.draw.circle(s, shine, (13, 11), 2)
    pygame.draw.circle(s, shine, (25, 11), 2)

    # Tucked legs (spread out sideways)
    pygame.draw.rect(s, body, pygame.Rect(2,  36, 9, 9), border_radius=3)
    pygame.draw.rect(s, body, pygame.Rect(25, 36, 9, 9), border_radius=3)

    toe = lerp_color(body, (0, 0, 0), 0.25)
    for dx in range(3):
        pygame.draw.circle(s, toe, (4 + dx * 3,  45), 1)
        pygame.draw.circle(s, toe, (27 + dx * 3, 45), 1)

    return s


def make_platform_tile(w, h, base, top_stripe, crack_color=None):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    # Fill with slight noise
    noise_rect(s, pygame.Rect(0, 0, w, h), base, variance=12)
    # Top stripe
    pygame.draw.rect(s, top_stripe, (0, 0, w, 4))
    # Optional crack lines
    if crack_color:
        mid = w // 2
        pygame.draw.line(s, crack_color, (mid, 6), (mid + 4, h - 2), 1)
        pygame.draw.line(s, crack_color, (mid // 2, 5),
                         (mid // 2 - 3, h - 3), 1)
    # Edge highlight
    light = lerp_color(base, (255, 255, 255), 0.3)
    pygame.draw.line(s, light, (0, 0), (w - 1, 0), 1)
    pygame.draw.line(s, light, (0, 0), (0, h - 1), 1)
    # Edge shadow
    dark = lerp_color(base, (0, 0, 0), 0.3)
    pygame.draw.line(s, dark, (w - 1, 0), (w - 1, h - 1), 1)
    pygame.draw.line(s, dark, (0, h - 1), (w - 1, h - 1), 1)
    return s


# ── background ─────────────────────────────────────────────────────────────

def make_background_meadow(w, h):
    s = gradient_surface(w, h, (30, 70, 130), (70, 130, 200))
    # Clouds
    for cx, cy, r in [(160, 80, 40), (420, 55, 30), (700, 95, 45), (900, 60, 35)]:
        for dx, dy, cr in [(-r // 2, 0, r * 0.7), (0, -r // 3, r), (r // 2, 0, r * 0.7)]:
            pygame.draw.circle(s, (230, 240, 255),
                               (int(cx + dx), int(cy + dy)), int(cr))
    # Distant hills
    for hx, hy, hr, hc in [
        (200, h, 280, (50, 110, 60)),
        (500, h, 340, (55, 120, 65)),
        (800, h, 300, (45, 105, 55)),
    ]:
        pygame.draw.circle(s, hc, (hx, hy), hr)
    return s


def make_background_ruins(w, h):
    s = gradient_surface(w, h, (15, 10, 28), (55, 35, 75))
    # Stars
    import random
    rng = random.Random(42)
    for _ in range(120):
        sx = rng.randint(0, w - 1)
        sy = rng.randint(0, h // 2)
        br = rng.randint(140, 255)
        s.set_at((sx, sy), (br, br, br))
    # Moon
    pygame.draw.circle(s, (220, 215, 190), (820, 110), 55)
    pygame.draw.circle(s, (15, 10, 28), (850, 90), 50)  # crescent cutout
    # Distant ruins silhouette
    ruin_color = (35, 20, 50)
    cols = [
        (50, h - 120, 30, 120),
        (110, h - 80, 20, 80),
        (170, h - 140, 40, 140),
        (700, h - 100, 25, 100),
        (760, h - 160, 35, 160),
        (820, h - 90, 20, 90),
        (900, h - 130, 30, 130),
    ]
    for rx, ry, rw, rh in cols:
        pygame.draw.rect(s, ruin_color, (rx, ry, rw, rh))
        # battlements
        for bx in range(rx, rx + rw - 6, 8):
            pygame.draw.rect(s, ruin_color, (bx, ry - 8, 5, 8))
    return s


def make_background_summit(w, h):
    s = gradient_surface(w, h, (10, 18, 35), (25, 45, 30))
    # Stars
    import random
    rng = random.Random(99)
    for _ in range(80):
        sx = rng.randint(0, w - 1)
        sy = rng.randint(0, h * 2 // 3)
        br = rng.randint(160, 255)
        s.set_at((sx, sy), (br, br, br))
    # Snow-capped mountain peaks in the distance
    peak_color = (200, 210, 220)
    snow_color = (240, 245, 255)
    for px, py, pw in [(150, 300, 220), (450, 260, 260), (750, 310, 200), (950, 280, 180)]:
        points = [(px - pw // 2, h), (px, py), (px + pw // 2, h)]
        pygame.draw.polygon(s, peak_color, points)
        # Snow cap
        snow_h = (h - py) * 0.25
        snow_pts = [
            (px - pw // 8, int(py + snow_h)),
            (px, py),
            (px + pw // 8, int(py + snow_h)),
        ]
        pygame.draw.polygon(s, snow_color, snow_pts)
    return s


def make_background_purple(w, h):
    s = gradient_surface(w, h, (10, 5, 25), (40, 20, 70))
    # Stars & sparkles
    import random
    rng = random.Random(7)
    for _ in range(150):
        sx = rng.randint(0, w - 1)
        sy = rng.randint(0, h)
        br = rng.randint(120, 255)
        col = (br, int(br * 0.6), br)
        s.set_at((sx, sy), col)
    # Swirling nebula blobs (simple circles with alpha would need per-pixel work; do ellipses)
    for nx, ny, nr, nc in [
        (300, 200, 120, (80, 30, 120)),
        (700, 350, 90, (60, 20, 100)),
        (150, 500, 70, (100, 40, 140)),
    ]:
        temp = pygame.Surface((nr * 2, nr * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(temp, (*nc, 60), (0, 0, nr * 2, nr * 2))
        s.blit(temp, (nx - nr, ny - nr))
    return s


# ═══════════════════════════════════════════════════════════════════════════
# PACK DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

print("Generating assets for defualt_pack …")
PACK = "texture_packs/defualt_pack"
save(make_player((220, 130, 60), (30, 30, 30)), PACK, "player_idle_0.png")
# subtle – same pose, slight blink handled by walk bob
save(make_player((220, 130, 60), (30, 30, 30)), PACK, "player_idle_1.png")
for i in range(4):
    save(make_player_walk((220, 130, 60), (30, 30, 30), i),
         PACK, f"player_walk_{i}.png")
save(make_player_jump((220, 130, 60), (30, 30, 30)), PACK, "player_jump_0.png")
save(make_background_meadow(1000, 800), PACK, "background_day.png")
save(make_platform_tile(32, 20, (70, 150, 70), (110, 200, 110),
     crack_color=(50, 110, 50)), PACK, "platform_tile.png")

print("Generating assets for exsample_pack …")
PACK = "texture_packs/exsample_pack"
_ep = dict(body=(180, 80, 200), eye=(255, 255, 100),
           shine=(200, 255, 200), ear=(140, 50, 170))
save(make_player(**_ep), PACK, "player_idle_0.png")
save(make_player(**_ep), PACK, "player_idle_1.png")
for i in range(4):
    save(make_player_walk(_ep["body"], _ep["eye"], i,
         shine=_ep["shine"], ear=_ep["ear"]), PACK, f"player_walk_{i}.png")
save(make_player_jump(_ep["body"], _ep["eye"],
     shine=_ep["shine"], ear=_ep["ear"]), PACK, "player_jump_0.png")
save(make_background_purple(1000, 800), PACK, "background_day.png")
save(make_platform_tile(32, 20, (100, 60, 180), (150, 100, 220),
     crack_color=(60, 30, 110)), PACK, "platform_tile.png")

print("Generating assets for new_pack …")
PACK = "texture_packs/new_pack"
_np = dict(body=(225, 120, 70), eye=(25, 25, 25), ear=(190, 90, 50))
save(make_player(**_np), PACK, "player_idle_0.png")
save(make_player(**_np), PACK, "player_idle_1.png")
for i in range(4):
    save(make_player_walk(_np["body"], _np["eye"], i,
         ear=_np["ear"]), PACK, f"player_walk_{i}.png")
save(make_player_jump(_np["body"], _np["eye"],
     ear=_np["ear"]), PACK, "player_jump_0.png")
save(make_background_summit(1000, 800), PACK, "background_day.png")
save(make_platform_tile(32, 20, (95, 175, 110), (140, 210, 150),
     crack_color=(60, 130, 75)), PACK, "platform_tile.png")

print("\nDone! All assets generated.")
pygame.quit()
