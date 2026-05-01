import pygame
import math
import bisect


def _draw_hex(surface, cx, cy, r, fill, outline):
    """Draw a flat-top hexagon centred at (cx, cy) with radius r."""
    pts = [(cx + r * math.cos(math.radians(60 * i)),
            cy + r * math.sin(math.radians(60 * i))) for i in range(6)]
    pygame.draw.polygon(surface, fill, pts)
    pygame.draw.polygon(surface, outline, pts, 1)


class Platform:
    DEFAULT_COLOR = (70, 150, 70)

    def __init__(self, x, y, width, height, color=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color or self.DEFAULT_COLOR

    def draw(self, surface, camera_x, override_color=None):
        r = self.rect.move(-camera_x, 0)
        draw_color = override_color or self.color

        # Main slab body (dark charcoal)
        pygame.draw.rect(surface, draw_color, r, border_radius=3)

        # Top edge highlight (slightly lighter)
        lighter = tuple(min(c + 30, 255) for c in draw_color)
        pygame.draw.rect(surface, lighter,
                         pygame.Rect(r.left, r.top, r.width, 5), border_radius=3)

        # Hanging lantern decorations underneath — one every ~80px
        hanger_color = tuple(max(c - 20, 0) for c in draw_color)
        for hx in range(r.left + 28, r.right - 10, 80):
            # Vertical chain
            pygame.draw.line(surface, hanger_color,
                             (hx, r.bottom), (hx, r.bottom + 16), 2)
            # Lantern box
            pygame.draw.rect(surface, hanger_color,
                             (hx - 7, r.bottom + 16, 14, 10), border_radius=2)
            pygame.draw.rect(surface, lighter,
                             (hx - 7, r.bottom + 16, 14, 10), 1, border_radius=2)


class Exit:
    COLOR = (245, 235, 80)
    FRAME_COLOR = (180, 120, 40)
    WIDTH = 40
    HEIGHT = 46

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, self.WIDTH, self.HEIGHT)

    def draw(self, surface, camera_x, color=None, frame_color=None):
        r = self.rect.move(-camera_x, 0)
        hc = color or self.COLOR          # honey color
        dc = frame_color or self.FRAME_COLOR  # dark outline

        cx, cy = r.centerx, r.centery
        w, h = self.WIDTH, self.HEIGHT

        # Honeycomb: stack of 3 rows of hex cells
        cell_r = 9
        offsets = [
            # row 0 (top): 2 cells
            (-cell_r, -cell_r - 2), (cell_r, -cell_r - 2),
            # row 1 (middle): 3 cells
            (-cell_r * 2, 2), (0, 2), (cell_r * 2, 2),
            # row 2 (bottom): 2 cells
            (-cell_r, cell_r + 6), (cell_r, cell_r + 6),
        ]
        for ox, oy in offsets:
            _draw_hex(surface, cx + ox, cy + oy, cell_r, hc, dc)

        # Glow outline
        pygame.draw.rect(surface, (255, 240, 120, 80),
                         r.inflate(4, 4), 2, border_radius=6)


class Level:
    def __init__(self, platforms, player_start, exit_pos, bg_color=(30, 30, 50), name="",
                 coins=None, bees=None):
        self.platforms = platforms
        self.player_start = player_start
        self.exit = Exit(*exit_pos)
        self.bg_color = bg_color
        self.name = name
        self.coins = coins or []
        self.bees = bees or []


class Coin:
    RADIUS = 10
    COLOR = (255, 210, 40)
    OUTLINE = (200, 150, 0)

    def __init__(self, x, y):
        self.rect = pygame.Rect(x - self.RADIUS, y - self.RADIUS,
                                self.RADIUS * 2, self.RADIUS * 2)
        self.collected = False
        self._t = 0.0  # animation timer

    def update(self, dt):
        self._t += dt / 60.0

    def draw(self, surface, camera_x):
        if self.collected:
            return
        cx = self.rect.centerx - camera_x
        cy = self.rect.centery + int(math.sin(self._t * 3) * 3)
        r = self.RADIUS

        # Berry body (red)
        pygame.draw.circle(surface, (210, 60, 50), (cx, cy + 2), r)
        pygame.draw.circle(surface, (240, 90, 70), (cx - 2, cy), r - 2)

        # Brown acorn cap
        pygame.draw.ellipse(surface, (130, 80, 30),
                            (cx - r, cy - r - 2, r * 2, r))
        pygame.draw.ellipse(surface, (160, 100, 40),
                            (cx - r + 1, cy - r - 1, r * 2 - 2, r - 2))

        # Small green leaf stem
        pygame.draw.line(surface, (60, 140, 60),
                         (cx + 1, cy - r - 2), (cx + 5, cy - r - 8), 2)


