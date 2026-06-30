"""Entry point for AI Dungeon Adventure."""

import random
from typing import Optional, Any, cast

import pygame

from assets.sprite_manager import get_named_icon

from game.combat import Combat
from game.boss import BossEnemy
from game.enemy import Enemy, EnemyAStar, EnemyGreedy
from game.item import HealthPotion, Item, Spirit, Sword, Torch, create_item_from_placement
from game.player import Player
from game.trap import create_trap_from_placement
from maps.dungeon import Dungeon, WALL, FLOOR
from ai.ucs import ucs
from ai.bfs import bfs
from ai.forward_checking import ForwardCheckingGateSolver
from maps.boss_arena import BossArena
from maps.fog_of_war import FogOfWar
from systems.laboratory_system import LaboratoryRoom
from systems.puzzle_system import (
    PuzzleRoom,
    PuzzleRoomBacktracking,
    PuzzleRoomMinConflicts,
)
from ui.hud import HUD
from assets.font_cache import FontCache


class Camera:
    """Follows the player and clamps to dungeon bounds."""

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        world_width: int,
        world_height: int,
    ) -> None:
        """Initialize camera limits for the dungeon world size."""
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._world_width = world_width
        self._world_height = world_height
        self.x = 0
        self.y = 0

    def update(self, target: Any, tile_size: int) -> None:
        """Center the camera on the target while clamping to map bounds."""
        target_pixel_x = target.x * tile_size + tile_size // 2
        target_pixel_y = target.y * tile_size + tile_size // 2

        target_x = target_pixel_x - self._screen_width // 2
        target_y = target_pixel_y - self._screen_height // 2

        max_x = max(0, self._world_width - self._screen_width)
        max_y = max(0, self._world_height - self._screen_height)

        self.x = max(0, min(target_x, max_x))
        self.y = max(0, min(target_y, max_y))


class DummyKeys:
    """Mock pygame keys sequence that always returns False for any key."""
    def __getitem__(self, key: int) -> bool:
        return False


class CameraAnchor:
    """A dummy camera anchor with x and y coordinates."""

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y




