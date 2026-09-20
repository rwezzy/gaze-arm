"""Snap the live gaze point to the center of a grid cell, to kill eye jitter.

The window is divided into cols x rows cells. The reported gaze point is the
center of the current cell, so small jitter inside a cell does nothing. To
move to a neighbouring cell, the gaze has to stay in it for `switch_frames`
frames in a row (no flicker when the eyes sit on a cell border); a jump of
more than `jump_cells` cells (a saccade across the screen) switches at once.
"""

from __future__ import annotations

import math
from typing import Optional

SNAP_COLS = 16          # 16 x 9 cells on a 1280 x 720 view = 80 x 80 px cells:
SNAP_ROWS = 9           # small enough that every object box contains a cell center
SWITCH_FRAMES = 4       # ~130 ms at 30 fps before moving to a neighbouring cell
JUMP_CELLS = 1.5        # further than this from the current cell's center: switch now


class GazeSnapper:
    def __init__(self, frame_w: int, frame_h: int, cols: int = SNAP_COLS, rows: int = SNAP_ROWS,
                 switch_frames: int = SWITCH_FRAMES, jump_cells: float = JUMP_CELLS):
        self.w, self.h, self.cols, self.rows = frame_w, frame_h, cols, rows
        self.cell_w, self.cell_h = frame_w / cols, frame_h / rows
        self.switch_frames, self.jump_cells = switch_frames, jump_cells
        self.cell: Optional[tuple[int, int]] = None
        self._pending: Optional[tuple[int, int]] = None
        self._pending_n = 0

    def reset(self) -> None:
        self.cell, self._pending, self._pending_n = None, None, 0

    def cell_of(self, pt) -> tuple[int, int]:
        col = min(self.cols - 1, max(0, int(pt[0] // self.cell_w)))
        row = min(self.rows - 1, max(0, int(pt[1] // self.cell_h)))
        return col, row

    def center(self, cell: tuple[int, int]) -> tuple[float, float]:
        return (cell[0] + 0.5) * self.cell_w, (cell[1] + 0.5) * self.cell_h

    def rect(self, cell: Optional[tuple[int, int]] = None) -> Optional[tuple[int, int, int, int]]:
        cell = self.cell if cell is None else cell
        if cell is None:
            return None
        return (int(cell[0] * self.cell_w), int(cell[1] * self.cell_h),
                int((cell[0] + 1) * self.cell_w), int((cell[1] + 1) * self.cell_h))

    def update(self, pt) -> Optional[tuple[float, float]]:
        """Raw (smoothed) gaze point -> snapped cell center; None if no gaze."""
        if pt is None:
            self.reset()
            return None
        cell = self.cell_of(pt)
        if self.cell is None or cell == self.cell:
            self.cell, self._pending, self._pending_n = cell, None, 0
            return self.center(self.cell)
        cx, cy = self.center(self.cell)
        far = math.hypot((pt[0] - cx) / self.cell_w, (pt[1] - cy) / self.cell_h) > self.jump_cells
        self._pending_n = self._pending_n + 1 if cell == self._pending else 1
        self._pending = cell
        if far or self._pending_n >= self.switch_frames:
            self.cell, self._pending, self._pending_n = cell, None, 0
        return self.center(self.cell)
