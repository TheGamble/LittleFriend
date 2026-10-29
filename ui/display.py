# ui/display.py
import time
import os
import config
from hardware.display_power import DisplayPower
import pygame

# Visual Theme
COLOR_BG = (18, 20, 26)
COLOR_SURFACE = (28, 32, 42)
COLOR_PRIMARY = (235, 140, 52)  # Amber
COLOR_ACCENT = (80, 200, 120)  # Green
COLOR_TEXT = (240, 240, 245)
COLOR_TEXT_DIM = (140, 145, 160)
COLOR_BAR_BG = (45, 50, 62)

# Safe Inset Margins to accommodate TV bezel/vignette
MARGIN_X = 24
MARGIN_Y = 20

MODE_PLAYING = "PLAYING"
MODE_HUD = "HUD"
MODE_BROWSE = "BROWSE"
MODE_SLEEP = "SLEEP"


class TouchUI:

    def __init__(self, player, state, library):
        self.player = player
        self.state = state
        self.library = library
        self.hud_bg = None

        pygame.init()
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        pygame.font.init()

        self.font_large = pygame.font.SysFont(None, 32)
        self.font_med = pygame.font.SysFont(None, 24)
        self.font_small = pygame.font.SysFont(None, 18)

        if config.IS_PI:
            self.screen = pygame.display.set_mode(
                (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN
            )
            pygame.mouse.set_visible(False)
        else:
            self.screen = pygame.display.set_mode(
                (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
            )
            pygame.display.set_caption("LittleFriend Simulator (640x480)")

        wm_info = pygame.display.get_wm_info()
        self.window_id = wm_info.get("window")
        self.player.set_window(self.window_id)

        self.mode = MODE_PLAYING
        self.is_sleeping = False
        self.hud_timer = 0
        self.volume_osd_timer = 0
        self.current_volume = 70
        self.last_progress_save = 0

        # Touch tracking
        self.touch_start_pos = None
        self.touch_start_time = 0

        # Menu pointers
        self.browse_show = None
        self.browse_season = 1
        self.browse_scroll_y = 0

    def start_playback(self):
        if not self.library.catalog:
            return

        active_show = self.state.data.get("active_show")
        if not active_show or active_show not in self.library.catalog:
            active_show = list(self.library.catalog.keys())[0]

        season, ep_file, pos_ms = self.state.get_last_position(active_show)
        self.play_show_episode(active_show, season or 1, ep_file, pos_ms)

    def play_show_episode(
        self, show_name, season_num, ep_identifier=None, start_ms=0
    ):
        seasons = self.library.catalog.get(show_name, {})
        episodes = seasons.get(season_num, [])

        if not episodes:
            if seasons:
                season_num = list(seasons.keys())[0]
                episodes = seasons[season_num]
            else:
                return

        target_ep = episodes[0]
        if ep_identifier:
            for ep in episodes:
                if ep_identifier in (ep.title, ep.path):
                    target_ep = ep
                    break

        self.browse_show = show_name
        self.browse_season = season_num
        self.state.update_progress(
            show_name, season_num, target_ep.title, start_ms
        )

        self.screen.fill((0, 0, 0))
        pygame.display.flip()

        self.player.load_media(target_ep.path, start_ms)
        self.mode = MODE_PLAYING

    def resume_current(self):
        """Resumes playback at the exact scrubbed timestamp."""
        show = self.state.data.get("active_show")
        season, ep_file, _ = self.state.get_last_position(show)
        # Use the scrubbed timestamp from the player
        pos_ms = max(0, self.player.last_known_time)
        self.play_show_episode(show, season or 1, ep_file, pos_ms)

    def open_hud(self):
        """Single tap: Grabs current frame with letterboxing, dims it, and displays HUD."""
        snap_path = "/tmp/lf_snap.png"

        self.player.take_snapshot(snap_path)

        self.state.update_progress(
            self.state.data.get("active_show"),
            self.browse_season,
            self.player.current_path,
            self.player.get_time(),
        )

        time.sleep(0.04)
        self.player.stop()

        # Load native snapshot and scale with proper letterbox aspect ratio
        self.hud_bg = None
        if os.path.exists(snap_path):
            try:
                raw_img = pygame.image.load(snap_path).convert()
                img_w, img_h = raw_img.get_size()

                if img_w > 0 and img_h > 0:
                    # Calculate scale factor to preserve native aspect ratio
                    scale = min(
                        config.SCREEN_WIDTH / img_w, config.SCREEN_HEIGHT / img_h
                    )
                    new_w = int(img_w * scale)
                    new_h = int(img_h * scale)
                    scaled_img = pygame.transform.smoothscale(
                        raw_img, (new_w, new_h)
                    )

                    # Center onto a 640x480 canvas (matches VLC letterboxing exactly)
                    frame_img = pygame.Surface(
                        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
                    )
                    frame_img.fill((0, 0, 0))
                    x_off = (config.SCREEN_WIDTH - new_w) // 2
                    y_off = (config.SCREEN_HEIGHT - new_h) // 2
                    frame_img.blit(scaled_img, (x_off, y_off))

                    # Apply dark cinematic dimming overlay
                    dim_layer = pygame.Surface(
                        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT),
                        pygame.SRCALPHA,
                    )
                    dim_layer.fill((10, 12, 16, 130))
                    frame_img.blit(dim_layer, (0, 0))

                    self.hud_bg = frame_img
            except Exception as e:
                print(f"[UI] Snapshot load failed: {e}")

        self.mode = MODE_HUD
        self.hud_timer = time.time() + 5.0

    def open_browser(self):
        """Second tap: Opens the full season/episode drawer."""
        self.mode = MODE_BROWSE

    def channel_surf(self, direction=1):
        shows = list(self.library.catalog.keys())
        if not shows:
            return
        curr_show = self.state.data.get("active_show")
        if curr_show not in shows:
            curr_show = shows[0]

        idx = (shows.index(curr_show) + direction) % len(shows)
        new_show = shows[idx]
        season, ep_file, pos_ms = self.state.get_last_position(new_show)
        self.play_show_episode(new_show, season or 1, ep_file, pos_ms)

    def toggle_sleep(self):
        self.is_sleeping = not self.is_sleeping
        if self.is_sleeping:
            self.state.update_progress(
                self.state.data.get("active_show"),
                self.browse_season,
                self.player.current_path,
                self.player.get_time(),
            )
            self.player.stop()
            self.mode = MODE_SLEEP
            self.screen.fill((0, 0, 0))
            pygame.display.flip()
            DisplayPower.set_backlight(False)
        else:
            DisplayPower.set_backlight(True)
            self.resume_current()

    def adjust_volume(self, volume_val):
        self.current_volume = volume_val
        self.player.set_volume(volume_val)
        self.volume_osd_timer = time.time() + 2.0

    def show_shutdown_screen(self):
        self.player.stop()
        self.mode = MODE_SLEEP
        self.screen.fill((10, 12, 16))
        msg = self.font_large.render("Goodnight...", True, COLOR_PRIMARY)
        self.screen.blit(
            msg,
            msg.get_rect(
                center=(
                    config.SCREEN_WIDTH // 2,
                    config.SCREEN_HEIGHT // 2 - 15,
                )
            ),
        )
        pygame.display.flip()
        time.sleep(1.5)

    # --- Touch Handling ---

    def handle_touch_down(self, pos):
        self.touch_start_pos = pos
        self.touch_start_time = time.time()

    def handle_touch_up(self, pos):
        if not self.touch_start_pos:
            return

        dx = pos[0] - self.touch_start_pos[0]
        dy = pos[1] - self.touch_start_pos[1]
        dist_sq = dx * dx + dy * dy
        elapsed = time.time() - self.touch_start_time

        # Fast swipe gesture
        if dist_sq > 2500 and elapsed < 0.4:
            if abs(dx) > abs(dy):
                if dx > 0:
                    self.player.seek_relative(config.SEEK_FORWARD_SECS)
                else:
                    self.player.seek_relative(-config.SEEK_BACKWARD_SECS)
            else:
                if dy > 0:
                    self.channel_surf(-1)
                else:
                    self.channel_surf(1)
        else:
            # Single Tap routing
            if self.mode == MODE_PLAYING:
                self.open_hud()
            elif self.mode == MODE_HUD:
                self.handle_hud_tap(pos)
            elif self.mode == MODE_BROWSE:
                self.handle_browse_tap(pos)

        self.touch_start_pos = None

    def handle_hud_tap(self, pos):
        x, y = pos
        self.hud_timer = time.time() + 5.0  # Reset auto-hide

        # Timeline Scrubber Tap (y: 330 to 355, x: 40 to 600)
        if 330 <= y <= 355 and 40 <= x <= 600:
            pct = (x - 40) / 560.0
            total = self.player.get_length()
            if total > 0:
                self.player.last_known_time = int(total * pct)
                self.player.player.set_time(self.player.last_known_time)
            return

        # HUD Button Row (y: 365 to 435)
        if 365 <= y <= 435:
            if 35 <= x <= 110:  # [ < 15s ]
                self.player.last_known_time = max(
                    0, self.player.last_known_time - 15000
                )
            elif 115 <= x <= 205:  # [ Resume > ]
                self.resume_current()
            elif 210 <= x <= 285:  # [ 30s > ]
                self.player.last_known_time += 30000
            elif 290 <= x <= 360:  # [ Skip ]
                self.player.last_known_time += config.INTRO_SKIP_SECS * 1000
            elif 365 <= x <= 435:  # [ Ch - ]
                self.channel_surf(-1)
            elif 440 <= x <= 510:  # [ Ch + ]
                self.channel_surf(1)
            elif 515 <= x <= 605:  # [ Browse ]
                self.open_browser()
        else:
            # Tap outside HUD card -> Resume
            self.resume_current()

    def handle_browse_tap(self, pos):
        x, y = pos

        # Top Bar (y: MARGIN_Y to MARGIN_Y + 50)
        if MARGIN_Y <= y <= MARGIN_Y + 50:
            if MARGIN_X <= x <= MARGIN_X + 160:  # [ Ch: Name > ]
                self.channel_surf(1)
            elif 640 - MARGIN_X - 100 <= x <= 640 - MARGIN_X:  # [ Close X ]
                self.resume_current()
            return

        # Left Season Selector (x: MARGIN_X to MARGIN_X + 90)
        if MARGIN_X <= x <= MARGIN_X + 90 and y >= MARGIN_Y + 60:
            seasons = sorted(
                self.library.catalog.get(self.browse_show, {}).keys()
            )
            btn_h = 55
            for i, s_num in enumerate(seasons[:6]):
                by = MARGIN_Y + 60 + (i * (btn_h + 8))
                if by <= y <= by + btn_h:
                    self.browse_season = s_num
                    self.browse_scroll_y = 0
            return

        # Right Episode Selector
        if x > MARGIN_X + 100 and y >= MARGIN_Y + 60:
            episodes = self.library.catalog.get(self.browse_show, {}).get(
                self.browse_season, []
            )
            item_h = 58
            start_y = MARGIN_Y + 60 + self.browse_scroll_y
            for i, ep in enumerate(episodes):
                ey = start_y + (i * (item_h + 6))
                if ey <= y <= ey + item_h:
                    self.play_show_episode(
                        self.browse_show, self.browse_season, ep.title, 0
                    )
                    return

    # --- Renderers ---

    def draw(self):
        if self.mode == MODE_SLEEP:
            return

        if not self.library.catalog:
            self.screen.fill(COLOR_BG)
            msg1 = self.font_large.render(
                "No Videos Found", True, COLOR_PRIMARY
            )
            self.screen.blit(
                msg1, msg1.get_rect(center=(config.SCREEN_WIDTH // 2, 200))
            )
            pygame.display.flip()
            return

        if self.mode == MODE_PLAYING:
            if time.time() < self.volume_osd_timer:
                self.draw_volume_osd()
                pygame.display.flip()

        elif self.mode == MODE_HUD:
            self.draw_hud()
            pygame.display.flip()

        elif self.mode == MODE_BROWSE:
            self.draw_browse()
            pygame.display.flip()

    def draw_hud(self):
        """Tier 1: Compact media bar overlaid on the dimmed video freeze-frame."""
        if time.time() > self.hud_timer:
            self.resume_current()
            return

        # Render the frozen video frame as background (fallback to dark slate if missing)
        hud_bg = getattr(self, "hud_bg", None)
        if hud_bg is not None:
            self.screen.blit(hud_bg, (0, 0))
        else:
            self.screen.fill(COLOR_BG)

        # Inset Floating Card (keeps well clear of TV bezel)
        card_rect = pygame.Rect(MARGIN_X, 290, 640 - (2 * MARGIN_X), 150)
        pygame.draw.rect(
            self.screen, COLOR_SURFACE, card_rect, border_radius=12
        )

        # Title & Time Info
        curr_t = self.player.last_known_time // 1000
        total_t = self.player.get_length() // 1000
        time_str = f"{curr_t // 60:02d}:{curr_t % 60:02d} / {total_t // 60:02d}:{total_t % 60:02d}"

        show_name = self.state.data.get("active_show", "LittleFriend")
        title_txt = self.font_med.render(
            f"{show_name[:18]}  •  {time_str}", True, COLOR_TEXT
        )
        self.screen.blit(title_txt, (MARGIN_X + 16, 305))

        # Scrubber Bar
        bar_x, bar_y, bar_w, bar_h = (
            MARGIN_X + 16,
            335,
            card_rect.width - 32,
            8,
        )
        pygame.draw.rect(
            self.screen,
            COLOR_BAR_BG,
            (bar_x, bar_y, bar_w, bar_h),
            border_radius=4,
        )
        if total_t > 0:
            fill_w = int(bar_w * (curr_t / total_t))
            pygame.draw.rect(
                self.screen,
                COLOR_PRIMARY,
                (bar_x, bar_y, fill_w, bar_h),
                border_radius=4,
            )

        # Button Row (All ASCII labels, no tofu boxes)
        btns = [
            ("< 15s", (MARGIN_X + 12, 360, 75, 60)),
            ("Resume >", (MARGIN_X + 92, 360, 92, 60)),
            ("30s >", (MARGIN_X + 189, 360, 75, 60)),
            ("Skip", (MARGIN_X + 269, 360, 70, 60)),
            ("Ch -", (MARGIN_X + 344, 360, 68, 60)),
            ("Ch +", (MARGIN_X + 417, 360, 68, 60)),
            ("Browse", (MARGIN_X + 490, 360, 90, 60)),
        ]
        for label, (bx, by, bw, bh) in btns:
            is_pri = label.startswith("Resume")
            bg = COLOR_PRIMARY if is_pri else COLOR_BAR_BG
            fg = COLOR_BG if is_pri else COLOR_TEXT
            pygame.draw.rect(self.screen, bg, (bx, by, bw, bh), border_radius=8)
            txt = self.font_med.render(label, True, fg)
            self.screen.blit(
                txt, txt.get_rect(center=(bx + bw // 2, by + bh // 2))
            )

    def draw_browse(self):
        """Tier 2: Full Season & Episode catalog browser."""
        self.screen.fill(COLOR_BG)

        # Header Bar (Safely inset from bezel)
        head_rect = pygame.Rect(
            MARGIN_X, MARGIN_Y, 640 - (2 * MARGIN_X), 50
        )
        pygame.draw.rect(
            self.screen, COLOR_SURFACE, head_rect, border_radius=8
        )

        show_name = self.browse_show or "Show"
        show_btn = self.font_med.render(
            f"Ch: {show_name[:12]} >", True, COLOR_PRIMARY
        )
        self.screen.blit(show_btn, (MARGIN_X + 16, MARGIN_Y + 16))

        close_btn = self.font_med.render("Close X", True, COLOR_TEXT_DIM)
        self.screen.blit(close_btn, (head_rect.right - 80, MARGIN_Y + 16))

        # Left Season Selector (Safely inset)
        seasons = sorted(self.library.catalog.get(self.browse_show, {}).keys())
        btn_h = 52
        for i, s_num in enumerate(seasons[:6]):
            by = MARGIN_Y + 60 + (i * (btn_h + 8))
            is_active = s_num == self.browse_season
            bg_col = COLOR_PRIMARY if is_active else COLOR_SURFACE
            txt_col = COLOR_BG if is_active else COLOR_TEXT
            pygame.draw.rect(
                self.screen, bg_col, (MARGIN_X, by, 85, btn_h), border_radius=8
            )
            stxt = self.font_med.render(f"S {s_num}", True, txt_col)
            self.screen.blit(
                stxt, stxt.get_rect(center=(MARGIN_X + 85 // 2, by + btn_h // 2))
            )

        # Right Episode Selector (Safely inset from right edge)
        episodes = self.library.catalog.get(self.browse_show, {}).get(
            self.browse_season, []
        )
        item_h = 56
        ep_x = MARGIN_X + 95
        ep_w = 640 - MARGIN_X - ep_x
        start_y = MARGIN_Y + 60 + self.browse_scroll_y

        for i, ep in enumerate(episodes):
            ey = start_y + (i * (item_h + 6))
            if ey > config.SCREEN_HEIGHT - MARGIN_Y or ey + item_h < MARGIN_Y + 60:
                continue
            pygame.draw.rect(
                self.screen, COLOR_SURFACE, (ep_x, ey, ep_w, item_h), border_radius=8
            )
            ep_txt = self.font_med.render(ep.title[:34], True, COLOR_TEXT)
            self.screen.blit(ep_txt, (ep_x + 14, ey + 18))

    def draw_volume_osd(self):
        vol_box = pygame.Rect(
            640 - MARGIN_X - 160, MARGIN_Y, 160, 36
        )
        pygame.draw.rect(self.screen, (0, 0, 0), vol_box, border_radius=4)
        pygame.draw.rect(
            self.screen, COLOR_ACCENT, vol_box, width=2, border_radius=4
        )

        total_blocks = 10
        active_blocks = int(round((self.current_volume / 100.0) * total_blocks))
        for i in range(total_blocks):
            bx = (640 - MARGIN_X - 150) + (i * 14)
            color = COLOR_ACCENT if i < active_blocks else (30, 60, 40)
            pygame.draw.rect(self.screen, color, (bx, MARGIN_Y + 6, 10, 24))

    # --- Main Loop ---

    def run(self):
        clock = pygame.time.Clock()
        running = True

        while running:
            now = time.time()

            # Heartbeat save: every 5 seconds
            if now - self.last_progress_save >= config.AUTO_SAVE_INTERVAL_SECS:
                self.last_progress_save = now
                if self.mode == MODE_PLAYING and self.player.is_playing():
                    curr_ms = self.player.get_time()
                    active_show = self.state.data.get("active_show")
                    if active_show:
                        self.state.update_progress(
                            active_show,
                            self.browse_season,
                            self.player.current_path,
                            curr_ms,
                        )

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_touch_down(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.handle_touch_up(event.pos)

                elif not config.IS_PI and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.toggle_sleep()
                    elif event.key == pygame.K_UP:
                        self.adjust_volume(min(100, self.current_volume + 5))
                    elif event.key == pygame.K_DOWN:
                        self.adjust_volume(max(0, self.current_volume - 5))
                    elif event.key == pygame.K_m:
                        if self.mode == MODE_PLAYING:
                            self.open_hud()
                        elif self.mode == MODE_HUD:
                            self.open_browser()
                        else:
                            self.resume_current()
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            self.draw()
            clock.tick(config.FPS)

        pygame.quit()