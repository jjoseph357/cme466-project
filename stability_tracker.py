"""
BBox-based posture stability: movement resets how long we've seen a stable pose.
Alarm only when posture is bad, bbox is stable, and that state held for a duration.
"""

from __future__ import annotations

from typing import Any


def bbox_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return inter / union


class PostureStabilityTracker:
    def __init__(
        self,
        stable_bad_seconds: float,
        min_iou_for_stable: float,
        bad_label: str = "sitting_bad_posture",
    ):
        self.stable_bad_seconds = stable_bad_seconds
        self.min_iou_for_stable = min_iou_for_stable
        self.bad_label = bad_label
        self._prev_bbox: list[float] | None = None
        self._stable_since: float | None = None

    def update(self, label: str, bbox: list[float] | None, t: float) -> dict[str, Any]:
        no_pose = bbox is None or label == "No posture detected"

        if no_pose:
            self._prev_bbox = None
            self._stable_since = None
            return {
                "posture_changing": True,
                "stable_duration_sec": 0.0,
                "alarm": False,
            }

        posture_changing = True
        if self._prev_bbox is not None:
            iou_val = bbox_iou(self._prev_bbox, bbox)
            posture_changing = iou_val < self.min_iou_for_stable

        self._prev_bbox = [float(x) for x in bbox]

        if posture_changing:
            self._stable_since = None
            return {
                "posture_changing": True,
                "stable_duration_sec": 0.0,
                "alarm": False,
            }

        if self._stable_since is None:
            self._stable_since = t

        stable_duration = t - self._stable_since
        is_bad = label == self.bad_label
        alarm = is_bad and stable_duration >= self.stable_bad_seconds

        return {
            "posture_changing": False,
            "stable_duration_sec": stable_duration,
            "alarm": alarm,
        }