class ShadyBear:
    """Dark enemy bear that replays the player's recorded path with a time delay."""
    WIDTH = 30
    HEIGHT = 36

    BODY_COLOR = (35,  28,  42)
    EAR_COLOR = (25,  20,  30)
    SNOUT_COLOR = (60,  48,  68)
    EYE_COLOR = (200, 60,  60)  # glowing red

    def __init__(self, delay_ms=2000):
        """delay_ms: how many milliseconds behind the player this bear lags."""
        self.delay_ms = delay_ms
        self.rect = pygame.Rect(-1000, -1000, self.WIDTH, self.HEIGHT)
        self._dir = 1
        self._t = 0.0
        self._spawned = False  # hidden until delay_ms of history exists

    def reset(self, spawn_x, spawn_y):
        """Called by reset_level — park bear off-screen until history is ready."""
        self.rect.centerx = -1000
        self.rect.centery = -1000
        self._dir = 1
        self._t = 0.0
        self._spawned = False

    def update(self, player_history, now_ms, dt):
        """player_history: deque of (timestamp_ms, cx, cy) in chronological order."""
        self._t += dt / 60.0
        if not player_history:
            return
        target_time = now_ms - self.delay_ms
        # Binary search: find the rightmost entry with timestamp <= target_time
        # Build a key sequence view using bisect on the timestamps
        lo, hi = 0, len(player_history) - 1
        idx = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if player_history[mid][0] <= target_time:
                idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if idx is not None:
            _, cx, cy = player_history[idx]
            dx = cx - self.rect.centerx
            if abs(dx) > 1:
                self._dir = 1 if dx > 0 else -1
            self.rect.centerx = cx
            self.rect.centery = cy
            self._spawned = True

    def draw(self, surface, camera_x):
        if not self._spawned:
            return
        r = self.rect.move(-camera_x, 0)
        cx = r.centerx
        hcy = r.top + 13   # head centre y
        hr = 11           # head radius

        bc = self.BODY_COLOR
        ec = self.EAR_COLOR
        sc = self.SNOUT_COLOR

        # Arms
        pygame.draw.ellipse(surface, ec,
                            (r.left - 2, r.top + 18, 8, 12))
        pygame.draw.ellipse(surface, ec,
                            (r.right - 6, r.top + 18, 8, 12))

        # Body
        pygame.draw.ellipse(surface, bc,
                            (r.left + 2, r.top + 18, r.width - 4, r.height - 18))

        # Ears
        for ex in (cx - 9, cx + 9):
            pygame.draw.circle(surface, ec, (ex, r.top + 5), 6)

        # Head
        pygame.draw.circle(surface, bc, (cx, hcy), hr)

        # Snout
        pygame.draw.ellipse(surface, sc,
                            (cx - 5, hcy + 3, 10, 7))

        # Glowing red eyes (shift toward facing direction)
        eo = 2 * self._dir
        for ex in (cx - 4 + eo, cx + 4 + eo):
            pygame.draw.circle(surface, self.EYE_COLOR, (ex, hcy - 3), 2)
            # tiny white glint
            pygame.draw.circle(surface, (255, 200, 200), (ex - 1, hcy - 4), 1)


# ── Level definitions ────────────────────────────────────────────────────────
# All levels fit within 1000 × 800 — no scrolling.
# Jump height ≈ 163 px (JUMP_FORCE=-14, GRAVITY=0.6 at 60 FPS).
# Platform vertical gaps are 120–140 px so each step is one jump.
# Layout mirrors original Shady Bears: zigzag climb left/right to top.
_SLAB = (45, 45, 52)
_SLAB2 = (55, 52, 62)
_TEAL = (110, 165, 155)

