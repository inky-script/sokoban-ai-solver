import math
import time

import pygame


C_BG = (28, 24, 36)
C_TITLE = (240, 230, 200)
C_HUD_BG = (38, 32, 48)
C_HUD_TEXT = (195, 188, 175)
C_BTN_BG = (55, 48, 72)
C_BTN_HOVER = (82, 70, 100)
C_BTN_BORDER = (130, 115, 160)
C_BTN_TEXT = (235, 228, 210)
C_AI_ON = (75, 215, 125)
C_AI_OFF = (175, 75, 75)
C_PROGRESS = (90, 180, 110)
C_PROGRESS_BG = (50, 45, 60)


class UIRenderer:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.title_font = pygame.font.SysFont("Segoe UI", 42, bold=True)
        self.body_font = pygame.font.SysFont("Segoe UI", 18, bold=True)
        self.hint_font = pygame.font.SysFont("Segoe UI", 12, bold=True)
        self.hud_font = pygame.font.SysFont("Consolas", 14, bold=True)
        self.btn_font = pygame.font.SysFont("Segoe UI", 19, bold=True)
        self.win_font = pygame.font.SysFont("Segoe UI", 38, bold=True)
        self.prog_font = pygame.font.SysFont("Consolas", 13, bold=True)
        self.sub_font = pygame.font.SysFont("Segoe UI", 15, bold=True)

    def draw_splash(self, surface: pygame.Surface, bg_image: pygame.Surface, anim_tick: int) -> None:
        surface.blit(bg_image, (0, 0))
        
        # Add a subtle vignette or darken
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 40))
        surface.blit(overlay, (0, 0))
        
        # Pulsing prompt
        pulse = int(180 + 75 * math.sin(anim_tick * 0.05))
        prompt_text = "NHẤN PHÍM BẤT KỲ ĐỂ TIẾP TỤC"
        
        # Shadow for text
        sh_surf = self.body_font.render(prompt_text, True, (20, 10, 30))
        sh_rect = sh_surf.get_rect(center=(self.width // 2 + 2, self.height - 100 + 2))
        surface.blit(sh_surf, sh_rect)
        
        ts = self.body_font.render(prompt_text, True, (pulse, pulse, pulse))
        tr = ts.get_rect(center=(self.width // 2, self.height - 100))
        surface.blit(ts, tr)

    def draw_menu(self, surface: pygame.Surface, levels: list[dict], anim_tick: int = 0, bg_image: pygame.Surface | None = None) -> list[tuple[pygame.Rect, int]]:
        if bg_image:
            surface.blit(bg_image, (0, 0))
            # Darker overlay for a more "premium" look
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 130)) 
            surface.blit(overlay, (0, 0))
            
            # Subtle vignette effect
            vignette = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            for i in range(150):
                alpha = int(80 * (i / 150))
                pygame.draw.rect(vignette, (0, 0, 0, alpha), (0, 0, self.width, i)) # Top
                pygame.draw.rect(vignette, (0, 0, 0, alpha), (0, self.height - i, self.width, i)) # Bottom
            surface.blit(vignette, (0, 0))
        else:
            surface.fill(C_BG)
            
        cx = self.width // 2

        ga = int(185 + 50 * math.sin(anim_tick * 0.04))
        ts = self.title_font.render("SOKOBAN", True, C_TITLE)
        tr = ts.get_rect(center=(cx, 80))
        
        # Deeper shadow for the bold title
        sh = self.title_font.render("SOKOBAN", True, (10, 5, 20))
        surface.blit(sh, (tr.x + 4, tr.y + 4))
        
        ts.set_alpha(ga)
        surface.blit(ts, tr)

        sub = self.sub_font.render("- Phiên bản Kenney -", True, (255, 245, 230))
        surface.blit(sub, sub.get_rect(center=(cx, 120)))

        buttons = []
        card_width, card_height = 340, 68
        start_y = 210
        mp = pygame.mouse.get_pos()
        for index, level in enumerate(levels):
            rect = pygame.Rect((self.width - card_width) // 2, start_y + index * 84, card_width, card_height)
            hover = rect.collidepoint(mp)
            bg = C_BTN_HOVER if hover else C_BTN_BG
            pygame.draw.rect(surface, bg, rect, border_radius=14)
            pygame.draw.rect(surface, C_BTN_BORDER, rect, 2, border_radius=14)
            if hover:
                hl = pygame.Surface((card_width - 8, 2), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 40))
                surface.blit(hl, (rect.x + 4, rect.y + 3))
            text = self.body_font.render(level["name"], True, C_BTN_TEXT)
            surface.blit(text, (rect.x + 18, rect.y + 20))
            buttons.append((rect, index))

        ht = self.hint_font.render("Phím mũi tên: Di chuyển  |  Tab: AI  |  Z: Hoàn tác  |  R: Chơi lại  |  Esc: Menu", True, (110, 102, 92))
        surface.blit(ht, ht.get_rect(center=(cx, self.height - 35)))
        return buttons

    def draw_hud(self, surface: pygame.Surface, level_name: str, ai_mode: bool,
                 targets: set, boxes: set, steps: int, best_h, no_improve: int,
                 restart_count: int, undo_count: int, undo_limit: int, elapsed: float, hud_y: int) -> None:
        pygame.draw.rect(surface, C_HUD_BG, (0, hud_y, self.width, self.height - hud_y))
        pygame.draw.line(surface, C_BTN_BORDER, (0, hud_y), (self.width, hud_y), 2)

        ln = self.btn_font.render(level_name, True, C_TITLE)
        surface.blit(ln, (16, hud_y + 8))

        alab = "AI: BẬT" if ai_mode else "AI: TẮT"
        acol = C_AI_ON if ai_mode else C_AI_OFF
        asurf = self.hud_font.render(alab, True, acol)
        arect = pygame.Rect(self.width - 105, hud_y + 6, 88, 22)
        pygame.draw.rect(surface, acol + (25,), arect, border_radius=11)
        pygame.draw.rect(surface, acol, arect, 2, border_radius=11)
        surface.blit(asurf, asurf.get_rect(center=arect.center))

        total_t = len(targets)
        done_t = sum(1 for b in boxes if b in targets)
        bar_x, bar_y, bar_w, bar_h = 16, hud_y + 36, 180, 14
        pygame.draw.rect(surface, C_PROGRESS_BG, (bar_x, bar_y, bar_w, bar_h), border_radius=7)
        if total_t > 0:
            fill_w = int(bar_w * done_t / total_t)
            if fill_w > 0:
                pygame.draw.rect(surface, C_PROGRESS, (bar_x, bar_y, fill_w, bar_h), border_radius=7)
        prog_text = self.prog_font.render(f"{done_t}/{total_t}", True, C_HUD_TEXT)
        surface.blit(prog_text, (bar_x + bar_w + 8, bar_y - 1))

        bh_val = int(best_h) if best_h != float("inf") else "N/A"
        stats = f"Bước: {steps}  |  Best_H: {bh_val}  |  Kẹt: {no_improve}  |  Khởi lại: {restart_count}"
        surface.blit(self.hud_font.render(stats, True, C_HUD_TEXT), (16, hud_y + 56))

        mins, secs = divmod(int(elapsed), 60)
        timer_t = self.hud_font.render(f"{mins:02d}:{secs:02d}", True, C_TITLE)
        surface.blit(timer_t, (self.width - 60, hud_y + 36))

        # Remaining undos display (undo_count now represents the remaining budget)
        rem = undo_count
        undo_col = (200, 180, 100) if rem > 0 else (200, 100, 100)
        undo_t = self.hud_font.render(f"Undo còn lại: {rem}/{undo_limit}", True, undo_col)
        surface.blit(undo_t, (self.width - 165, hud_y + 56))

        ctrl = self.hint_font.render("Mũi tên: Di chuyển  |  Tab: AI  |  Z: Hoàn tác  |  R: Chơi lại  |  Esc: Menu", True, (95, 88, 78))
        surface.blit(ctrl, (16, hud_y + 80))

    def draw_intro(self, surface: pygame.Surface, anim_tick: int, chars_visible: int, bg_image: pygame.Surface | None = None) -> bool:
        if bg_image:
            surface.blit(bg_image, (0, 0))
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 110)) 
            surface.blit(overlay, (0, 0))
        else:
            surface.fill((0, 0, 0))

        cx = self.width // 2
        
        # Draw a central instruction board
        board_w, board_h = 600, 480
        board_rect = pygame.Rect(cx - board_w // 2, (self.height - board_h) // 2 - 20, board_w, board_h)
        board_surf = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
        board_surf.fill((20, 15, 30, 200))
        surface.blit(board_surf, board_rect)
        pygame.draw.rect(surface, (130, 115, 160), board_rect, 2, border_radius=15)
        
        lines = [
            "HƯỚNG DẪN CÁCH CHƠI",
            "",
            "• Sử dụng các PHÍM MŨI TÊN để di chuyển nhân vật.",
            "• Đẩy các THÙNG vào đúng ô MỤC TIÊU.",
            "• Nhấn phím Z để HOÀN TÁC (Undo) nếu đi sai bước.",
            "• Nhấn phím R để CHƠI LẠI (Restart) màn hiện tại.",
            "• Nhấn phím TAB để nhờ AI giải hộ khi gặp khó khăn.",
            "• Phím ESC để quay lại màn hình chọn màn chơi.",
            "",
            "♥♥ Chúc bạn có những giây phút chơi game vui vẻ! ♥♥"
        ]
        
        full_text = "\n".join(lines)
        typed_text = full_text[:chars_visible]
        typed_lines = typed_text.split("\n")
        
        y = board_rect.y + 45
        for i, line in enumerate(typed_lines):
            if not line and i < len(lines) and not lines[i]:
                y += 15
                continue
            
            color = (255, 255, 255)
            font = self.sub_font
            if i == 0:
                color = (255, 215, 100)
                font = self.body_font
            elif i == len(lines) - 1:
                color = (120, 255, 170)
                font = self.body_font
                
            # Draw shadow
            shadow = font.render(line, True, (10, 5, 20))
            surface.blit(shadow, (cx - 260 + 2, y + 2))
            
            ls = font.render(line, True, color)
            surface.blit(ls, (cx - 260, y))
            y += 38

        finished = chars_visible >= len(full_text)
        
        if finished:
            pulse = int(180 + 75 * math.sin(anim_tick * 0.07))
            prompt = self.hint_font.render("NHẤN ENTER ĐỂ TIẾP TỤC", True, (pulse, pulse, pulse))
            surface.blit(prompt, prompt.get_rect(center=(cx, board_rect.bottom - 40)))
        
        skip_hint = self.hint_font.render("Nhấn [K] để bỏ qua hướng dẫn", True, (140, 140, 140))
        surface.blit(skip_hint, (self.width - 200, self.height - 40))
        
        return finished

    def draw_win_overlay(self, surface: pygame.Surface, game_h: int, steps: int, elapsed: float, anim_tick: int) -> None:
        ov = pygame.Surface((self.width, game_h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 110))
        surface.blit(ov, (0, 0))
        pulse = int(220 + 35 * math.sin(anim_tick * 0.1))
        wt = self.win_font.render("HOÀN THÀNH!", True, (255, pulse, 80))
        wy = game_h // 2 - 25
        surface.blit(wt, wt.get_rect(center=(self.width // 2, wy)))
        mins, secs = divmod(int(elapsed), 60)
        st = self.sub_font.render(f"Hoàn thành trong {steps} bước ({mins:02d}:{secs:02d})  -  R: Chơi lại  |  Esc: Menu", True, (195, 188, 175))
        surface.blit(st, st.get_rect(center=(self.width // 2, game_h // 2 + 25)))

    def draw_fail_overlay(self, surface: pygame.Surface, game_h: int,
                          restart_count: int, elapsed: float, anim_tick: int, is_ai: bool = True) -> None:
        ov = pygame.Surface((self.width, game_h), pygame.SRCALPHA)
        # Tím đen (Dark purple/black)
        ov.fill((15, 10, 25, 180))
        surface.blit(ov, (0, 0))

        # Pulsing purple title
        pulse = int(180 + 75 * math.sin(anim_tick * 0.08))
        title_str = "BẠN ĐÃ THUA!"
        title = self.win_font.render(title_str, True, (pulse, 120, 255))
        ty = game_h // 2 - 55
        # Shadow
        shadow = self.win_font.render(title_str, True, (40, 20, 60))
        surface.blit(shadow, shadow.get_rect(center=(self.width // 2 + 3, ty + 3)))
        surface.blit(title, title.get_rect(center=(self.width // 2, ty)))

        # Reason
        if is_ai:
            reason_txt = f"AI bị kẹt sau {restart_count} lần khởi động lại"
        else:
            reason_txt = "Bạn đã bị kẹt (Deadlock)!"
        
        reason = self.sub_font.render(reason_txt, True, (190, 170, 210))
        surface.blit(reason, reason.get_rect(center=(self.width // 2, game_h // 2)))

        # Elapsed time
        mins, secs = divmod(int(elapsed), 60)
        time_txt = self.sub_font.render(
            f"Thời gian: {mins:02d}:{secs:02d}",
            True, (160, 150, 180),
        )
        surface.blit(time_txt, time_txt.get_rect(center=(self.width // 2, game_h // 2 + 30)))

        # Action hints
        if is_ai:
            hint_txt = "R: Thử lại  |  Tab: Đổi AI  |  Esc: Menu"
        else:
            hint_txt = "Z: Hoàn tác  |  R: Chơi lại  |  Esc: Menu"
            
        hint = self.sub_font.render(hint_txt, True, (140, 130, 160))
        surface.blit(hint, hint.get_rect(center=(self.width // 2, game_h // 2 + 68)))

        # Animated subtle purple vignette border
        border_alpha = int(50 + 25 * math.sin(anim_tick * 0.06))
        border_surf = pygame.Surface((self.width, game_h), pygame.SRCALPHA)
        for y_off in range(12):
            a = border_alpha * (12 - y_off) // 12
            pygame.draw.line(border_surf, (110, 50, 180, a), (0, y_off), (self.width, y_off))
            pygame.draw.line(border_surf, (110, 50, 180, a), (0, game_h - 1 - y_off), (self.width, game_h - 1 - y_off))
        surface.blit(border_surf, (0, 0))

    def draw_ai_modal(self, surface: pygame.Surface, solvers: list, anim_tick: int = 0) -> list[tuple[pygame.Rect, int]]:
        """Draw AI algorithm selection modal. Returns list of (rect, solver_index) buttons."""
        ov = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        surface.blit(ov, (0, 0))

        modal_w, modal_h = 420, 60 + len(solvers) * 90 + 40
        mx = (self.width - modal_w) // 2
        my = (self.height - modal_h) // 2

        modal_bg = pygame.Surface((modal_w, modal_h), pygame.SRCALPHA)
        modal_bg.fill((38, 32, 50, 240))
        surface.blit(modal_bg, (mx, my))
        pygame.draw.rect(surface, C_BTN_BORDER, (mx, my, modal_w, modal_h), 2, border_radius=16)

        pulse = int(230 + 25 * math.sin(anim_tick * 0.06))
        title = self.btn_font.render("Chọn thuật toán AI", True, (pulse, pulse - 10, pulse - 40))
        surface.blit(title, title.get_rect(center=(self.width // 2, my + 30)))

        buttons = []
        mp = pygame.mouse.get_pos()
        for i, solver_cls in enumerate(solvers):
            by = my + 60 + i * 90
            rect = pygame.Rect(mx + 20, by, modal_w - 40, 76)
            hover = rect.collidepoint(mp)
            bg = C_BTN_HOVER if hover else C_BTN_BG
            pygame.draw.rect(surface, bg, rect, border_radius=12)
            border_col = (180, 160, 220) if hover else C_BTN_BORDER
            pygame.draw.rect(surface, border_col, rect, 2, border_radius=12)
            if hover:
                hl = pygame.Surface((rect.width - 8, 2), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 50))
                surface.blit(hl, (rect.x + 4, rect.y + 3))

            label = self.body_font.render(solver_cls.LABEL, True, C_BTN_TEXT)
            surface.blit(label, (rect.x + 16, rect.y + 12))

            desc = self.hint_font.render(solver_cls.DESC, True, (150, 142, 130))
            surface.blit(desc, (rect.x + 16, rect.y + 40))

            idx_tag = self.prog_font.render(f"[{i+1}]", True, (120, 110, 140))
            surface.blit(idx_tag, (rect.x + rect.width - 36, rect.y + 14))

            buttons.append((rect, i))

        hint = self.hint_font.render("Nhấn 1-3 hoặc click để chọn  |  Esc: Đóng", True, (95, 88, 78))
        surface.blit(hint, hint.get_rect(center=(self.width // 2, my + modal_h - 18)))

        return buttons
