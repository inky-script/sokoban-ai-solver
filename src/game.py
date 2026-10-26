import sys
import time
from pathlib import Path

import pygame

from src.animation import AnimationController, ease_out_cubic
from src.assets import AssetCatalog
from src.config import FPS, HUD_HEIGHT, TILE, MOVE_SPEED, AI_MOVE_SPEED, MAX_UNDO
from src.levels import LEVEL_DATA, level_bounds
from src.logic import GameState, StrategicProAI, HillClimbAI, AI_SOLVERS
from src.render import Renderer, ParticleSystem
from src.ui import UIRenderer


class SokobanKenneyGame:
    def __init__(self, headless: bool = False) -> None:
        pygame.init()
        max_cols, max_rows = level_bounds(LEVEL_DATA)
        width = max(max_cols * TILE + 80, 720)
        height = max_rows * TILE + HUD_HEIGHT + 200
        self.W = width
        self.H = height
        if headless:
            self.screen = pygame.Surface((width, height))
        else:
            pygame.display.set_caption("Sokoban - Phiên bản Kenney")
            self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()
        self.state = "SPLASH"
        self.project_root = Path(__file__).resolve().parents[1]
        self.catalog = AssetCatalog(self.project_root, TILE)
        self.renderer = Renderer(self.catalog, TILE)
        self.ui = UIRenderer(width, height)
        self.animation = AnimationController(TILE)
        self.ai = StrategicProAI()
        self.particles = ParticleSystem()
        self.logic = None
        self.player_direction = "down"
        self.headless = headless
        self.btns = []
        self.ai_modal_btns = []
        self.anim_tick = 0
        self.idle_frame = 0
        self.idle_timer = 0
        self.walk_frame = 0
        self.is_pushing = False
        self.moving = False
        self.move_progress = 0.0
        self.move_from = (0, 0)
        self.move_to = (0, 0)
        self.box_moving = False
        self.box_from = (0, 0)
        self.box_to = (0, 0)
        self.move_trails = []
        self.play_start_time = 0
        self.play_elapsed = 0
        self.transition_alpha = 0
        self.transitioning = False
        self.transition_target = None
        self.won = False
        self.win_confetti_done = False
        self.ai_step_timer = 0
        self.current_level_idx = 0
        self.undo_limit = MAX_UNDO # This will now be the max budget
        self.undo_budget = MAX_UNDO
        self.sound_played = False
        self.player_failed = False
        self.menu_bg = self.catalog.get_image("splash_bg", (self.W, self.H))
        self.intro_chars_visible = 0
        self.intro_chars_timer = 0
        self.intro_finished = False
        self.splash_bg = self.catalog.get_image("splash_bg", (self.W, self.H))

    def start_level(self, level_index: int) -> None:
        self.current_level_idx = level_index
        level = LEVEL_DATA[level_index]
        self.undo_limit = level.get("n", MAX_UNDO)
        self.undo_budget = self.undo_limit
        self.logic = GameState.from_rows(level["name"], level["map"])
        self.ai.load_from_level_data(LEVEL_DATA, level_index)
        self.state = "PLAY"
        self.won = False
        self.win_confetti_done = False
        self.player_direction = "down"
        self.moving = False
        self.is_pushing = False
        self.walk_frame = 0
        self.move_trails = []
        self.particles.particles.clear()
        self.play_elapsed = 0
        self.transition_alpha = 255
        self.transitioning = True
        self.transition_target = "PLAY"
        self.sound_played = False
        self.player_failed = False
        pygame.mixer.music.stop()

    def _select_ai(self, solver_index: int) -> None:
        """Instantiate the chosen AI solver and activate it."""
        solver_cls = AI_SOLVERS[solver_index]
        self.ai = solver_cls()
        if self.logic:
            self.ai.load_from_level_data(LEVEL_DATA, self.current_level_idx)
            # Re-sync to current game state
            self.ai.player = self.logic.player
            self.ai.boxes = set(self.logic.boxes)
            self.ai.steps = self.logic.steps
        self.ai.ai_mode = True
        self.state = "PLAY"

    def _try_move(self, dr: int, dc: int) -> None:
        if self.moving or self.won or self.player_failed or self.logic is None:
            return
        g = self.logic
        nr, nc = g.player[0] + dr, g.player[1] + dc
        if dr == -1:
            self.player_direction = "up"
        elif dr == 1:
            self.player_direction = "down"
        elif dc == -1:
            self.player_direction = "left"
        elif dc == 1:
            self.player_direction = "right"
        if (nr, nc) in g.walls:
            return
        g.save_undo()
        # Remove stack capping, we use a total budget instead
        self.box_moving = False
        self.is_pushing = False
        if (nr, nc) in g.boxes:
            nnr, nnc = nr + dr, nc + dc
            if (nnr, nnc) in g.walls or (nnr, nnc) in g.boxes:
                g.undo_stack.pop()
                return
            g.boxes.remove((nr, nc))
            g.boxes.add((nnr, nnc))
            self.box_moving = True
            self.box_from = (nr, nc)
            self.box_to = (nnr, nnc)
            self.is_pushing = True
            px = nr * TILE + TILE // 2
            py = nc * TILE + TILE // 2
            self.particles.emit_dust(px, py)
            if (nnr, nnc) in g.targets:
                sx = nnr * TILE + TILE // 2
                sy = nnc * TILE + TILE // 2
                self.particles.emit_sparkle(sx, sy)
        self.move_from = (g.player[0], g.player[1])
        self.move_to = (nr, nc)
        g.player = (nr, nc)
        g.steps += 1
        self.moving = True
        self.move_progress = 0
        self.walk_frame = (self.walk_frame + 1) % 2
        self.move_trails.append({
            "from": self.move_from, "to": self.move_to, "progress": 0,
            "has_box": self.box_moving,
            "box_from": self.box_from if self.box_moving else None,
            "box_to": self.box_to if self.box_moving else None,
            "direction": self.player_direction,
            "is_pushing": self.is_pushing,
        })

    def _play_sound(self, key: str) -> None:
        if self.headless or self.sound_played:
            return
        path = self.catalog.sounds.get(key)
        if path and Path(path).exists():
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                self.sound_played = True
            except Exception as e:
                print(f"Error playing sound {key}: {e}")

    def run_one_frame(self, dt: float) -> None:
        self.anim_tick += 1
        if self.transitioning:
            self.transition_alpha = max(0, self.transition_alpha - 600 * dt)
            if self.transition_alpha <= 0:
                self.transitioning = False
                if self.transition_target:
                    self.state = self.transition_target
                    self.transition_target = None

        if self.state == "PLAY" and self.logic is not None:
            hud_h = HUD_HEIGHT
            game_h = self.H - hud_h

            self.idle_timer += dt
            if self.idle_timer > 0.35:
                self.idle_timer = 0
                self.idle_frame = (self.idle_frame + 1) % 4

            cur_speed = AI_MOVE_SPEED if self.ai.ai_mode else MOVE_SPEED
            if self.moving:
                self.move_progress += cur_speed * dt
                if self.move_progress >= 1.0:
                    self.move_progress = 1.0
                    self.moving = False

            alive_trails = []
            for trail in self.move_trails:
                trail["progress"] += cur_speed * dt
                if trail["progress"] < 1.0:
                    alive_trails.append(trail)
            self.move_trails = alive_trails

            game_surface = pygame.Surface((self.W, game_h), pygame.SRCALPHA)
            game_surface.fill((28, 24, 36))
            p_offset = self.renderer.draw_playfield(
                game_surface, self.logic, self.player_direction, motion=None,
                move_trails=self.move_trails, move_from=self.move_from,
                move_progress=self.move_progress, is_moving=self.moving,
                is_pushing=self.is_pushing, walk_frame=self.walk_frame,
                idle_frame=self.idle_frame, box_moving=self.box_moving,
                box_from=self.box_from, box_to=self.box_to,
            )
            ox, oy = p_offset

            self.particles.update(dt)
            self.particles.draw(game_surface, ox, oy)

            if self.logic.is_complete() and not self.moving:
                if not self.won:
                    self.won = True
                if not self.win_confetti_done:
                    self.particles.emit_confetti(self.W)
                    self.win_confetti_done = True
                    self._play_sound("win")
                self.ui.draw_win_overlay(game_surface, game_h, self.logic.steps, self.play_elapsed, self.anim_tick)

            if self.ai.failed and not self.won:
                self.ai.ai_mode = False
                self.ui.draw_fail_overlay(game_surface, game_h,
                                         self.ai.restart_count, self.play_elapsed,
                                         self.anim_tick, is_ai=True)
                self._play_sound("fail")

            if (self.player_failed or self.logic.is_deadlocked()) and not self.ai.ai_mode and not self.won and not self.moving:
                if not self.player_failed:
                    self.player_failed = True
                    self._play_sound("fail")
                
                self.ui.draw_fail_overlay(game_surface, game_h,
                                         0, self.play_elapsed,
                                         self.anim_tick, is_ai=False)

            self.screen.fill((28, 24, 36))
            self.screen.blit(game_surface, (0, 0))

            if not self.won and not self.ai.failed and not self.player_failed:
                self.play_elapsed += dt

            self.ui.draw_hud(
                self.screen, self.logic.name, self.ai.ai_mode,
                self.logic.targets, self.logic.boxes, self.logic.steps,
                self.ai.best_h, self.ai.no_improve, self.ai.restart_count,
                self.undo_budget, self.undo_limit, self.play_elapsed, game_h,
            )

            if self.ai.ai_mode and not self.won:
                self.ai_step_timer += dt
                if self.ai_step_timer >= 0.03:
                    self.ai_step_timer = 0
                    old_player = self.ai.player
                    old_boxes = frozenset(self.ai.boxes)
                    d = self.ai.ai_step()
                    if d:
                        dr, dc = d
                        if dr == -1:
                            self.player_direction = "up"
                        elif dr == 1:
                            self.player_direction = "down"
                        elif dc == -1:
                            self.player_direction = "left"
                        elif dc == 1:
                            self.player_direction = "right"
                        if d == (0, 0):
                            # AI Restarted
                            self.move_trails = []
                            self.moving = False
                        
                        self.logic.player = self.ai.player
                        self.logic.boxes = set(self.ai.boxes)
                        self.logic.steps = self.ai.steps
                        new_boxes = frozenset(self.ai.boxes)
                        moved_box_to = new_boxes - old_boxes
                        moved_box_from = old_boxes - new_boxes
                        has_box = bool(moved_box_to)
                        trail = {
                            "from": old_player, "to": self.ai.player, "progress": 0,
                            "has_box": has_box,
                            "box_from": list(moved_box_from)[0] if moved_box_from else None,
                            "box_to": list(moved_box_to)[0] if moved_box_to else None,
                            "direction": self.player_direction,
                            "is_pushing": has_box,
                        }
                        self.move_trails.append(trail)
                        if len(self.move_trails) > 8:
                            self.move_trails = self.move_trails[-4:]

        elif self.state == "AI_SELECT":
            # Draw play state underneath then modal on top
            if self.logic is not None:
                hud_h = HUD_HEIGHT
                game_h = self.H - hud_h
                game_surface = pygame.Surface((self.W, game_h), pygame.SRCALPHA)
                game_surface.fill((28, 24, 36))
                self.renderer.draw_playfield(
                    game_surface, self.logic, self.player_direction, motion=None,
                )
                self.screen.fill((28, 24, 36))
                self.screen.blit(game_surface, (0, 0))
                self.ui.draw_hud(
                    self.screen, self.logic.name, False,
                    self.logic.targets, self.logic.boxes, self.logic.steps,
                    self.ai.best_h, self.ai.no_improve, self.ai.restart_count,
                    self.undo_budget, self.undo_limit, self.play_elapsed, game_h,
                )
            self.ai_modal_btns = self.ui.draw_ai_modal(self.screen, AI_SOLVERS, self.anim_tick)

        elif self.state == "INTRO":
            self.intro_chars_timer += dt
            if self.intro_chars_timer > 0.02:
                self.intro_chars_timer = 0
                self.intro_chars_visible += 1
            self.intro_finished = self.ui.draw_intro(self.screen, self.anim_tick, self.intro_chars_visible, self.splash_bg)
        
        elif self.state == "SPLASH":
            self.ui.draw_splash(self.screen, self.splash_bg, self.anim_tick)

        else:
            self.btns = self.ui.draw_menu(self.screen, LEVEL_DATA, self.anim_tick, self.menu_bg)

        if self.transitioning or self.transition_alpha > 0:
            ov = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, int(self.transition_alpha)))
            self.screen.blit(ov, (0, 0))

        if self.state == "PLAY" and self.won:
            self.particles.update(dt)
            self.particles.draw(self.screen)

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if self.state == "INTRO":
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_RETURN:
                            if self.intro_finished:
                                self.state = "MENU"
                            else:
                                self.intro_chars_visible = 1000
                        elif e.key == pygame.K_k:
                            self.state = "MENU"
                    continue
                if self.state == "SPLASH":
                    if e.type == pygame.KEYDOWN or e.type == pygame.MOUSEBUTTONDOWN:
                        self.state = "INTRO"
                    continue
                if e.type == pygame.MOUSEBUTTONDOWN and self.state == "MENU":
                    for rect, idx in self.btns:
                        if rect.collidepoint(e.pos):
                            self.start_level(idx)
                if e.type == pygame.MOUSEBUTTONDOWN and self.state == "AI_SELECT":
                    for rect, idx in self.ai_modal_btns:
                        if rect.collidepoint(e.pos):
                            self._select_ai(idx)
                if e.type == pygame.KEYDOWN and self.state == "AI_SELECT":
                    if e.key == pygame.K_ESCAPE:
                        self.state = "PLAY"
                    elif e.key in (pygame.K_1, pygame.K_KP1):
                        self._select_ai(0)
                    elif e.key in (pygame.K_2, pygame.K_KP2):
                        self._select_ai(1)
                if e.type == pygame.KEYDOWN and self.state == "PLAY":
                    if e.key == pygame.K_TAB:
                        if self.ai.ai_mode:
                            self.ai.ai_mode = False
                        else:
                            self.state = "AI_SELECT"
                    if e.key == pygame.K_ESCAPE:
                        self.ai.ai_mode = False
                        self.state = "MENU"
                        self.particles.particles.clear()
                        pygame.mixer.music.stop()
                    if e.key == pygame.K_r and self.logic:
                        self.ai.ai_mode = False
                        self.player_failed = False
                        self.ai.restart_count += 1
                        # Save restart count before reload
                        rc = self.ai.restart_count
                        self.start_level(self.current_level_idx)
                        self.ai.restart_count = rc
                    if e.key == pygame.K_z and self.logic:
                        if not self.moving and self.undo_budget > 0 and self.logic.undo_stack:
                            self.logic.undo()
                            self.undo_budget -= 1
                            self.player_failed = False
                            self.sound_played = False # Allow sound to play again if they fail again
                            if not self.logic.is_deadlocked():
                                pygame.mixer.music.stop() # Stop fail music if undo fixes deadlock
                            self.ai.player = self.logic.player
                            self.ai.boxes = set(self.logic.boxes)
                            self.ai.steps = self.logic.steps
                    if not self.ai.ai_mode:
                        move_map = {
                            pygame.K_UP: (-1, 0), pygame.K_DOWN: (1, 0),
                            pygame.K_LEFT: (0, -1), pygame.K_RIGHT: (0, 1),
                        }
                        if e.key in move_map:
                            dr, dc = move_map[e.key]
                            self._try_move(dr, dc)
            self.run_one_frame(dt)
            if not self.headless:
                pygame.display.flip()