class GameApplication:
    """Manages the Pygame application lifecycle."""

    WINDOW_WIDTH: int = 1280
    WINDOW_HEIGHT: int = 720
    BACKGROUND_COLOR: tuple[int, int, int] = (0, 0, 0)
    KEY_TARGET_COUNT: int = 4
    ENEMY_MIN_SPAWN_DISTANCE: int = 15
    DAMAGE_FOG_DURATION: float = 0.45
    MINIMAP_WIDTH: int = 200
    MINIMAP_HEIGHT: int = 125
    MINIMAP_MARGIN: int = 16
    MINIMAP_BACKGROUND_COLOR: tuple[int, int, int] = (13, 12, 18)
    MINIMAP_BORDER_COLOR: tuple[int, int, int] = (120, 95, 86)
    MINIMAP_SPAWN_COLOR: tuple[int, int, int] = (220, 214, 184)
    MINIMAP_LAB_COLOR: tuple[int, int, int] = (65, 150, 150)
    MINIMAP_ROUTE_COLOR: tuple[int, int, int] = (143, 105, 58)
    
    # Đồng bộ chính xác với bảng màu của maps/dungeon.py để tránh xung đột hình ảnh
    WALL_COLOR: tuple[int, int, int] = (24, 30, 48)
    FLOOR_COLOR: tuple[int, int, int] = (14, 13, 19)
    KEY_ROOM_COLOR: tuple[int, int, int] = (66, 48, 72)
    LABORATORY_FLOOR_COLOR: tuple[int, int, int] = (27, 72, 76)
    BOSS_ROOM_COLOR: tuple[int, int, int] = (48, 28, 56)
    PUZZLE_BACKTRACKING_COLOR: tuple[int, int, int] = (96, 67, 82)
    PUZZLE_MIN_CONFLICTS_COLOR: tuple[int, int, int] = (83, 64, 49)
    MINIMAP_BOSS_COLOR: tuple[int, int, int] = (86, 42, 88)

    LOCKED_COLOR: tuple[int, int, int] = (97, 23, 36)
    UNLOCKED_COLOR: tuple[int, int, int] = (47, 103, 70)

    def __init__(self) -> None:
        """Initialize the game application."""
        pygame.init()
        self._screen = pygame.display.set_mode(
            (self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        )
        pygame.display.set_caption("AI Dungeon Adventure")
        self._clock = pygame.time.Clock()
        self._hud = HUD()

        # State machine settings
        self._state = "MODE_SELECT"
        self._game_mode = "LOW" # "LOW" or "MEDIUM"
        self._menu_selected_idx = 0 # 0 for LOW, 1 for MEDIUM

        self._boss_alert_spawned = False
        self._in_boss_arena = False
        self._boss_arena: Optional[BossArena] = None
        self._saved_state = None
        self._spirit_path_has_key = False
        self._death_animations: list[dict] = []
        self._path_camera_step_time = 0.18
        self._enemy_growth_interval: float = 90.0
        self._damage_fog_timer: float = 0.0

        # Transition variables
        self._transition_active = False
        self._transition_timer = 0.0
        self._transition_duration = 2.5

        # Preload named icons and report missing core sprites.
        try:
            from assets.sprite_manager import load_icons
            load_icons()
        except Exception:
            print("Warning: unable to preload sprite icons.")

        self._running = True

    def _world_pixel_size(self) -> tuple[int, int]:
        """Return the full dungeon size in pixels."""
        width = self._dungeon.GRID_WIDTH * self._dungeon.TILE_SIZE
        height = self._dungeon.GRID_HEIGHT * self._dungeon.TILE_SIZE
        return width, height

    def run(self) -> None:
        """Start the main game loop."""
        while self._running:
            dt = self._clock.tick(60) / 1000.0
            self._handle_events()
            
            if self._state == "MODE_SELECT":
                self._render_mode_select()
                continue
                
            if self._state == "VICTORY":
                self._render_victory_screen()
                continue

            # Update transition scene
            if self._transition_active:
                self._transition_timer -= dt
                if self._transition_timer <= 0.0:
                    self._transition_active = False
                    self._enter_boss_arena()
            
            self._update_spirit_path(dt)
            self._update_path_camera(dt)
            self._update_defeat_marks(dt)
            
            if self._player.is_alive and not self._inventory_open and not self._transition_active:
                if self._in_boss_arena:
                    self._boss_battle.update()
                    self._update_boss_round_pause(dt)
                else:
                    if not self._path_camera_active:
                        self._player.update(pygame.key.get_pressed(), self._dungeon, dt)
                    else:
                        self._player.update(cast(Any, DummyKeys()), self._dungeon, dt)
                    # Record visited tiles after movement.
                    self._visited_tiles.add(self._player.grid_position())
                    self._handle_traps()
                    self._update_enemy_growth(dt)
                    
                    # Auto-trigger backtracking gate solver if adjacent with 4 keys
                    gate_positions = self._dungeon.get_gate_positions()
                    player_pos = self._player.grid_position()
                    adjacent_gate = any(
                        abs(player_pos[0] - gx) + abs(player_pos[1] - gy) == 1
                        for gx, gy in gate_positions
                    )
                    has_all_keys = self._player.keys >= 4 or sum(self._player.inventory.count(k) for k in ("Key 1", "Key 2", "Key 3", "Key 4")) >= 4
                    guards_defeated = not self._boss_gate_guards_alive()
                    if has_all_keys and adjacent_gate and self._dungeon.gate.locked and not self._gate_unlock_active and guards_defeated:
                        self._gate_unlock_active = True
                        self._gate_timer = 0.0
                        self._gate_solver.start_solving()
                        self._gate_message = "Ready. Standing still..."
                        print("[AUTO-SOLVE] Adjacent to gate with all keys. Automatically starting gate solver...")
                    elif has_all_keys and adjacent_gate and self._dungeon.gate.locked and not guards_defeated:
                        self._gate_message = "Defeat the boss gate guards first!"

                    # Backtracking Lock-Picking Logic
                    if self._gate_unlock_active:
                        # Check movement input interruption
                        keys_state = pygame.key.get_pressed()
                        movement_pressed = (
                            keys_state[pygame.K_w] or keys_state[pygame.K_s] or
                            keys_state[pygame.K_a] or keys_state[pygame.K_d] or
                            keys_state[pygame.K_UP] or keys_state[pygame.K_DOWN] or
                            keys_state[pygame.K_LEFT] or keys_state[pygame.K_RIGHT]
                        )
                        
                        # Check damage interruption
                        if self._player.hp < self._last_player_hp:
                            self._gate_unlock_active = False
                            self._gate_solver.interrupt()
                            self._gate_message = "Interrupted by damage!"
                        elif movement_pressed:
                            self._gate_unlock_active = False
                            self._gate_solver.interrupt()
                            self._gate_message = "Interrupted: movement key pressed!"
                        else:
                            # Check distance interruption
                            gate_positions = self._dungeon.get_gate_positions()
                            player_pos = self._player.grid_position()
                            adjacent_gate = any(
                                abs(player_pos[0] - gx) + abs(player_pos[1] - gy) == 1
                                for gx, gy in gate_positions
                            )
                            if not adjacent_gate:
                                self._gate_unlock_active = False
                                self._gate_solver.interrupt()
                                self._gate_message = "Interrupted: moved too far!"
                            else:
                                # Run backtracking solver steps slowly to let the player see how it solves (0.75s step rate)
                                self._gate_timer += dt
                                if self._gate_timer >= 0.75:
                                    self._gate_timer = 0.0
                                    is_finished, msg = self._gate_solver.step()
                                    self._gate_message = msg
                                    if is_finished:
                                        self._gate_unlock_active = False
                                        if self._gate_solver.is_solved:
                                            self._dungeon.gate.locked = False
                                            # Consume keys
                                            for key_type in ("Key 1", "Key 2", "Key 3", "Key 4"):
                                                self._player.inventory.remove(key_type, 1)
                                            self._player.keys = 0
                                            # Trigger transition
                                            self._transition_active = True
                                            self._transition_timer = self._transition_duration
                    
                    for enemy in self._enemies:
                        if not enemy.is_alive:
                            continue
                        enemy.update(
                            self._player,
                            self._dungeon,
                            dt,
                            self._blocked_positions_for(enemy),
                        )
                        # If player approaches the boss area, spawn an alert wave of enemies once.
                        boss_center = self._dungeon.get_boss_room_center()
                        distance_to_boss = abs(self._player.x - boss_center[0]) + abs(self._player.y - boss_center[1])
                        if distance_to_boss <= 8 and not self._boss_alert_spawned:
                            self._spawn_boss_alert()
                            self._boss_alert_spawned = True
                    self._remove_defeated_enemies()
                    
                    # If player stepped into the boss entrance and the gate is unlocked,
                    # teleport into the boss arena (handled by transition scene now, but fallback remains)
                    if self._dungeon.is_boss_room_tile(*self._player.grid_position()) and not self._dungeon.gate.locked:
                        self._enter_boss_arena()
                        
            if self._player.hp < self._last_player_hp:
                self._damage_fog_timer = self.DAMAGE_FOG_DURATION

            if self._damage_fog_timer > 0.0:
                self._damage_fog_timer = max(0.0, self._damage_fog_timer - dt)

            # Keep track of player's last HP for damage checks
            self._last_player_hp = self._player.hp
            
            if not self._in_boss_arena:
                self._fog.update(
                    self._player,
                    self._dungeon,
                    boss_visible=self._is_boss_area_visible(),
                )
            camera_target = self._path_camera_anchor if self._path_camera_active else self._player
            self._camera.update(camera_target, self._dungeon.TILE_SIZE)
            self._render_frame()
            pygame.display.flip()

        pygame.quit()

    def _render_victory_screen(self) -> None:
        """Draw a beautiful victory screen with victory image and interactive buttons."""
        self._screen.fill((10, 20, 15)) # Dark emerald gothic
        
        # Load victory image on demand and cache it
        if not hasattr(self, "_victory_image"):
            import os
            sprites_dir = os.path.join(os.path.dirname(__file__), "assets", "sprites")
            path = None
            for filename in ("victory.png", "victory.jpg"):
                candidate = os.path.join(sprites_dir, filename)
                if os.path.exists(candidate):
                    path = candidate
                    break

            if path is not None:
                try:
                    self._victory_image = pygame.image.load(path).convert()
                except Exception:
                    self._victory_image = None
            else:
                self._victory_image = None

        if self._victory_image:
            scaled_img = pygame.transform.smoothscale(
                self._victory_image,
                (self.WINDOW_WIDTH, self.WINDOW_HEIGHT),
            )
            self._screen.blit(scaled_img, (0, 0))
            contrast = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
            contrast.fill((0, 0, 0, 80))
            self._screen.blit(contrast, (0, 0))

        font_title = FontCache.get(36)
        font_body = FontCache.get(22)
        font_btn = FontCache.get(18)
        
        title_surf = font_title.render("VICTORY ACHIEVED!", True, (220, 180, 50))
        title_rect = title_surf.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 + 50))
        self._screen.blit(title_surf, title_rect)
        
        subtitle_surf = font_body.render("You have vanquished the dungeon boss in Gomoku!", True, (200, 220, 200))
        subtitle_rect = subtitle_surf.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 + 95))
        self._screen.blit(subtitle_surf, subtitle_rect)

        # Mouse hover coordinates
        mx, my = pygame.mouse.get_pos()
        
        # Button coordinates and sizes
        rx = self.WINDOW_WIDTH // 2 - 110
        ex = self.WINDOW_WIDTH // 2 + 110
        by = self.WINDOW_HEIGHT // 2 + 160
        bw, bh = 180, 42
        
        r_hover = (rx - bw // 2 <= mx <= rx + bw // 2) and (by - bh // 2 <= my <= by + bh // 2)
        e_hover = (ex - bw // 2 <= mx <= ex + bw // 2) and (by - bh // 2 <= my <= by + bh // 2)
        
        # Draw Restart Button
        r_rect = pygame.Rect(rx - bw // 2, by - bh // 2, bw, bh)
        r_color = (40, 140, 70) if r_hover else (25, 45, 30)
        pygame.draw.rect(self._screen, r_color, r_rect, border_radius=5)
        pygame.draw.rect(self._screen, (180, 140, 50), r_rect, 1, border_radius=5)
        r_text = font_btn.render("Restart [R]", True, (255, 255, 255))
        self._screen.blit(r_text, r_text.get_rect(center=r_rect.center))
        
        # Draw Exit Button
        e_rect = pygame.Rect(ex - bw // 2, by - bh // 2, bw, bh)
        e_color = (160, 40, 50) if e_hover else (45, 25, 30)
        pygame.draw.rect(self._screen, e_color, e_rect, border_radius=5)
        pygame.draw.rect(self._screen, (180, 140, 50), e_rect, 1, border_radius=5)
        e_text = font_btn.render("Exit [Esc]", True, (255, 255, 255))
        self._screen.blit(e_text, e_text.get_rect(center=e_rect.center))
        
        pygame.display.flip()

    def _render_frame(self) -> None:
        """Render the world with camera follow and fixed HUD overlays."""
        if self._state == "MODE_SELECT":
            self._render_mode_select()
            return
            
        if self._state == "VICTORY":
            self._render_victory_screen()
            return

        if self._in_boss_arena:
            self._boss_battle.render(self._screen)
            if self._transition_active:
                self._render_transition()
            return

        self._world_surface.fill(self.BACKGROUND_COLOR)
        self._dungeon.render(self._world_surface)
        self._render_map_color_overlays(self._world_surface)
        for puzzle_room in self._puzzle_rooms:
            puzzle_room.render(self._world_surface, self._dungeon.TILE_SIZE)
        self._laboratory_room.render(self._world_surface, self._dungeon.TILE_SIZE)
        for item in self._items:
            item.render(self._world_surface, self._dungeon.TILE_SIZE)
        for trap in self._traps:
            trap.render(self._world_surface, self._dungeon.TILE_SIZE)
        for enemy in self._enemies:
            if enemy.is_alive:
                enemy.render(self._world_surface, self._dungeon.TILE_SIZE)
        self._fog.render(self._world_surface, self._dungeon.TILE_SIZE)
        self._player.render(self._world_surface, self._dungeon.TILE_SIZE)

        self._render_spirit_path(self._world_surface)
        self._render_defeat_marks(self._world_surface)
        self._screen.fill(self.BACKGROUND_COLOR)
        
        self._screen.blit(
            self._world_surface,
            (-self._camera.x, -self._camera.y),
        )
        self._render_damage_fog()
            
        # Draw bottom/horizontal inventory or default HUD
        sorted_items = self._get_sorted_inventory_items()
        self._hud.render(
            self._screen,
            self._player,
            self.KEY_TARGET_COUNT,
            self._inventory_open,
            self._inventory_selected_index,
            show_hud_bars=self._first_inventory_pressed,
            sorted_items=sorted_items,
        )
        if self._minimap_visible:
            self._render_minimap()
            
        # Render backtracking gate decryption UI
        gate_positions = self._dungeon.get_gate_positions()
        player_pos = self._player.grid_position()
        adjacent_gate = any(
            abs(player_pos[0] - gx) + abs(player_pos[1] - gy) == 1
            for gx, gy in gate_positions
        )
        if (self._gate_unlock_active or self._gate_message) and adjacent_gate:
            self._render_backtracking_puzzle()
            
        # Render transition overlay
        if self._transition_active:
            self._render_transition()

    def _render_damage_fog(self) -> None:
        """Tint the dark fog red briefly after the player takes damage."""
        if self._damage_fog_timer <= 0.0:
            return

        progress = self._damage_fog_timer / self.DAMAGE_FOG_DURATION
        alpha = int(90 * max(0.0, min(1.0, progress)))
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((150, 18, 28, alpha))
        self._screen.blit(overlay, (0, 0))

    def _handle_events(self) -> None:
        """Process user input and window events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._state == "VICTORY":
                    mx, my = event.pos
                    rx = self.WINDOW_WIDTH // 2 - 110
                    ex = self.WINDOW_WIDTH // 2 + 110
                    by = self.WINDOW_HEIGHT // 2 + 160
                    bw, bh = 180, 42
                    if (rx - bw // 2 <= mx <= rx + bw // 2) and (by - bh // 2 <= my <= by + bh // 2):
                        self._reset_game()
                        self._state = "PLAY"
                    elif (ex - bw // 2 <= mx <= ex + bw // 2) and (by - bh // 2 <= my <= by + bh // 2):
                        self._running = False
                        return

            if event.type == pygame.KEYDOWN:
                if self._state == "VICTORY":
                    if event.key == pygame.K_r:
                        self._reset_game()
                        self._state = "PLAY"
                    elif event.key == pygame.K_ESCAPE:
                        self._running = False
                        return
                    continue

                if event.key == pygame.K_ESCAPE:
                    self._running = False
                    return

                # 1. Mode select menu input handling
                if self._state == "MODE_SELECT":
                    if event.key in (pygame.K_w, pygame.K_UP):
                        self._menu_selected_idx = 0
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        self._menu_selected_idx = 1
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
                        self._game_mode = "LOW" if self._menu_selected_idx == 0 else "MEDIUM"
                        self._reset_game()
                        self._state = "PLAY"
                    continue

                # 2. Fullscreen Gomoku boss battle input handling
                if self._in_boss_arena:
                    if self._boss_battle.is_player_turn:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            self._boss_battle.move_cursor(0, -1)
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            self._boss_battle.move_cursor(0, 1)
                        elif event.key in (pygame.K_a, pygame.K_LEFT):
                            self._boss_battle.move_cursor(-1, 0)
                        elif event.key in (pygame.K_d, pygame.K_RIGHT):
                            self._boss_battle.move_cursor(1, 0)
                        elif event.key in (pygame.K_SPACE, pygame.K_e, pygame.K_RETURN):
                            self._boss_battle.place_player_move()
                    continue

                # 3. Standard play mode input handling
                if event.key == pygame.K_i:
                    self._inventory_open = not self._inventory_open
                    self._inventory_selected_index = 0
                    self._first_inventory_pressed = True # Unlock HP/STA display permanently

                # Quick use hotkeys 1-5
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    slot_idx = event.key - pygame.K_1
                    sorted_items = self._get_sorted_inventory_items()
                    if slot_idx < len(sorted_items):
                        item_name, _ = sorted_items[slot_idx]
                        self._use_item_by_name(item_name)

                elif self._inventory_open and event.key in (pygame.K_a, pygame.K_LEFT, pygame.K_w, pygame.K_UP):
                    self._cycle_inventory_selection(-1)

                elif self._inventory_open and event.key in (pygame.K_d, pygame.K_RIGHT, pygame.K_s, pygame.K_DOWN):
                    self._cycle_inventory_selection(1)

                elif event.key == pygame.K_m:
                    # ONLY unlocked if laboratory room is completed
                    is_minimap_unlocked = hasattr(self, "_laboratory_room") and getattr(self._laboratory_room, "map_unlocked", False)
                    if is_minimap_unlocked:
                        self._minimap_visible = not self._minimap_visible
                    else:
                        print("[SYSTEM] Minimap locked! Requires Laboratory room completion to unlock.")

                elif event.key == pygame.K_e:
                    if self._player.is_alive:
                        if self._inventory_open:
                            self._use_selected_item()
                        else:
                            self._handle_interactions()

                elif event.key == pygame.K_SPACE:
                    if self._player.is_alive:
                        if self._path_camera_active:
                            self._stop_path_camera()
                            return
                        self._handle_sword_attack()

                elif event.key == pygame.K_r:
                    self._reset_game()

    def _reset_game(self) -> None:
        """Regenerate the dungeon and reset the player state based on selected mode."""
        gw = (self.WINDOW_WIDTH // Dungeon.TILE_SIZE) * 2
        gh = (self.WINDOW_HEIGHT // Dungeon.TILE_SIZE) * 2
        
        self._dungeon = Dungeon(grid_width=gw, grid_height=gh, game_mode=self._game_mode)
        self._world_surface = pygame.Surface(self._world_pixel_size())
        self._camera = Camera(
            self.WINDOW_WIDTH,
            self.WINDOW_HEIGHT,
            self._world_surface.get_width(),
            self._world_surface.get_height(),
        )
        self._player = Player.spawn(self._dungeon)
        
        # Configure player parameters based on selected mode
        if self._game_mode == "LOW":
            self._player.stamina_cost_per_move = 0.0
            self._player.move_cooldown_val = 0.10
        else:
            self._player.stamina_cost_per_move = 0.5
            self._player.move_cooldown_val = 0.15


        self._puzzle_rooms = self._spawn_puzzle_rooms()
        self._laboratory_room = self._spawn_laboratory_room()
        self._items = self._spawn_items()
        self._traps = self._spawn_traps()
        self._enemies = self._spawn_enemies()
        self._combat = Combat()
        self._combat.STAMINA_COST = Player.ATTACK_COST
        self._fog = FogOfWar(self._dungeon.GRID_WIDTH, self._dungeon.GRID_HEIGHT)
        self._fog.update(
            self._player,
            self._dungeon,
            boss_visible=self._is_boss_area_visible(),
        )
        self._camera.update(self._player, self._dungeon.TILE_SIZE)
        self._inventory_open = False
        self._inventory_selected_index = 0
        self._spirit_path = []
        self._laboratory_path = []
        self._spirit_path_timer = 0.0
        self._spirit_path_duration = 4.0
        self._path_camera_active = False
        self._spirit_camera_active = False
        self._path_camera_anchor = CameraAnchor(self._player.x, self._player.y)
        self._path_camera_index = 0
        self._path_camera_timer = 0.0
        self._defeat_marks = []
        self._enemy_growth_timer = 0.0
        self._damage_fog_timer = 0.0
        self._minimap_visible = False
        self._in_boss_arena = False
        self._boss_arena = None
        self._first_inventory_pressed = False

        # Gomoku Boss Battle initializations
        from systems.boss_battle import BossBattle
        self._boss_battle = BossBattle(mode=self._game_mode)
        self._round_pause_timer = 0.0
        self._round_pause_started = False

        self._visited_tiles = set()
        self._visited_tiles.add(self._player.grid_position())

        # Backtracking Gate combo setup
        self._gate_correct_combo = [1, 2, 3, 4]
        random.shuffle(self._gate_correct_combo)
        self._gate_solver = ForwardCheckingGateSolver(self._gate_correct_combo)
        self._gate_unlock_active = False
        self._gate_timer = 0.0
        self._gate_message = ""
        self._last_player_hp = self._player.hp

    def _get_sorted_inventory_items(self) -> list[tuple[str, int]]:
        """Return a sorted list of inventory items where usable items are placed first."""
        raw = self._player.inventory.to_dict()
        items = [(k, v) for k, v in raw.items() if v > 0]
        
        usable = []
        others = []
        for name, count in items:
            if name in ("Health Potion", "Spirit"):
                usable.append((name, count))
            else:
                others.append((name, count))
        
        usable.sort(key=lambda x: x[0])
        others.sort(key=lambda x: x[0])
        return usable + others

    def _use_item_by_name(self, name: str) -> None:
        """Use an item by its exact raw name."""
        if name == "Sword":
            print("Sword equipped. Press SPACE to attack.")
        elif name == "Torch":
            print(f"Torch active. Version is {self._player.vision}.")
        elif name == "Magic Stone":
            self._use_magic_stone()
        elif name == "Spirit":
            self._use_spirit_item()
        elif name == "Health Potion":
            self._use_health_potion()
        elif name.startswith("Key"):
            self._use_keys_item()

    def _render_mode_select(self) -> None:
        """Draw the mode selection screen at startup."""
        self._screen.fill((10, 8, 16))
        
        font_title = FontCache.get(38)
        font_body = FontCache.get(26)
        
        title_surf = font_title.render("AI DUNGEON ADVENTURE", True, (180, 130, 60))
        title_rect = title_surf.get_rect(center=(self.WINDOW_WIDTH // 2, 120))
        self._screen.blit(title_surf, title_rect)
        
        subtitle_surf = font_body.render("CHOOSE GAMEPLAY MODE", True, (160, 150, 150))
        subtitle_rect = subtitle_surf.get_rect(center=(self.WINDOW_WIDTH // 2, 180))
        self._screen.blit(subtitle_surf, subtitle_rect)
        
        # Low mode option
        low_color = (255, 230, 100) if self._menu_selected_idx == 0 else (120, 110, 120)
        low_text = font_body.render("-> LOW MODE (Easy / Gomoku Boss)" if self._menu_selected_idx == 0 else "   LOW MODE (Easy / Gomoku Boss)", True, low_color)
        low_rect = low_text.get_rect(center=(self.WINDOW_WIDTH // 2, 280))
        self._screen.blit(low_text, low_rect)
        
        low_desc = FontCache.get(20).render("Walking costs 0 Stamina. +3 Swords/Torches. Gomoku Boss 6x6 board.", True, (120, 120, 120))
        self._screen.blit(low_desc, low_desc.get_rect(center=(self.WINDOW_WIDTH // 2, 315)))
        
        # Medium mode option
        med_color = (255, 230, 100) if self._menu_selected_idx == 1 else (120, 110, 120)
        med_text = font_body.render("-> MEDIUM MODE (Normal / Gomoku 15x15)" if self._menu_selected_idx == 1 else "   MEDIUM MODE (Normal / Gomoku 15x15)", True, med_color)
        med_rect = med_text.get_rect(center=(self.WINDOW_WIDTH // 2, 400))
        self._screen.blit(med_text, med_rect)
        
        med_desc = FontCache.get(20).render("Walking costs 0.5 Stamina. A* Ghost slows inside walls. Bombs deal DOT. Potion drops. Gomoku 15x15.", True, (120, 120, 120))
        self._screen.blit(med_desc, med_desc.get_rect(center=(self.WINDOW_WIDTH // 2, 435)))
        
        hint_surf = FontCache.get(22).render("Use W/S or UP/DOWN to navigate, ENTER or SPACE to start", True, (180, 180, 180))
        hint_rect = hint_surf.get_rect(center=(self.WINDOW_WIDTH // 2, 580))
        self._screen.blit(hint_surf, hint_rect)
        
        pygame.display.flip()

    def _update_boss_round_pause(self, dt: float) -> None:
        """Wait briefly between rounds before starting the next board."""
        self._handle_boss_match_result()
        from systems.boss_battle import MatchResult
        if self._boss_battle.match_result != MatchResult.NONE:
            return
        if not self._boss_battle.is_active:
            return

        if self._boss_battle.is_boss_turn:
            self._boss_battle.update()
            self._handle_boss_match_result()

        if not self._boss_battle.round_over:
            self._round_pause_started = False
            return

        if not self._round_pause_started:
            self._round_pause_timer = 1.8 # BOSS_ROUND_PAUSE
            self._round_pause_started = True
            return

        if self._round_pause_timer <= 0.0:
            return

        self._round_pause_timer = max(0.0, self._round_pause_timer - dt)
        if self._round_pause_timer == 0.0:
            self._boss_battle.advance_after_round_delay()
            self._round_pause_started = False
            self._boss_battle.update()

    def _handle_boss_match_result(self) -> None:
        """Apply the final boss match outcome."""
        from systems.boss_battle import MatchResult
        result = self._boss_battle.match_result
        if result == MatchResult.NONE:
            return

        self._boss_battle.exit_battle()
        self._round_pause_timer = 0.0
        self._round_pause_started = False

        if result == MatchResult.PLAYER_WIN:
            # We exit the boss arena successfully and trigger victory!
            print("Congratulations! You defeated the Boss in Gomoku!")
            self._in_boss_arena = False
            self._exit_boss_arena()
        else:
            # Player lost! Game Over.
            self._player.hp = 0
            print("The Boss defeated you in Gomoku.")


    def _handle_sword_attack(self) -> None:
        """Attack adjacent enemies with the sword when requirements are met."""
        if not self._player.has_sword():
            return

        if not self._player.can_attack():
            if self._player._attack_cooldown_timer > 0.0:
                return
            print("Not enough stamina")
            return

        targets = self._boss_arena.enemies if self._in_boss_arena and self._boss_arena is not None else self._enemies
        try:
            self._player.start_attack()
        except Exception:
            pass

        defeated = self._combat.sword_attack(self._player, cast(Any, targets))
        if defeated:
            for enemy in defeated:
                self._defeat_marks.append(
                    {"x": enemy.x, "y": enemy.y, "timer": 0.5}
                )
                if random.random() < 0.10:
                    potion = HealthPotion(enemy.x, enemy.y)
                    self._items.append(potion)
                    print("[LOOT] The enemy dropped a Health Potion!")
            gained = 10 * len(defeated)
            self._player.heal(gained)
            print(f"Healed {gained} HP from defeated enemies.")

    def _render_map_color_overlays(self, surface: pygame.Surface) -> None:
        """Leave dungeon tiles intact so sprite doors and room colors render cleanly."""
        return

    def _render_spirit_path(self, surface: pygame.Surface) -> None:
        """Draw paths revealed by the Spirit item or Laboratory."""
        if self._in_boss_arena:
            return

        tile_size = self._dungeon.TILE_SIZE

        # Render Laboratory path (orange, permanent)
        if self._laboratory_path:
            lab_overlay = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            lab_overlay.fill((255, 140, 0, 100)) # Translucent orange
            for x, y in self._laboratory_path:
                surface.blit(lab_overlay, (x * tile_size, y * tile_size))

        # Render Spirit path (sky blue, temporary)
        if self._spirit_path:
            spirit_overlay = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            spirit_overlay.fill((80, 220, 220, 120)) # Translucent sky blue
            for x, y in self._spirit_path:
                surface.blit(spirit_overlay, (x * tile_size, y * tile_size))

    def _render_defeat_marks(self, surface: pygame.Surface) -> None:
        """Draw short red X markers where enemies were defeated."""
        tile_size = self._dungeon.TILE_SIZE
        for mark in self._defeat_marks:
            x = int(mark["x"]) * tile_size
            y = int(mark["y"]) * tile_size
            alpha = int(255 * max(0.0, min(1.0, float(mark["timer"]) / 0.5)))
            layer = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            color = (230, 25, 35, alpha)
            pygame.draw.line(layer, color, (6, 6), (tile_size - 6, tile_size - 6), 4)
            pygame.draw.line(layer, color, (tile_size - 6, 6), (6, tile_size - 6), 4)
            surface.blit(layer, (x, y))

    def _update_spirit_path(self, dt: float) -> None:
        """Update the active spirit guidance overlay timer."""
        if self._path_camera_active:
            return

        if self._spirit_path_timer <= 0.0:
            return

        self._spirit_path_timer = max(0.0, self._spirit_path_timer - dt)
        if self._spirit_path_timer == 0.0:
            self._spirit_path = []

    def _start_path_camera(self, path: list[tuple[int, int]], is_spirit: bool = False) -> None:
        """Lock the camera to a moving path preview anchor."""
        if not path:
            return

        self._path_camera_active = True
        self._path_camera_index = 0
        self._path_camera_timer = 0.0
        self._path_camera_anchor.x, self._path_camera_anchor.y = path[0]
        self._spirit_camera_active = is_spirit

        if is_spirit:
            self._reveal_spirit_fog(path[0])

    def _stop_path_camera(self) -> None:
        """Return camera control to the player."""
        self._path_camera_active = False
        
        # If this was a Spirit camera scouter finishing
        if self._spirit_camera_active:
            self._spirit_camera_active = False
            if not getattr(self, "_spirit_path_has_key", False):
                # Close/vanish path if no key was found along it
                self._spirit_path = []
                self._spirit_path_timer = 0.0
        else:
            self._spirit_camera_active = False

        self._path_camera_anchor.x = self._player.x
        self._path_camera_anchor.y = self._player.y

    def _update_path_camera(self, dt: float) -> None:
        """Advance the path camera one tile at a time."""
        if not self._path_camera_active or not self._spirit_path:
            return

        self._path_camera_timer += dt
        if self._path_camera_timer < self._path_camera_step_time:
            return

        self._path_camera_timer = 0.0
        self._path_camera_index += 1
        if self._path_camera_index >= len(self._spirit_path):
            self._stop_path_camera()
            return

        pos = self._spirit_path[self._path_camera_index]
        self._path_camera_anchor.x, self._path_camera_anchor.y = pos

        if self._spirit_camera_active:
            self._reveal_spirit_fog(pos)

    def _reveal_spirit_fog(self, pos: tuple[int, int]) -> None:
        """Reveal fog of war in a 1-tile radius around the spirit's position."""
        cx, cy = pos
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self._fog._width and 0 <= ny < self._fog._height:
                    self._fog._revealed[ny][nx] = True

    def _update_defeat_marks(self, dt: float) -> None:
        """Expire short red X enemy defeat markers and update death animations."""
        for mark in self._defeat_marks:
            mark["timer"] = float(mark["timer"]) - dt
        self._defeat_marks = [
            mark for mark in self._defeat_marks if float(mark["timer"]) > 0.0
        ]

        for anim in self._death_animations:
            anim["timer"] -= dt
        self._death_animations = [
            anim for anim in self._death_animations if anim["timer"] > 0.0
        ]

    def _inventory_lines(self) -> list[str]:
        """Return a list of selectable inventory items for the overlay."""
        lines: list[str] = []
        if self._player.inventory.has("Sword"):
            lines.append("Sword")
        if self._player.inventory.has("Magic Stone"):
            lines.append("Magic Stone")
        if self._player.inventory.has("Spirit"):
            lines.append("Spirit")
        if self._player.inventory.has("Health Potion"):
            lines.append(f"Health Potion x{self._player.inventory.count('Health Potion')}")
        if self._player.inventory.has("Torch"):
            lines.append("Torch")
        if self._player.keys > 0:
            lines.append(f"Keys: {self._player.keys}/{self.KEY_TARGET_COUNT}")
        if not lines:
            lines.append("No usable items")
        return lines

    def _cycle_inventory_selection(self, delta: int) -> None:
        """Move the current inventory cursor up or down."""
        items = self._get_sorted_inventory_items()
        if not items:
            self._inventory_selected_index = 0
            return

        self._inventory_selected_index = (
            self._inventory_selected_index + delta
        ) % len(items)

    def _use_selected_item(self) -> None:
        """Use the currently selected inventory item from the I menu."""
        items = self._get_sorted_inventory_items()
        if not items:
            print("No item selected.")
            return

        if self._inventory_selected_index >= len(items):
            self._inventory_selected_index = 0

        selected, _ = items[self._inventory_selected_index]
        self._use_item_by_name(selected)

    def _use_magic_stone(self) -> None:
        """Consume a Magic Stone and place a temporary wall in front of the player."""
        if not self._player.inventory.has("Magic Stone"):
            print("No Magic Stone to use.")
            return

        fx = self._player.x + self._player.facing[0]
        fy = self._player.y + self._player.facing[1]
        if self._in_boss_arena and self._boss_arena is not None:
            if 0 <= fx < self._boss_arena.GRID_WIDTH and 0 <= fy < self._boss_arena.GRID_HEIGHT:
                if self._boss_arena._grid[fy][fx] == self._boss_arena.FLOOR:
                    self._boss_arena._grid[fy][fx] = self._boss_arena.WALL
                    self._player.inventory.remove("Magic Stone", 1)
                    print("Placed Magic Wall in arena")
                    return

        if 0 <= fx < self._dungeon.GRID_WIDTH and 0 <= fy < self._dungeon.GRID_HEIGHT:
            if not self._dungeon.is_gate_position(fx, fy) and self._dungeon.get_tile(fx, fy) == FLOOR:
                self._dungeon._grid[fy][fx] = WALL
                self._player.inventory.remove("Magic Stone", 1)
                print("Placed Magic Wall")
                return

        print("Cannot place Magic Stone there.")

    def _use_health_potion(self) -> None:
        """Consume a stored health potion to restore the player's HP to max."""
        if not self._player.inventory.has("Health Potion"):
            print("No Health Potion to use.")
            return

        if self._player.hp >= self._player.max_hp:
            print("You are already at full health.")
            return

        if not self._player.inventory.remove("Health Potion", 1):
            print("Failed to use Health Potion.")
            return

        self._inventory_open = False
        self._player.heal(self._player.max_hp)
        print("Used Health Potion and restored full health.")

    def _use_spirit_item(self) -> None:
        """Consume the Spirit and scout blind paths using BFS."""
        if not self._player.inventory.has("Spirit"):
            print("No Spirit to use.")
            return

        if not self._player.inventory.remove("Spirit", 1):
            print("Failed to use Spirit.")
            return

        # Close inventory immediately and reset camera scouter
        self._inventory_open = False
        self._stop_path_camera()

        start = self._player.grid_position()
        grid = self._dungeon._build_pathfinding_grid(include_gate=True)

        # Custom BFS for blind branch exploration (max 80 tiles)
        from collections import deque
        queue = deque([(start, [start])])
        visited = {start}
        
        all_unexplored_paths = []
        
        has_all_keys = self._player.keys >= 4 or sum(self._player.inventory.count(k) for k in ("Key 1", "Key 2", "Key 3", "Key 4")) >= 4
        
        key_coords = {}
        for item in self._items:
            if item.name.startswith("Key"):
                key_coords[item.grid_position()] = item.name

        def is_boss_tile(tx, ty):
            return self._dungeon.is_boss_room_tile(tx, ty)

        while queue:
            current, path = queue.popleft()
            if len(path) > 80:
                continue
                
            x, y = current
            is_revealed = self._fog.is_revealed(x, y)
            
            if not is_revealed:
                if is_boss_tile(x, y) and not has_all_keys:
                    pass
                else:
                    all_unexplored_paths.append(path)
            
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self._dungeon.GRID_WIDTH and 0 <= ny < self._dungeon.GRID_HEIGHT:
                    if grid[ny][nx] == 0 and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append(((nx, ny), path + [(nx, ny)]))

        selected_path = []
        if all_unexplored_paths:
            # Pick the longest blind path to explore deeply
            selected_path = max(all_unexplored_paths, key=len)
        else:
            # Fallback path to the boss gate
            goal = self._dungeon.get_gate_position()
            fallback_path, _, _ = bfs(start, goal, grid)
            if fallback_path:
                selected_path = fallback_path[:80]

        if not selected_path:
            print("The spirit cannot find any paths to explore.")
            return

        # Check if the scouted path contains any key
        self._spirit_path_has_key = any(pos in key_coords for pos in selected_path)

        # Always start path camera scouter to lead the player along the path (full 80 blocks)
        self._spirit_path = selected_path
        self._spirit_path_timer = max(self._spirit_path_duration, len(selected_path) * self._path_camera_step_time + 2.0)
        self._start_path_camera(selected_path, is_spirit=True)
        if self._spirit_path_has_key:
            print("The spirit found a path containing a hidden key! Scouting...")
        else:
            print("The spirit flies off to explore blindly... (No keys found)")

    def _activate_laboratory_path(self) -> None:
        """Reveal a path from the laboratory to the boss gate and light up only this path."""
        start = self._player.grid_position()
        goal = self._dungeon.get_gate_position()
        path, _, _ = bfs(
            start,
            goal,
            self._dungeon._build_pathfinding_grid(include_gate=True),
        )

        if not path:
            print("Laboratory could not locate the boss gate.")
            return

        # Reset all revealed fog of war tiles to False
        for y in range(self._fog._height):
            for x in range(self._fog._width):
                self._fog._revealed[y][x] = False

        # Reveal only the tiles on the path
        for px, py in path:
            self._fog._revealed[py][px] = True

        # Keep player's surrounding tiles visible
        self._fog.update(
            self._player,
            self._dungeon,
            boss_visible=self._is_boss_area_visible(),
        )

        # Highlight the path permanently
        self._laboratory_path = path
        self._start_path_camera(path, is_spirit=False)
        print("Laboratory BFS path revealed. Camera follows the path to the boss gate.")

    def _use_keys_item(self) -> None:
        """Use accumulated keys to unlock the boss gate when standing nearby."""
        gate_positions = self._dungeon.get_gate_positions()
        player_pos = self._player.grid_position()
        adjacent_gate = any(
            abs(player_pos[0] - gx) + abs(player_pos[1] - gy) == 1
            for gx, gy in gate_positions
        )

        if self._dungeon.gate.locked and adjacent_gate:
            available_keys = max(
                self._player.keys,
                sum(self._player.inventory.count(k) for k in ("Key 1", "Key 2", "Key 3", "Key 4")),
            )
            if available_keys < self.KEY_TARGET_COUNT:
                print(f"You need {self.KEY_TARGET_COUNT} keys to attempt unlocking.")
                self._gate_message = f"Need {self.KEY_TARGET_COUNT} keys!"
                return

            if self._boss_gate_guards_alive():
                self._gate_message = "Defeat the boss gate guards first!"
                print("The boss gate is guarded. Defeat the gate guards first.")
                return

            if not self._gate_unlock_active:
                self._gate_unlock_active = True
                self._gate_timer = 0.0
                self._gate_solver.start_solving()
                self._gate_message = "Ready. Standing still..."
                print("Unlocking boss gate using backtracking algorithm...")
            return

        print("Stand next to the boss gate to use your keys.")

    def _render_minimap(self) -> None:
        """Draw an enlarged, high-visibility minimap in the top-right corner."""
        w = 260
        h = 162
        minimap_x = self.WINDOW_WIDTH - w - self.MINIMAP_MARGIN
        minimap_y = self.MINIMAP_MARGIN
        panel_rect = pygame.Rect(
            minimap_x,
            minimap_y,
            w,
            h,
        )
        pygame.draw.rect(self._screen, self.MINIMAP_BACKGROUND_COLOR, panel_rect)
        pygame.draw.rect(self._screen, self.MINIMAP_BORDER_COLOR, panel_rect, 2)

        cell_width = w / self._dungeon.GRID_WIDTH
        cell_height = h / self._dungeon.GRID_HEIGHT
        visited = set(self._visited_tiles)

        # Draw default route if laboratory map unlocked (orange path)
        if hasattr(self, "_laboratory_room") and getattr(self._laboratory_room, "map_unlocked", False):
            ucs_path = self._dungeon.get_ucs_path()
            for x, y in ucs_path:
                route_rect = pygame.Rect(
                    minimap_x + int(x * cell_width),
                    minimap_y + int(y * cell_height),
                    max(1, int(cell_width)),
                    max(1, int(cell_height)),
                )
                pygame.draw.rect(self._screen, (255, 140, 0), route_rect) # Orange path

        # Draw Spirit path (sky blue path)
        if self._spirit_path:
            for x, y in self._spirit_path:
                route_rect = pygame.Rect(
                    minimap_x + int(x * cell_width),
                    minimap_y + int(y * cell_height),
                    max(1, int(cell_width)),
                    max(1, int(cell_height)),
                )
                pygame.draw.rect(self._screen, (100, 200, 255), route_rect) # Sky blue path

        for y in range(self._dungeon.GRID_HEIGHT):
            for x in range(self._dungeon.GRID_WIDTH):
                if not self._dungeon.is_boss_room_tile(x, y):
                    continue

                boss_rect = pygame.Rect(
                    minimap_x + int(x * cell_width),
                    minimap_y + int(y * cell_height),
                    max(1, int(cell_width)),
                    max(1, int(cell_height)),
                )
                pygame.draw.rect(self._screen, self.MINIMAP_BOSS_COLOR, boss_rect)

        lab_x, lab_y = self._dungeon.get_laboratory_room_position()
        lab_rect = pygame.Rect(
            minimap_x + int(lab_x * cell_width),
            minimap_y + int(lab_y * cell_height),
            max(2, int(cell_width)),
            max(2, int(cell_height)),
        )
        pygame.draw.rect(self._screen, self.MINIMAP_LAB_COLOR, lab_rect)

        spawn_x, spawn_y = self._dungeon.get_spawn_point()
        spawn_rect = pygame.Rect(
            minimap_x + int(spawn_x * cell_width),
            minimap_y + int(spawn_y * cell_height),
            max(2, int(cell_width)),
            max(2, int(cell_height)),
        )
        pygame.draw.rect(self._screen, self.MINIMAP_SPAWN_COLOR, spawn_rect)

        for x, y in visited:
            visited_rect = pygame.Rect(
                minimap_x + int(x * cell_width),
                minimap_y + int(y * cell_height),
                max(1, int(cell_width)),
                max(1, int(cell_height)),
            )
            pygame.draw.rect(self._screen, (80, 80, 80), visited_rect)

        # Visibility checking for enemies
        enemy_visible_tiles = set(visited)
        if hasattr(self, "_laboratory_room") and getattr(self._laboratory_room, "map_unlocked", False):
            enemy_visible_tiles.update(self._dungeon.get_ucs_path())

        for ry in range(self._fog._height):
            for rx in range(self._fog._width):
                if self._fog.is_revealed(rx, ry):
                    enemy_visible_tiles.add((rx, ry))

        # Draw enemies on minimap
        for enemy in self._enemies:
            enemy_pos = enemy.grid_position()
            if not enemy.is_alive or enemy_pos not in enemy_visible_tiles:
                continue

            enemy_rect = pygame.Rect(
                minimap_x + int(enemy_pos[0] * cell_width),
                minimap_y + int(enemy_pos[1] * cell_height),
                max(2, int(cell_width)),
                max(2, int(cell_height)),
            )
            pygame.draw.rect(self._screen, (210, 45, 55), enemy_rect)

        # Draw player on minimap
        px, py = self._player.grid_position()
        player_rect = pygame.Rect(
            minimap_x + int(px * cell_width),
            minimap_y + int(py * cell_height),
            max(2, int(cell_width)),
            max(2, int(cell_height)),
        )
        pygame.draw.rect(self._screen, (50, 180, 255), player_rect)

        is_minimap_unlocked = hasattr(self, "_laboratory_room") and getattr(self._laboratory_room, "map_unlocked", False)
        if not is_minimap_unlocked:
            lock_rect = pygame.Rect(minimap_x, minimap_y, w, h)
            s = pygame.Surface((lock_rect.width, lock_rect.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 160))
            self._screen.blit(s, (minimap_x, minimap_y))
            hint = self._hud._font.render("Minimap locked: Solve Laboratory", True, (255, 220, 180))
            hint_rect = hint.get_rect(center=lock_rect.center)
            self._screen.blit(hint, hint_rect)

    def _render_backtracking_puzzle(self) -> None:
        """Render the backtracking lock-picking visualizer overlay."""
        # Panel dimension
        w, h = 540, 240
        x = (self.WINDOW_WIDTH - w) // 2
        y = (self.WINDOW_HEIGHT - h) // 2
        
        # Deep burgundy/dark fantasy color palette
        bg_color = (20, 10, 15)
        border_color = (130, 20, 30)
        text_color = (230, 210, 210)
        active_color = (255, 230, 100)
        locked_color = (40, 180, 80)
        unassigned_color = (80, 80, 80)
        
        # Draw background and border
        panel_rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self._screen, bg_color, panel_rect)
        pygame.draw.rect(self._screen, border_color, panel_rect, 3)
        
        # Title
        font_title = pygame.font.Font(None, 28)
        title_surf = font_title.render("DECRYPTING WARDEN GATE (Backtracking CSP)", True, border_color)
        title_rect = title_surf.get_rect(midtop=(x + w // 2, y + 15))
        self._screen.blit(title_surf, title_rect)
        
        # Draw 4 locks
        box_size = 80
        gap = 20
        start_x = x + (w - (4 * box_size + 3 * gap)) // 2
        box_y = y + 55
        
        for i in range(4):
            box_rect = pygame.Rect(start_x + i * (box_size + gap), box_y, box_size, box_size)
            # Determine color
            is_locked = self._gate_solver.locked_status[i]
            assigned_key = self._gate_solver.assigned_keys[i]
            
            box_border_color = locked_color if is_locked else border_color
            pygame.draw.rect(self._screen, box_border_color, box_rect, 2)
            
            # Fill small background if locked
            if is_locked:
                s = pygame.Surface((box_size - 4, box_size - 4), pygame.SRCALPHA)
                s.fill((40, 180, 80, 45))
                self._screen.blit(s, (box_rect.x + 2, box_rect.y + 2))
                
            # Draw Lock label "Lock 1", "Lock 2"...
            lbl = self._hud._font.render(f"Lock {i+1}", True, text_color)
            self._screen.blit(lbl, (box_rect.x + (box_size - lbl.get_width()) // 2, box_rect.y + 8))
            
            # Draw Key / lock status
            if is_locked:
                key_text = f"Key {assigned_key}" if assigned_key else "LOCKED"
                val_surf = self._hud._font.render(key_text, True, locked_color)
            elif assigned_key is not None:
                # Lock 2 doesn't visually lock, but we show key try
                val_surf = self._hud._font.render(f"Key {assigned_key}", True, active_color)
            else:
                val_surf = self._hud._font.render("?", True, unassigned_color)
                
            self._screen.blit(val_surf, (box_rect.x + (box_size - val_surf.get_width()) // 2, box_rect.y + 40))
            
            # Draw visual lock status icon
            if is_locked or (i == 1 and self._gate_solver.locked_status[2]): # Lock 2 is correct if Lock 3 is locked
                icon_name = "key"
                icon_surface = get_named_icon(icon_name, 16)
                if icon_surface:
                    self._screen.blit(icon_surface, (box_rect.x + 6, box_rect.y + box_size - 22))
            
        # Draw status message
        msg_font = pygame.font.Font(None, 22)
        msg_surf = msg_font.render(self._gate_message, True, text_color)
        msg_rect = msg_surf.get_rect(midbottom=(x + w // 2, y + h - 20))
        self._screen.blit(msg_surf, msg_rect)
        
        # Skill action guidance
        guard_hint = msg_font.render("Watch out! Enemies will interrupt if they damage you.", True, (180, 180, 180))
        guard_rect = guard_hint.get_rect(midtop=(x + w // 2, y + h - 50))
        self._screen.blit(guard_hint, guard_rect)

    def _render_transition(self) -> None:
        """Render a dark fantasy screen transition scene."""
        alpha = int((self._transition_timer / self._transition_duration) * 255)
        
        # We want to fade to black, so we use a black surface with transparency
        fade_surf = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        fade_surf.fill((10, 5, 8)) # Very dark gothic shade
        
        # Transition goes from transparent (alpha=0) at duration, to solid black (alpha=255) at 0
        current_alpha = max(0, min(255, 255 - alpha))
        fade_surf.set_alpha(current_alpha)
        self._screen.blit(fade_surf, (0, 0))
        
        # Draw gothic opening text at the center
        if current_alpha > 100:
            font_title = pygame.font.Font(None, 48)
            font_sub = pygame.font.Font(None, 24)
            
            title_color = (130, 20, 30) # Blood red
            sub_color = (200, 190, 190)
            
            title = font_title.render("THE GATE GRINDS OPEN...", True, title_color)
            sub = font_sub.render("Entering the Boss's Chamber", True, sub_color)
            
            title_rect = title.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 - 25))
            sub_rect = sub.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 + 25))
            
            title.set_alpha(current_alpha)
            sub.set_alpha(current_alpha)
            
            self._screen.blit(title, title_rect)
            self._screen.blit(sub, sub_rect)

    def _render_min_conflict_tactical_advisor(self) -> None:
        """Render the min-conflicts recommendation overlay in the boss chamber."""
        if not self._boss_arena:
            return
            
        w, h = 330, 200
        panel_x = self.WINDOW_WIDTH - w - 16
        panel_y = 16
        
        # Bronze/Dark gold gothic palette
        bg_color = (15, 12, 18)
        border_color = (180, 130, 60)
        text_color = (226, 218, 198)
        
        panel_rect = pygame.Rect(panel_x, panel_y, w, h)
        pygame.draw.rect(self._screen, bg_color, panel_rect)
        pygame.draw.rect(self._screen, border_color, panel_rect, 2)
        
        # Header
        font_header = pygame.font.Font(None, 24)
        header_surf = font_header.render("MIN-CONFLICTS ADVISOR", True, border_color)
        self._screen.blit(header_surf, (panel_x + 12, panel_y + 12))
        
        # Separator line
        pygame.draw.line(self._screen, border_color, (panel_x + 12, panel_y + 35), (panel_x + w - 12, panel_y + 35), 1)
        
        # Body text
        font_body = pygame.font.Font(None, 20)
        
        # 1. Decision (e.g. Engage boss? / Do not engage)
        dec_label = font_body.render("Tactical Decision:", True, (150, 150, 150))
        self._screen.blit(dec_label, (panel_x + 12, panel_y + 45))
        
        decision_text = self._boss_arena.current_decision
        dec_color = (40, 180, 80) if "Engage Boss!" in decision_text and "DO NOT" not in decision_text else (180, 130, 60) if "Risky" in decision_text else (220, 60, 60)
        dec_surf = font_body.render(decision_text, True, dec_color)
        self._screen.blit(dec_surf, (panel_x + 12, panel_y + 60))
        
        # 2. Recommended target
        target_label = font_body.render("Current Recommended Target:", True, (150, 150, 150))
        self._screen.blit(target_label, (panel_x + 12, panel_y + 85))
        
        rec_target = self._boss_arena.current_recommendation.upper()
        target_color = (220, 60, 60) if rec_target == "RED" else (60, 220, 80) if rec_target == "GREEN" else (60, 100, 220) if rec_target == "BLUE" else (220, 40, 60)
        target_surf = font_header.render(f">> {rec_target} <<", True, target_color)
        self._screen.blit(target_surf, (panel_x + 12, panel_y + 100))
        
        # 3. Recommended sequence
        seq_label = font_body.render("Optimal Attack Sequence:", True, (150, 150, 150))
        self._screen.blit(seq_label, (panel_x + 12, panel_y + 130))
        
        if self._boss_arena.recommended_sequence:
            seq_text = " -> ".join([c.split(" ")[0] for c in self._boss_arena.recommended_sequence])
            seq_surf = font_body.render(seq_text, True, text_color)
        else:
            seq_surf = font_body.render("Engage Boss Directly", True, (40, 180, 80))
            
        self._screen.blit(seq_surf, (panel_x + 12, panel_y + 145))
        
        # Spin/pulse loading effect
        import math
        pulse_color = (int(127 + 127 * math.sin(pygame.time.get_ticks() / 150.0)), 0, 0)
        pygame.draw.circle(self._screen, pulse_color, (panel_x + w - 18, panel_y + 18), 4)

    def _remove_defeated_enemies(self) -> None:
        """Remove dead enemies and spawn red X defeat animations."""
        alive_enemies = []
        for enemy in self._enemies:
            if enemy.is_alive:
                alive_enemies.append(enemy)
            else:
                self._death_animations.append({
                    "x": enemy.x,
                    "y": enemy.y,
                    "timer": 0.5
                })
        self._enemies = alive_enemies

    def _update_enemy_growth(self, dt: float) -> None:
        """Increase living enemy HP during long adventure exploration."""
        self._enemy_growth_timer += dt
        if self._enemy_growth_timer < self._enemy_growth_interval:
            return

        self._enemy_growth_timer -= self._enemy_growth_interval
        for enemy in self._enemies:
            if not enemy.is_alive:
                continue
            enemy.max_hp += 1
            enemy.hp += 1
        print("Enemies grow stronger: +1 HP.")

    def _spawn_laboratory_room(self) -> LaboratoryRoom:
        """Create the laboratory room at the annealing-optimized position."""
        return LaboratoryRoom(self._dungeon.get_laboratory_room_position())

    def _spawn_puzzle_rooms(self) -> list[PuzzleRoom]:
        """Create puzzle room markers for Keys #1 and #2 locations."""
        backtracking_position, min_conflicts_position = (
            self._dungeon.get_puzzle_room_positions()
        )
        return [
            self._create_puzzle_room(
                PuzzleRoomBacktracking(backtracking_position),
                self.PUZZLE_BACKTRACKING_COLOR,
            ),
            self._create_puzzle_room(
                PuzzleRoomMinConflicts(min_conflicts_position),
                self.PUZZLE_MIN_CONFLICTS_COLOR,
            ),
        ]

    def _create_puzzle_room(
        self,
        puzzle_room: PuzzleRoom,
        color: tuple[int, int, int],
    ) -> PuzzleRoom:
        """Assign the required puzzle room color without enabling puzzle gameplay."""
        puzzle_room.color = color
        return puzzle_room

    def _spawn_items(self) -> list:
        """Create map items including Keys #1-#4, sword, potion, and torch, ensuring spacing."""
        items = [
            create_item_from_placement(placement)
            for placement in self._dungeon.get_item_placements()
        ]

        try:
            spawn = self._dungeon.get_spawn_point()
        except Exception:
            spawn = None

        occupied = {item.grid_position() for item in items}

        def find_nearby_tile(center, radius=3):
            cx, cy = center
            candidates = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < self._dungeon.GRID_WIDTH and 0 <= ny < self._dungeon.GRID_HEIGHT):
                        continue
                    if (nx, ny) in occupied:
                        continue
                    if not self._dungeon.is_walkable(nx, ny):
                        continue
                    if self._dungeon.is_forbidden_spawn_tile(nx, ny):
                        continue
                    candidates.append((nx, ny))
            if not candidates:
                return None
            return random.choice(candidates)

        if spawn is not None and items:
            preferred = ("Health Potion", "Torch")
            occupied = {item.grid_position() for item in items}

            relocated = 0
            for kind in preferred:
                if relocated >= 2:
                    break
                for item in items:
                    if item.name == kind:
                        if random.random() < 0.7:
                            target = find_nearby_tile(spawn, radius=3)
                            if target is not None:
                                item.x, item.y = target
                                occupied.add(target)
                                relocated += 1
                        break

        # Spawn up to 3 Spirits
        if spawn is not None:
            occupied = {item.grid_position() for item in items}
            spirit_count = 0
            for _ in range(3):
                spirit_target = find_nearby_tile(spawn, radius=8 + spirit_count * 4)
                if spirit_target is not None:
                    items.append(Spirit(*spirit_target))
                    occupied.add(spirit_target)
                    spirit_count += 1

        # Spawn up to 4 Health Potions
        if spawn is not None:
            health_count = sum(1 for item in items if isinstance(item, HealthPotion))
            while health_count < 4 and len(items) < self._dungeon.GRID_WIDTH * self._dungeon.GRID_HEIGHT:
                health_target = find_nearby_tile(spawn, radius=8)
                if health_target is None:
                    break
                if health_target not in occupied:
                    items.append(HealthPotion(*health_target))
                    occupied.add(health_target)
                    health_count += 1

        if spawn is not None:
            torch_count = sum(1 for item in items if isinstance(item, Torch))
            target_torch_count = torch_count + 3
            while torch_count < target_torch_count:
                torch_target = find_nearby_tile(spawn, radius=10 + torch_count * 2)
                if torch_target is None:
                    break
                if torch_target not in occupied:
                    items.append(Torch(*torch_target))
                    occupied.add(torch_target)
                    torch_count += 1
                else:
                    break

        # Enforce spacing of general items (non-keys) to be at least 5 tiles apart
        spaced_items = []
        placed_positions = []
        for item in items:
            if item.name.startswith("Key"):
                spaced_items.append(item)
                placed_positions.append(item.grid_position())
                continue

            pos = item.grid_position()
            # If too close (distance < 5) to any already placed item
            too_close = any(abs(pos[0] - px) + abs(pos[1] - py) < 5 for px, py in placed_positions)
            if too_close:
                # Find a new random walkable tile far from other items (dist >= 5) and outside boss/spawn
                found = False
                for _ in range(100):
                    rx = random.randint(1, self._dungeon.GRID_WIDTH - 2)
                    ry = random.randint(1, self._dungeon.GRID_HEIGHT - 2)
                    if self._dungeon.is_walkable(rx, ry) and not self._dungeon.is_boss_room_tile(rx, ry) and not self._dungeon.is_forbidden_spawn_tile(rx, ry):
                        if all(abs(rx - px) + abs(ry - py) >= 5 for px, py in placed_positions):
                            item.x, item.y = rx, ry
                            found = True
                            break
                if not found:
                    for _ in range(50):
                        rx = random.randint(1, self._dungeon.GRID_WIDTH - 2)
                        ry = random.randint(1, self._dungeon.GRID_HEIGHT - 2)
                        if self._dungeon.is_walkable(rx, ry) and not self._dungeon.is_boss_room_tile(rx, ry) and not self._dungeon.is_forbidden_spawn_tile(rx, ry):
                            if all(abs(rx - px) + abs(ry - py) >= 3 for px, py in placed_positions):
                                item.x, item.y = rx, ry
                                break

            spaced_items.append(item)
            placed_positions.append(item.grid_position())

        return self._normalize_sword_spawns(spaced_items, spawn)

    def _normalize_sword_spawns(self, items: list, spawn: tuple[int, int] | None) -> list:
        """Spawn the requested number of swords randomly away from reserved tiles."""
        target_count = 3 if self._game_mode == "LOW" else 5
        normalized = [item for item in items if item.name != "Sword"]
        occupied = {item.grid_position() for item in normalized}

        available_positions: list[tuple[int, int]] = []
        for y in range(self._dungeon.GRID_HEIGHT):
            for x in range(self._dungeon.GRID_WIDTH):
                pos = (x, y)
                if pos in occupied:
                    continue
                if not self._dungeon.is_walkable(x, y):
                    continue
                if self._dungeon.is_boss_room_tile(x, y):
                    continue
                if self._dungeon.is_forbidden_spawn_tile(x, y):
                    continue
                available_positions.append(pos)

        # We need to spawn target_count swords
        if target_count <= 0 or not available_positions:
            return normalized

        if spawn is not None:
            # Group available positions by Manhattan distance to spawn
            dists = {pos: abs(pos[0] - spawn[0]) + abs(pos[1] - spawn[1]) for pos in available_positions}
            
            # Find the closest distance we can achieve that is >= 30, preferably exactly 30.
            eligible_dists_ge_30 = [d for d in dists.values() if d >= 30]
            if eligible_dists_ge_30:
                d_closest = min(eligible_dists_ge_30)
            else:
                # If no tiles are >= 30, the maximum possible distance in the grid is our d_closest
                d_closest = max(dists.values()) if dists else None

            if d_closest is not None:
                # 1. Spawn exactly 1 sword at d_closest
                closest_pool = [pos for pos in available_positions if dists[pos] == d_closest]
                chosen_closest = random.choice(closest_pool)
                normalized.append(Sword(*chosen_closest))
                occupied.add(chosen_closest)
                
                # 2. Spawn the remaining target_count - 1 swords at distance > d_closest
                remaining_count = target_count - 1
                if remaining_count > 0:
                    further_pool = [pos for pos in available_positions if dists[pos] > d_closest and pos not in occupied]
                    # If we don't have enough tiles with distance > d_closest, we fall back to:
                    # - remaining tiles in closest_pool
                    # - tiles with distance < d_closest, sorted by distance descending (furthest first)
                    if len(further_pool) < remaining_count:
                        fallback_pool = [pos for pos in available_positions if dists[pos] < d_closest and pos not in occupied]
                        fallback_pool.sort(key=lambda pos: dists[pos], reverse=True)
                        pool = further_pool + [pos for pos in closest_pool if pos not in occupied] + fallback_pool
                    else:
                        pool = further_pool
                    
                    random.shuffle(pool)
                    for pos in pool[:remaining_count]:
                        normalized.append(Sword(*pos))
                        occupied.add(pos)
            else:
                # Fallback if no distances computed (should never happen if available_positions is not empty)
                random.shuffle(available_positions)
                for pos in available_positions[:target_count]:
                    normalized.append(Sword(*pos))
                    occupied.add(pos)
        else:
            # Fallback if spawn is None
            random.shuffle(available_positions)
            for pos in available_positions[:target_count]:
                normalized.append(Sword(*pos))
                occupied.add(pos)

        return normalized

    def _spawn_traps(self) -> list:
        """Create traps from AI-optimized dungeon placements."""
        return [
            create_trap_from_placement(placement)
            for placement in self._dungeon.get_trap_placements()
        ]

    def _spawn_enemies(self) -> list[Enemy]:
        """Spawn initial enemies adhering to key guards, gate guards, and isolated corridor distribution."""
        from game.enemy import EnemyGreedy, EnemyAStar
        enemies: list[Enemy] = []
        occupied_positions: set[tuple[int, int]] = set()

        player_spawn = self._dungeon.get_spawn_point()
        occupied_positions.add(player_spawn)

        # Find key positions
        key_positions = []
        for item in self._items:
            if item.name.startswith("Key"):
                key_positions.append(item.grid_position())

        # Define 3x3 key room tiles to prevent other enemies from spawning there
        key_room_tiles = set()
        for kx, ky in key_positions:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    key_room_tiles.add((kx + dx, ky + dy))

        # Dynamic monster spawn counts
        key_guard_count = 1 if self._game_mode == "LOW" else 2
        gate_guard_count = 1 if self._game_mode == "LOW" else 3
        corridor_enemy_count = 6 if self._game_mode == "LOW" else 12

        # 1. Spawn guards around each of the 4 key positions
        for kx, ky in key_positions:
            candidates = []
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx == 0 and dy == 0:
                        continue
                    px, py = kx + dx, ky + dy
                    if not self._dungeon.is_walkable(px, py):
                        continue
                    if (px, py) in occupied_positions:
                        continue
                    candidates.append((px, py))
            
            if candidates:
                # Find walkable tiles in the key room for patrol
                key_room_walkables = []
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        wx, wy = kx + dx, ky + dy
                        if self._dungeon.is_walkable(wx, wy):
                            key_room_walkables.append((wx, wy))

                for pos in random.sample(candidates, min(key_guard_count, len(candidates))):
                    enemy_cls = EnemyGreedy if random.random() < 0.5 else EnemyAStar
                    enemy = enemy_cls(*pos)
                    other_tiles = [p for p in key_room_walkables if p != pos]
                    if other_tiles:
                        enemy.patrol_route = [pos, random.choice(other_tiles)]
                    else:
                        enemy.patrol_route = [pos]
                    enemy._patrol_index = 0
                    enemy._patrol_forward = True
                    enemies.append(enemy)
                    occupied_positions.add(pos)

        # 2. Spawn guards protecting each gate entrance to the boss room (excluding key room tiles)
        gate_positions = self._dungeon.get_gate_positions()
        for gx, gy in gate_positions:
            candidates = []
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    if dx == 0 and dy == 0:
                        continue
                    px, py = gx + dx, gy + dy
                    if not self._dungeon.is_walkable(px, py):
                        continue
                    if self._dungeon.is_boss_room_tile(px, py):
                        continue
                    if (px, py) in key_room_tiles:
                        continue
                    if (px, py) in occupied_positions:
                        continue
                    candidates.append((px, py))
            
            if candidates:
                candidates.sort(key=lambda p: abs(p[0] - gx) + abs(p[1] - gy))
                for pos in candidates[:gate_guard_count]:
                    enemy_cls = EnemyGreedy if random.random() < 0.6 else EnemyAStar
                    enemy = enemy_cls(*pos)
                    enemy.is_boss_gate_guard = True
                    enemy.max_chase_distance = 20
                    enemy.patrol_route = self._boss_guard_patrol_route(pos, (gx, gy))
                    enemy._patrol_index = 0
                    enemy._patrol_forward = True
                    enemies.append(enemy)
                    occupied_positions.add(pos)

        # 3. Spawn multiple isolated corridor enemies (spaced >= 8, excluding key room tiles)
        far_candidates = self._get_far_spawn_candidates()
        corridor_candidates = []
        for pos in far_candidates:
            if pos in occupied_positions:
                continue
            if self._dungeon.is_boss_room_tile(*pos):
                continue
            if pos in key_room_tiles:
                continue
            if all(abs(pos[0] - op[0]) + abs(pos[1] - op[1]) >= 8 for op in occupied_positions):
                corridor_candidates.append(pos)

        random.shuffle(corridor_candidates)
        # Spawn up to corridor_enemy_count corridor enemies
        for pos in corridor_candidates[:corridor_enemy_count]:
            enemy_cls = EnemyGreedy if random.random() < 0.5 else EnemyAStar
            enemies.append(enemy_cls(*pos))
            occupied_positions.add(pos)

        return enemies

    def _boss_gate_guards_alive(self) -> bool:
        """Return True while any required boss gate guard is still alive."""
        return any(
            enemy.is_boss_gate_guard and enemy.is_alive
            for enemy in self._enemies
        )

    def _is_boss_area_visible(self) -> bool:
        """Return True when normal vision may reveal boss-room tiles."""
        lab_unlocked = hasattr(self, "_laboratory_room") and getattr(
            self._laboratory_room,
            "map_unlocked",
            False,
        )
        return lab_unlocked or not self._boss_gate_guards_alive()

    def _boss_guard_patrol_route(
        self,
        start: tuple[int, int],
        gate: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """Build a short route so gate guards move around the boss entrance."""
        candidates: list[tuple[int, int]] = []
        gx, gy = gate

        for dy in range(-3, 4):
            for dx in range(-3, 4):
                px, py = gx + dx, gy + dy
                pos = (px, py)
                if pos == start:
                    continue
                if not self._dungeon.is_walkable(px, py):
                    continue
                if self._dungeon.is_boss_room_tile(px, py):
                    continue
                if self._dungeon.is_gate_position(px, py):
                    continue
                if abs(px - gx) + abs(py - gy) > 4:
                    continue
                candidates.append(pos)

        candidates.sort(key=lambda pos: abs(pos[0] - start[0]) + abs(pos[1] - start[1]))
        route = [start]
        for pos in candidates[:3]:
            if pos not in route:
                route.append(pos)
        return route

    def _get_far_spawn_candidates(self) -> list[tuple[int, int]]:
        """Return walkable tiles far enough from spawn and outside special rooms."""
        player_spawn = self._dungeon.get_spawn_point()
        candidates: list[tuple[int, int]] = []

        for y in range(self._dungeon.GRID_HEIGHT):
            for x in range(self._dungeon.GRID_WIDTH):
                if not self._dungeon.is_walkable(x, y):
                    continue
                if self._dungeon.is_forbidden_spawn_tile(x, y):
                    continue
                if (x, y) == player_spawn:
                    continue

                distance = abs(x - player_spawn[0]) + abs(y - player_spawn[1])
                if distance < self.ENEMY_MIN_SPAWN_DISTANCE:
                    continue

                candidates.append((x, y))

        return candidates

    def _spawn_boss_alert(self) -> None:
        """Spawn a pressure wave of guards from multiple boss approaches."""
        from game.enemy import EnemyGreedy, EnemyAStar

        spawn_count = 5 if self._game_mode == "LOW" else 7
        player_pos = self._player.grid_position()
        occupied = {player_pos}
        occupied.update(enemy.grid_position() for enemy in self._enemies if enemy.is_alive)
        occupied.update(item.grid_position() for item in self._items)
        occupied.update(self._dungeon.get_gate_positions())

        candidates: list[tuple[int, int]] = []
        for gx, gy in self._dungeon.get_gate_positions():
            for dy in range(-6, 7):
                for dx in range(-6, 7):
                    pos = (gx + dx, gy + dy)
                    x, y = pos
                    if pos in occupied:
                        continue
                    if abs(dx) + abs(dy) > 7:
                        continue
                    if not self._dungeon.is_walkable(x, y):
                        continue
                    if self._dungeon.is_boss_room_tile(x, y):
                        continue
                    candidates.append(pos)

        random.shuffle(candidates)
        for pos in candidates[:spawn_count]:
            enemy_cls = EnemyAStar if random.random() < 0.45 else EnemyGreedy
            enemy = enemy_cls(*pos)
            enemy.is_boss_gate_guard = True
            enemy.max_chase_distance = 20
            enemy.detection_radius = max(enemy.detection_radius, 10)
            enemy.last_known_player_position = player_pos
            enemy.state = Enemy.CHASE
            enemy.patrol_route = self._boss_guard_patrol_route(pos, random.choice(self._dungeon.get_gate_positions()))
            self._enemies.append(enemy)

        if candidates:
            print(f"[BOSS ALERT] {min(spawn_count, len(candidates))} gate guards joined the fight!")

    def _blocked_positions_for(self, enemy: Enemy) -> set[tuple[int, int]]:
        """Return tiles this enemy may not enter during movement."""
        blocked = {self._player.grid_position()}

        for other_enemy in self._enemies:
            if other_enemy is enemy or not other_enemy.is_alive:
                continue
            blocked.add(other_enemy.grid_position())

        # Block key positions
        for item in self._items:
            if item.name.startswith("Key"):
                blocked.add(item.grid_position())

        # Block gate positions
        gate_positions = self._dungeon.get_gate_positions()
        for gp in gate_positions:
            blocked.add(gp)

        return blocked

    def _handle_interactions(self) -> None:
        """Handle laboratory and item collection with the E key."""
        player_position = self._player.grid_position()

        x, y = player_position
        if self._dungeon.is_laboratory_room_tile(x, y):
            self._laboratory_room.interact(self._player)
            self._activate_laboratory_path()
            return

        for item in self._items[:]:
            if item.grid_position() != player_position:
                continue

            if self._collect_item(item):
                self._items.remove(item)
            return

        if self._player.inventory.has("Magic Stone"):
            fx = self._player.x + self._player.facing[0]
            fy = self._player.y + self._player.facing[1]
            if self._in_boss_arena and self._boss_arena is not None:
                if 0 <= fx < self._boss_arena.GRID_WIDTH and 0 <= fy < self._boss_arena.GRID_HEIGHT:
                    if self._boss_arena._grid[fy][fx] == self._boss_arena.FLOOR:
                        self._boss_arena._grid[fy][fx] = self._boss_arena.WALL
                        self._player.inventory.remove("Magic Stone", 1)
                        print("Placed Magic Wall in arena")
                        return
            else:
                if 0 <= fx < self._dungeon.GRID_WIDTH and 0 <= fy < self._dungeon.GRID_HEIGHT:
                    if not self._dungeon.is_gate_position(fx, fy) and self._dungeon.get_tile(fx, fy) == FLOOR:
                        self._dungeon._grid[fy][fx] = WALL
                        self._player.inventory.remove("Magic Stone", 1)
                        print("Placed Magic Wall")
                        return

    def _collect_item(self, item: Item) -> bool:
        """Return True when the item instance should disappear from the map and restore 40 stamina."""
        success = item.pickup(self._player)
        if success:
            self._player.regenerate_stamina(40.0)
            print(f"[HUD] Collected {item.name}! +40 Stamina restored.")
        return success

    def _handle_traps(self) -> None:
        """Activate traps when the player occupies the same tile."""
        player_position = self._player.grid_position()

        for trap in self._traps[:]:
            if trap.grid_position() != player_position:
                continue

            trap.activate(self._player)
            self._traps.remove(trap)

    def _enter_boss_arena(self) -> None:
        """Teleport the player into the boss arena for the final fight."""
        if self._in_boss_arena:
            return

        self._in_boss_arena = True
        self._boss_battle.enter_battle()
        print("Entered the Gomoku boss arena! Best of three wins.")

    def _exit_boss_arena(self) -> None:
        """Return the player to the dungeon after the boss is defeated."""
        self._in_boss_arena = False
        self._state = "VICTORY"
        print("Boss defeated!")


def main() -> None:
    """Launch the game."""
    app = GameApplication()
    app.run()


if __name__ == "__main__":
    main()