# Enemy waypoint paths — each tuple is the (centre_x, centre_y) the bear
# walks toward. They trace the same zigzag the player takes.
# y = platform.rect.top - ShadyBear.HEIGHT // 2
_PATH1 = [
    (80, 702), (290, 702),   # ground L
    (240, 572), (460, 572),   # step L1
    (540, 442), (760, 442),   # step R1
    (200, 312), (420, 312),   # step L2
    (580, 182), (800, 182),   # step R2
    (320,  82), (680,  82),   # top slab
]
_PATH2 = [
    (60, 702), (260, 702),   # ground L
    (260, 582), (420, 582),   # step L
    (580, 462), (740, 462),   # step R
    (220, 352), (380, 352),   # step L2
    (620, 242), (780, 242),   # step R2
    (260, 142), (420, 142),   # step L3
    (350,  72), (650,  72),   # top slab
]
_PATH3 = [
    (60, 702), (220, 702),   # ground L
    (280, 592), (400, 592),   # step L
    (600, 472), (720, 472),   # step R
    (220, 362), (340, 362),   # step L2
    (660, 252), (780, 252),   # step R2
    (240, 152), (360, 152),   # step L3
    (600,  62), (640,  62),   # top
]

# Alias so mods/texture-packs that reference Bee still work
Bee = ShadyBear

LEVELS = [
    # ── Level 1: Birch Forest ────────────────────────────────────────────────
    # Wide ground slabs on L and R, zigzag up to honeycomb at top centre.
    Level(
        name="Level 1 - Birch Forest",
        bg_color=_TEAL,
        player_start=(80, 670),
        exit_pos=(460, 82),          # honeycomb on top slab
        platforms=[
            Platform(0,   720, 320, 80, _SLAB),   # ground left
            Platform(680, 720, 320, 80, _SLAB),   # ground right
            Platform(220, 590, 260, 18, _SLAB2),  # step L
            Platform(520, 460, 260, 18, _SLAB),   # step R
            Platform(180, 330, 260, 18, _SLAB2),  # step L
            Platform(560, 200, 260, 18, _SLAB),   # step R
            Platform(300, 100, 400, 18, _SLAB2),  # top / exit slab
        ],
        coins=[
            Coin(350, 555),
        ],
        bees=[
            ShadyBear(delay_ms=2000),
            ShadyBear(delay_ms=3000),
            ShadyBear(delay_ms=4000),
        ],
    ),

    # ── Level 2: Deep Woods ──────────────────────────────────────────────────
    # Narrower steps, tighter gaps, more bees.
    Level(
        name="Level 2 - Deep Woods",
        bg_color=(90, 140, 130),
        player_start=(60, 670),
        exit_pos=(450, 72),
        platforms=[
            Platform(0,   720, 280, 80, _SLAB),
            Platform(720, 720, 280, 80, _SLAB),
            Platform(240, 600, 200, 18, _SLAB2),
            Platform(560, 480, 200, 18, _SLAB),
            Platform(200, 370, 200, 18, _SLAB2),
            Platform(600, 260, 200, 18, _SLAB),
            Platform(240, 160, 200, 18, _SLAB2),
            Platform(330,  90, 340, 18, _SLAB),   # top / exit slab
        ],
        coins=[
            Coin(340, 565),
        ],
        bees=[
            ShadyBear(delay_ms=2000),
            ShadyBear(delay_ms=2500),
            ShadyBear(delay_ms=3000),
            ShadyBear(delay_ms=3500),
            ShadyBear(delay_ms=4000),
        ],
    ),

    # ── Level 3: Summit ──────────────────────────────────────────────────────
    # Smallest slabs, fastest bees.
    Level(
        name="Level 3 - Summit",
        bg_color=(75, 120, 115),
        player_start=(60, 670),
        exit_pos=(455, 62),
        platforms=[
            Platform(0,   720, 240, 80, _SLAB),
            Platform(760, 720, 240, 80, _SLAB),
            Platform(260, 610, 160, 18, _SLAB2),
            Platform(580, 490, 160, 18, _SLAB),
            Platform(200, 380, 160, 18, _SLAB2),
            Platform(640, 270, 160, 18, _SLAB),
            Platform(220, 170, 160, 18, _SLAB2),
            Platform(580, 80,  160, 18, _SLAB),
            Platform(340,  80, 320, 18, _SLAB2),  # top / exit slab
        ],
        coins=[
            Coin(340, 575),
        ],
        bees=[
            ShadyBear(delay_ms=2000),
            ShadyBear(delay_ms=2500),
            ShadyBear(delay_ms=3000),
            ShadyBear(delay_ms=3500),
            ShadyBear(delay_ms=4000),
            ShadyBear(delay_ms=4500),
        ],
    ),
]
