import math
import random
import pygame

from src.animation import ease_out_cubic


class Particle:
    __slots__ = ["x", "y", "vx", "vy", "life", "max_life", "color", "size", "gravity"]

    def __init__(self, x, y, vx, vy, life, color, size=3, gravity=0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit_dust(self, x, y):
        for _ in range(random.randint(4, 8)):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(15, 45)
            c = random.randint(140, 180)
            self.particles.append(Particle(
                x, y, math.cos(angle) * speed, math.sin(angle) * speed,
                random.uniform(0.3, 0.6), (c, c - 15, c - 30), random.uniform(2, 4), 80
            ))

    def emit_sparkle(self, x, y):
        for _ in range(random.randint(8, 14)):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(30, 80)
            c = random.choice([(255, 240, 100), (255, 200, 60), (255, 255, 180), (200, 255, 150)])
            self.particles.append(Particle(
                x, y, math.cos(angle) * speed, math.sin(angle) * speed,
                random.uniform(0.4, 0.8), c, random.uniform(2, 4)
            ))

    def emit_confetti(self, w):
        for _ in range(35):
            c = random.choice([
                (255, 100, 100), (100, 200, 255), (255, 220, 60),
                (100, 255, 140), (255, 150, 220), (200, 150, 255)
            ])
            self.particles.append(Particle(
                random.uniform(0, w), random.uniform(-30, 0),
                random.uniform(-20, 20), random.uniform(40, 100),
                random.uniform(1.5, 3.0), c, random.uniform(3, 6), 30
            ))

    def update(self, dt):
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life > 0:
                p.vy += p.gravity * dt
                p.x += p.vx * dt
                p.y += p.vy * dt
                alive.append(p)
        self.particles = alive

    def draw(self, screen, offset_x=0, offset_y=0):
        for p in self.particles:
            alpha = max(0, min(255, int(255 * (p.life / p.max_life))))
            sz = max(1, int(p.size * (p.life / p.max_life)))
            s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
            col = p.color + (alpha,) if len(p.color) == 3 else p.color
            pygame.draw.circle(s, col, (sz, sz), sz)
            screen.blit(s, (int(p.x + offset_x) - sz, int(p.y + offset_y) - sz))


def _apply_sprite_effects(sprite: pygame.Surface, t: float, is_pushing: bool, tile_size: int) -> tuple[pygame.Surface, int, int]:
    """Apply bobbing, tilt, and squash-stretch to a sprite during movement.
    Returns (transformed_surface, dx_offset, dy_offset)."""
    bob_y = int(math.sin(t * math.pi) * -4)
    if is_pushing:
        tilt_deg = math.sin(t * math.pi * 2) * 4.0
        sx = 1.0 + math.sin(t * math.pi) * 0.04
        sy = 1.0 - math.sin(t * math.pi) * 0.04
    else:
        tilt_deg = math.sin(t * math.pi * 2) * 6.0
        sx = 1.0 + math.sin(t * math.pi * 2) * 0.03
        sy = 1.0 - math.sin(t * math.pi * 2) * 0.03

    new_w = max(1, int(tile_size * sx))
    new_h = max(1, int(tile_size * sy))
    stretched = pygame.transform.smoothscale(sprite, (new_w, new_h))
    if abs(tilt_deg) > 0.5:
        stretched = pygame.transform.rotate(stretched, tilt_deg)
    ow, oh = stretched.get_size()
    dx = (tile_size - ow) // 2
    dy = (tile_size - oh) + bob_y
    return stretched, dx, dy


def _apply_crate_effects(sprite: pygame.Surface, t: float, tile_size: int) -> tuple[pygame.Surface, int, int]:
    """Apply squash-stretch bounce to a crate being pushed."""
    if t < 0.3:
        sx = 1.0 + (0.3 - t) * 0.15
        sy = 1.0 - (0.3 - t) * 0.1
    elif t > 0.7:
        bounce = (t - 0.7) / 0.3
        sx = 1.0 + math.sin(bounce * math.pi) * 0.04
        sy = 1.0 - math.sin(bounce * math.pi) * 0.03
    else:
        sx, sy = 1.0, 1.0
    new_w = max(1, int(tile_size * sx))
    new_h = max(1, int(tile_size * sy))
    stretched = pygame.transform.smoothscale(sprite, (new_w, new_h))
    dx = (tile_size - new_w) // 2
    dy = tile_size - new_h
    return stretched, dx, dy


class Renderer:
    def __init__(self, catalog, tile_size: int) -> None:
        self.catalog = catalog
        self.tile_size = tile_size

    def _get_walk_pose(self, t: float, is_pushing: bool) -> str:
        """Choose sprite pose based on animation progress for a smooth walk cycle."""
        if is_pushing:
            return "push"
        if t < 0.35:
            return "walk1"
        elif t < 0.65:
            return "idle"
        else:
            return "walk2"

    def draw_playfield(self, surface: pygame.Surface, state, player_direction: str, motion,
                       move_trails=None, move_from=None, move_progress=0.0,
                       is_moving=False, is_pushing=False, walk_frame=0,
                       idle_frame=0, box_moving=False, box_from=None, box_to=None) -> tuple[int, int]:
        ts = self.tile_size
        num_rows = len(state.rows)
        num_cols = len(state.rows[0]) if state.rows else 0

        game_area_w = surface.get_width()
        game_area_h = surface.get_height()
        ox = (game_area_w - num_cols * ts) // 2
        oy = (game_area_h - num_rows * ts) // 2

        if move_trails is None:
            move_trails = []

        for r, row in enumerate(state.rows):
            for c, ch in enumerate(row):
                x, y = ox + c * ts, oy + r * ts
                if (r, c) not in state.walls:
                    surface.blit(self.catalog.tile("floor"), (x, y))
                if (r, c) in state.targets:
                    surface.blit(self.catalog.tile("target"), (x, y))
                if (r, c) in state.walls:
                    surface.blit(self.catalog.tile("wall"), (x, y))

        animating_boxes = {}
        for trail in move_trails:
            if trail.get("has_box") and trail.get("box_to"):
                t = ease_out_cubic(min(trail["progress"], 1.0))
                bfr, bfc = trail["box_from"]
                btr, btc = trail["box_to"]
                animating_boxes[(btr, btc)] = (
                    ox + int(bfc * ts + (btc - bfc) * ts * t),
                    oy + int(bfr * ts + (btr - bfr) * ts * t),
                    min(trail["progress"], 1.0),
                )
        if box_moving and is_moving and box_to:
            t = ease_out_cubic(min(move_progress, 1.0))
            bfr, bfc = box_from
            btr, btc = box_to
            animating_boxes[(btr, btc)] = (
                ox + int(bfc * ts + (btc - bfc) * ts * t),
                oy + int(bfr * ts + (btr - bfr) * ts * t),
                min(move_progress, 1.0),
            )

        for r, c in state.boxes:
            if (r, c) in animating_boxes:
                bx, by, raw_t = animating_boxes[(r, c)]
                key = "crate_ok" if (r, c) in state.targets else "crate"
                base_spr = self.catalog.tile(key)
                eff_spr, edx, edy = _apply_crate_effects(base_spr, raw_t, ts)
                surface.blit(eff_spr, (bx + edx, by + edy))
            else:
                bx, by = ox + c * ts, oy + r * ts
                key = "crate_ok" if (r, c) in state.targets else "crate"
                surface.blit(self.catalog.tile(key), (bx, by))

        pr, pc = state.player
        px, py = ox + pc * ts, oy + pr * ts
        raw_t = 0.0

        if is_moving and move_from:
            raw_t = min(move_progress, 1.0)
            t = ease_out_cubic(raw_t)
            fr, fc = move_from
            px = ox + int(fc * ts + (pc - fc) * ts * t)
            py = oy + int(fr * ts + (pr - fr) * ts * t)
            pose = self._get_walk_pose(raw_t, is_pushing)
            p_spr = self.catalog.player_sprite(player_direction, pose)
            eff_spr, edx, edy = _apply_sprite_effects(p_spr, raw_t, is_pushing, ts)
            surface.blit(eff_spr, (px + edx, py + edy))
        elif move_trails:
            last = move_trails[-1]
            raw_t = min(last["progress"], 1.0)
            t = ease_out_cubic(raw_t)
            fr, fc = last["from"]
            tr, tc = last["to"]
            px = ox + int(fc * ts + (tc - fc) * ts * t)
            py = oy + int(fr * ts + (tr - fr) * ts * t)
            trail_dir = last.get("direction", player_direction)
            trail_pushing = last.get("is_pushing", last.get("has_box", False))
            pose = self._get_walk_pose(raw_t, trail_pushing)
            p_spr = self.catalog.player_sprite(trail_dir, pose)
            eff_spr, edx, edy = _apply_sprite_effects(p_spr, raw_t, trail_pushing, ts)
            surface.blit(eff_spr, (px + edx, py + edy))
        else:
            p_spr = self.catalog.player_sprite(player_direction, "idle")
            surface.blit(p_spr, (px, py))

        return (ox, oy)
