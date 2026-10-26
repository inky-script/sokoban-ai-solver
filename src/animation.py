import math
from dataclasses import dataclass


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


@dataclass
class MotionSample:
    player_offset: tuple[int, int]
    crate_offset: tuple[int, int]
    player_tilt: float
    crate_scale: tuple[float, float]
    complete: bool


class AnimationController:
    def __init__(self, tile_size: int) -> None:
        self.tile_size = tile_size
        self.active = None

    def begin_move(self, direction: str, pushed: bool, duration: float) -> None:
        self.active = {"direction": direction, "pushed": pushed, "duration": duration}

    def sample(self, elapsed: float) -> MotionSample:
        if self.active is None:
            return MotionSample((0, 0), (0, 0), 0.0, (1.0, 1.0), True)
        duration = self.active["duration"]
        t = min(1.0, max(0.0, elapsed / duration))
        eased = ease_out_cubic(t)
        push_delay = 0.18 if self.active["pushed"] else 0.0
        crate_t = 0.0 if t < push_delay else ease_out_cubic((t - push_delay) / (1.0 - push_delay))
        return MotionSample(
            player_offset=(int(self.tile_size * eased), int(math.sin(t * math.pi) * -3)),
            crate_offset=(int(self.tile_size * crate_t), 0),
            player_tilt=6.0 if self.active["pushed"] else 3.0,
            crate_scale=(1.03, 0.97) if self.active["pushed"] and t < 0.2 else (1.0, 1.0),
            complete=t >= 1.0,
        )
