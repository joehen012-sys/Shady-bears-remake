import pygame
import settings
from mod_manager import mod_manager

GRAVITY = 0.6
JUMP_FORCE = -14
MOVE_SPEED = 5


def _key_from_name(name):
    """Convert a key-binding string like 'space', 'ctrl', 'A' to a pygame key constant."""
    if not name:
        return None
    name = name.strip()
    if len(name) == 1:
        return ord(name.lower())
    special = {
        "space": pygame.K_SPACE,
        "ctrl": pygame.K_LCTRL,
        "lctrl": pygame.K_LCTRL,
        "rctrl": pygame.K_RCTRL,
        "shift": pygame.K_LSHIFT,
        "lshift": pygame.K_LSHIFT,
        "rshift": pygame.K_RSHIFT,
        "up": pygame.K_UP,
        "down": pygame.K_DOWN,
        "left": pygame.K_LEFT,
        "right": pygame.K_RIGHT,
        "enter": pygame.K_RETURN,
        "escape": pygame.K_ESCAPE,
    }
    return special.get(name.lower())


class Player:
    WIDTH = 36
    HEIGHT = 48
    COLOR = (220, 130, 60)
    EYE_COLOR = (30, 30, 30)

    # Animation: lists of pygame.Surface frames per state, empty = use drawn fallback
    ANIM_IDLE = []
    ANIM_WALK = []
    ANIM_JUMP = []
    ANIM_FPS = 8   # frames per second for all animations

    def __init__(self, x, y, max_jumps=1):
        self.rect = pygame.Rect(x, y, self.WIDTH, self.HEIGHT)
        self.float_x = float(x)  # sub-pixel precision
        self.float_y = float(y)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = False
        self.max_jumps = max(1, int(max_jumps))
        self.jumps_used = 0
        self._jump_was_down = False
        self._anim_time = 0.0   # accumulates real time in seconds
        self._facing = 1      # 1 = right, -1 = left

    def _get_frame(self, frames):
        """Return the correct frame surface for the current anim time."""
        if not frames:
            return None
        fps = max(1, self.ANIM_FPS)
        idx = int(self._anim_time * fps) % len(frames)
        return frames[idx]

    def update(self, platforms, dt=1.0):
        """dt is normalised to 1.0 at 60 FPS."""
        kb = settings.key_bindings
        left_key = _key_from_name(kb.get("left", "a"))
        right_key = _key_from_name(kb.get("right", "d"))
        jump_key = _key_from_name(kb.get("jump", "space"))

        keys = pygame.key.get_pressed()
        jump_down = jump_key is not None and (
            keys[jump_key] or mod_manager.is_virtual_key_down(jump_key)
        )

        self.vel_x = 0.0
        if left_key is not None and (keys[left_key] or mod_manager.is_virtual_key_down(left_key)):
            self.vel_x = -MOVE_SPEED
            self._facing = -1
        if right_key is not None and (keys[right_key] or mod_manager.is_virtual_key_down(right_key)):
            self.vel_x = MOVE_SPEED
            self._facing = 1

        if jump_down and (not self._jump_was_down) and self.jumps_used < self.max_jumps:
            self.vel_y = JUMP_FORCE
            self.on_ground = False
            self.jumps_used += 1

        # Advance animation timer (dt is 1.0 at 60 FPS → 1/60 s per tick)
        self._anim_time += dt / 60.0

        # Gravity (scaled by dt)
        self.vel_y += GRAVITY * dt
        if self.vel_y > 22:
            self.vel_y = 22

        # Horizontal movement + collision
        self.float_x += self.vel_x * dt
        self.rect.x = round(self.float_x)
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vel_x > 0:
                    self.rect.right = plat.rect.left
                elif self.vel_x < 0:
                    self.rect.left = plat.rect.right
                self.float_x = float(self.rect.x)

        # Vertical movement + collision
        self.on_ground = False
        self.float_y += self.vel_y * dt
        self.rect.y = round(self.float_y)
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vel_y > 0:
                    self.rect.bottom = plat.rect.top
                    self.on_ground = True
                    self.jumps_used = 0
                elif self.vel_y < 0:
                    self.rect.top = plat.rect.bottom
                self.vel_y = 0
                self.float_y = float(self.rect.y)

        self._jump_was_down = jump_down

    def draw(self, surface, camera_x):
        r = self.rect.move(-camera_x, 0)

        # Pick animation state
        if not self.on_ground:
            frames = self.ANIM_JUMP or self.ANIM_IDLE
        elif self.vel_x != 0:
            frames = self.ANIM_WALK or self.ANIM_IDLE
        else:
            frames = self.ANIM_IDLE

        frame = self._get_frame(frames)
        if frame is not None:
            scaled = pygame.transform.scale(frame, (r.width, r.height))
            if self._facing == -1:
                scaled = pygame.transform.flip(scaled, True, False)
            surface.blit(scaled, r.topleft)
        else:
            # Bear character — round head, ears, snout, body, arms
            body_c = self.COLOR
            dark_c = tuple(max(0,   c - 50) for c in body_c)
            light_c = tuple(min(255, c + 60) for c in body_c)
            pink_c = (210, 115, 125)

            cx = r.centerx
            hcy = r.top + 18   # head centre y
            hr = 15           # head radius

            # Arms (behind body)
            pygame.draw.ellipse(surface, dark_c,
                                (r.left - 3, r.top + 28, 11, 16))
            pygame.draw.ellipse(surface, dark_c,
                                (r.right - 8, r.top + 28, 11, 16))

            # Body
            pygame.draw.ellipse(surface, body_c,
                                (r.left + 3, r.top + 25, r.width - 6, r.height - 25))

            # Belly patch
            pygame.draw.ellipse(surface, light_c,
                                (r.left + 8, r.top + 30, r.width - 16, r.height - 36))

            # Ears (drawn before head so head slightly covers their bases)
            for ex in (cx - 12, cx + 12):
                pygame.draw.circle(surface, dark_c, (ex, r.top + 7), 7)
                pygame.draw.circle(surface, pink_c,  (ex, r.top + 7), 4)

            # Head
            pygame.draw.circle(surface, body_c, (cx, hcy), hr)

            # Snout
            pygame.draw.ellipse(surface, light_c,
                                (cx - 7, hcy + 4, 14, 9))
            # Nose
            pygame.draw.ellipse(surface, (45, 25, 15),
                                (cx - 3, hcy + 4, 6, 4))

            # Eyes (shift toward facing direction for a subtle look)
            eo = 2 * self._facing
            for ex in (cx - 5 + eo, cx + 5 + eo):
                pygame.draw.circle(surface, self.EYE_COLOR, (ex, hcy - 4), 3)
                pygame.draw.circle(surface, (255, 255, 255),
                                   (ex - 1, hcy - 5), 1)
