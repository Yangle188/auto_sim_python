# safety/aeb.py
"""FCW / AEB：独立于 ACC 的纵向安全通道。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from simulator.config import MAX_DECEL

from .config import (
    AEB_DECEL,
    AEB_DIST,
    AEB_HOLD_GAP,
    AEB_HOLD_SPEED,
    AEB_TTC,
    DEFAULT_LEAD_HALF_LENGTH,
    EGO_FRONT_LENGTH,
    EGO_LANE_LAT,
    FCW_DIST,
    FCW_TTC,
    MIN_CLOSING_SPEED,
)

Point = Tuple[float, float]

MODE_NONE = "none"
MODE_FCW = "fcw"
MODE_AEB = "aeb"


@dataclass
class AEBResult:
    mode: str = MODE_NONE
    acc: Optional[float] = None  # 盖写加速度；None 表示不盖写
    d_gap: Optional[float] = None
    ttc: Optional[float] = None
    v_rel: Optional[float] = None
    msg: str = ""
    code: str = ""


class AEBController:
    """基于本车道 lead 的 TTC / 距离分级告警与紧急制动。"""

    def __init__(
        self,
        fCW_ttc: float = FCW_TTC,
        fCW_dist: float = FCW_DIST,
        aeb_ttc: float = AEB_TTC,
        aeb_dist: float = AEB_DIST,
        aeb_decel: float = AEB_DECEL,
        ego_front: float = EGO_FRONT_LENGTH,
        lead_half: float = DEFAULT_LEAD_HALF_LENGTH,
        ego_lat: float = EGO_LANE_LAT,
    ) -> None:
        self.fcw_ttc = float(fCW_ttc)
        self.fcw_dist = float(fCW_dist)
        self.aeb_ttc = float(aeb_ttc)
        self.aeb_dist = float(aeb_dist)
        # 减速度取配置与车模上限中「不更负」者（不能超过植物限幅）
        self.aeb_decel = max(float(aeb_decel), float(MAX_DECEL))
        self.ego_front = float(ego_front)
        self.lead_half = float(lead_half)
        self.ego_lat = float(ego_lat)
        self.last: AEBResult = AEBResult()
        self._fcw_latched = False
        self._aeb_latched = False

    def reset(self) -> None:
        self.last = AEBResult()
        self._fcw_latched = False
        self._aeb_latched = False

    def evaluate(
        self,
        vehicle_state: dict,
        path: Sequence[Point],
        leads: Sequence[Any] = (),
        *,
        enabled: bool = True,
    ) -> AEBResult:
        if not enabled or len(path) < 2:
            self.last = AEBResult()
            return self.last

        x = float(vehicle_state["x"])
        y = float(vehicle_state["y"])
        v_ego = float(vehicle_state.get("speed", 0.0) or 0.0)
        ego_s, _, yaw = self._project(x, y, path)

        best = None
        best_gap = float("inf")
        for lead in leads:
            lx, ly, vx, vy, half_l = self._lead_fields(lead)
            s, lat, _ = self._project(lx, ly, path)
            if abs(lat) > self.ego_lat:
                continue
            ds = s - ego_s
            if ds < 0.5:
                continue
            # 保险杠净空
            d_gap = ds - self.ego_front - half_l
            if d_gap < best_gap:
                best_gap = d_gap
                # 沿路径切向相对速度（接近为正）
                tx, ty = math.cos(yaw), math.sin(yaw)
                v_lead_long = vx * tx + vy * ty
                v_rel = v_ego - v_lead_long  # >0 正在接近
                best = (d_gap, v_rel, v_lead_long)

        if best is None:
            # 无威胁时解除闩锁
            if v_ego < AEB_HOLD_SPEED:
                pass
            self._fcw_latched = False
            self._aeb_latched = False
            self.last = AEBResult()
            return self.last

        d_gap, v_rel, _v_lead = best
        ttc = None
        if v_rel > MIN_CLOSING_SPEED:
            ttc = d_gap / v_rel

        mode = MODE_NONE
        # AEB 条件
        aeb_hit = d_gap <= self.aeb_dist or (
            ttc is not None and ttc <= self.aeb_ttc
        )
        fcw_hit = d_gap <= self.fcw_dist or (
            ttc is not None and ttc <= self.fcw_ttc
        )

        # 已触发 AEB 且仍近距/低速 → 保持制动
        if self._aeb_latched and (
            d_gap < AEB_HOLD_GAP + 6.0 or v_ego > AEB_HOLD_SPEED
        ):
            aeb_hit = True

        if aeb_hit and (v_rel > MIN_CLOSING_SPEED or d_gap < self.aeb_dist or v_ego > AEB_HOLD_SPEED):
            mode = MODE_AEB
            self._aeb_latched = True
            self._fcw_latched = True
            acc = self.aeb_decel
            if v_ego <= AEB_HOLD_SPEED and d_gap < AEB_HOLD_GAP + 2.0:
                acc = min(acc, -1.0)
            self.last = AEBResult(
                mode=mode,
                acc=acc,
                d_gap=d_gap,
                ttc=ttc,
                v_rel=v_rel,
                msg="自动紧急制动",
                code="aeb",
            )
            return self.last

        if fcw_hit and v_rel > MIN_CLOSING_SPEED:
            mode = MODE_FCW
            self._fcw_latched = True
            self.last = AEBResult(
                mode=mode,
                acc=None,
                d_gap=d_gap,
                ttc=ttc,
                v_rel=v_rel,
                msg="请注意前方",
                code="fcw",
            )
            return self.last

        if d_gap > self.fcw_dist + 5.0 and (ttc is None or ttc > self.fcw_ttc + 1.0):
            self._fcw_latched = False
            self._aeb_latched = False

        self.last = AEBResult(d_gap=d_gap, ttc=ttc, v_rel=v_rel)
        return self.last

    def _lead_fields(self, lead: Any) -> Tuple[float, float, float, float, float]:
        if isinstance(lead, dict):
            lx = float(lead.get("x", 0.0))
            ly = float(lead.get("y", 0.0))
            vx = float(lead.get("vx", 0.0) or 0.0)
            vy = float(lead.get("vy", 0.0) or 0.0)
            half = 0.5 * float(lead.get("height", lead.get("length", self.lead_half * 2)))
            if "height" not in lead and "length" not in lead:
                half = self.lead_half
            else:
                half = max(0.5, half)
            return lx, ly, vx, vy, half
        lx = float(getattr(lead, "x", 0.0))
        ly = float(getattr(lead, "y", 0.0))
        return lx, ly, 0.0, 0.0, self.lead_half

    @staticmethod
    def _project(
        x: float, y: float, path: Sequence[Point]
    ) -> Tuple[float, float, float]:
        """返回 s, lat(左正), yaw。"""
        pts = [(float(px), float(py)) for px, py in path]
        best_s = 0.0
        best_lat = 0.0
        best_yaw = 0.0
        best_d2 = float("inf")
        cum = 0.0
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            dx, dy = x1 - x0, y1 - y0
            seg = math.hypot(dx, dy)
            if seg < 1e-12:
                continue
            tx, ty = dx / seg, dy / seg
            nx, ny = -ty, tx
            t = ((x - x0) * tx + (y - y0) * ty) / seg
            tc = max(0.0, min(1.0, t))
            px = x0 + tc * dx
            py = y0 + tc * dy
            d2 = (px - x) ** 2 + (py - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_s = cum + tc * seg
                best_lat = (x - px) * nx + (y - py) * ny
                best_yaw = math.atan2(dy, dx)
            cum += seg
        return best_s, best_lat, best_yaw
