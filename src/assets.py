from dataclasses import dataclass
from pathlib import Path

import pygame


RUNTIME_ASSET_GROUPS = {
    "player": Path("assets/kenney/Player"),
    "crates": Path("assets/kenney/Crates"),
    "blocks": Path("assets/kenney/Blocks"),
    "ground": Path("assets/kenney/Ground"),
    "environment": Path("assets/kenney/Environment"),
}


@dataclass(frozen=True)
class SpriteRef:
    path: Path
    offset: tuple[int, int] = (0, 0)


class AssetCatalog:
    """Kenney Sokoban Pack - 24 player sprites mapped by direction and pose.

    Down (front):  01=idle  02=walk1  03=walk2  05=push   23=happy  24=happy2
    Up   (back):   04=idle  08=walk1  09=walk2  10=push
    Right (side):  11=idle  12=walk1  13=walk2  14=push   15=alt    16=alt2
    Left (side):   19=idle  20=walk1  21=walk2  22=push   17=alt    18=alt2
    """

    def __init__(self, project_root: Path, tile_size: int) -> None:
        self.project_root = project_root
        self.tile_size = tile_size
        self._cache: dict[str, pygame.Surface] = {}

        P = "assets/kenney/Player"
        self.player_map = {
            # Down = front-facing (mặt hướng về phía người chơi)
            ("down", "idle"):   SpriteRef(Path(f"{P}/player_01.png")),
            ("down", "walk1"):  SpriteRef(Path(f"{P}/player_02.png")),
            ("down", "walk2"):  SpriteRef(Path(f"{P}/player_03.png")),
            ("down", "push"):   SpriteRef(Path(f"{P}/player_05.png")),
            # Up = back-facing (mặt quay lưng)
            ("up", "idle"):     SpriteRef(Path(f"{P}/player_04.png")),
            ("up", "walk1"):    SpriteRef(Path(f"{P}/player_08.png")),
            ("up", "walk2"):    SpriteRef(Path(f"{P}/player_09.png")),
            ("up", "push"):     SpriteRef(Path(f"{P}/player_10.png")),
            # Left = nhìn sang trái (player_14, 15, 16, 20)
            ("left", "idle"):   SpriteRef(Path(f"{P}/player_14.png")),
            ("left", "walk1"):  SpriteRef(Path(f"{P}/player_15.png")),
            ("left", "walk2"):  SpriteRef(Path(f"{P}/player_16.png")),
            ("left", "push"):   SpriteRef(Path(f"{P}/player_20.png")),
            # Right = nhìn sang phải (player_11, 12, 13, 17)
            ("right", "idle"):  SpriteRef(Path(f"{P}/player_11.png")),
            ("right", "walk1"): SpriteRef(Path(f"{P}/player_12.png")),
            ("right", "walk2"): SpriteRef(Path(f"{P}/player_13.png")),
            ("right", "push"):  SpriteRef(Path(f"{P}/player_17.png")),
        }

        self._tile_map = {
            "floor": Path("assets/kenney/Ground/ground_01.png"),
            "target": Path("assets/kenney/Environment/environment_11.png"),
            "wall": Path("assets/kenney/Blocks/block_01.png"),
            "crate": Path("assets/kenney/Crates/crate_01.png"),
            "crate_ok": Path("assets/kenney/Crates/crate_05.png"),
        }
        self.sounds = {
            "win": str(self.project_root / "assets/sounds/Am_thanh_chuc_mung_chien_thang.mp3"),
            "fail": str(self.project_root / "assets/sounds/hieu_ung_am_thanh_that_bai_trong_tro_choi.mp3"),
        }
        self._image_map = {
            "menu_bg": Path("assets/images/hinh-nen-gaming-2.jpg"),
            "splash_bg": Path("assets/images/hinh-nen-1.jpg"),
        }

    def _load_scaled(self, relative_path: Path) -> pygame.Surface:
        key = str(relative_path)
        if key in self._cache:
            return self._cache[key]
        surface = pygame.image.load(str(self.project_root / relative_path)).convert_alpha()
        scaled = pygame.transform.smoothscale(surface, (self.tile_size, self.tile_size))
        self._cache[key] = scaled
        return scaled

    def get_image(self, key: str, size: tuple[int, int] | None = None) -> pygame.Surface:
        rel_path = self._image_map.get(key)
        if not rel_path:
            return pygame.Surface((0, 0))
        
        cache_key = f"img_{key}_{size}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        surface = pygame.image.load(str(self.project_root / rel_path)).convert()
        if size:
            surface = pygame.transform.smoothscale(surface, size)
        
        self._cache[cache_key] = surface
        return surface

    def tile(self, key: str) -> pygame.Surface:
        return self._load_scaled(self._tile_map[key])

    def player_sprite(self, direction: str, pose: str) -> pygame.Surface:
        ref = self.player_map.get((direction, pose))
        if ref is None:
            ref = self.player_map.get((direction, "idle"))
        if ref is None:
            ref = self.player_map[("down", "idle")]
        return self._load_scaled(ref.path)
