# visualize/renderer.py
"""鸟瞰 2D 可视化：matplotlib 实时刷新车辆 / 路径 / 预瞄 / 障碍 / HUD。"""
from __future__ import annotations

import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

from . import config as viz_config
from .config import (
    FIG_SIZE,
    UPDATE_EVERY_N,
    TRAIL_LENGTH,
    PAUSE_SEC,
    VIEW_PADDING,
    VEHICLE_LENGTH,
    VEHICLE_WIDTH,
    HOLD_ON_FINISH,
    PAUSE_POLL_SEC,
)

_SOURCE_COLOR = {
    "fusion": "#d62728",
    "lidar_only": "#1f77b4",
    "camera_only": "#2ca02c",
}


def _snap_get(obj: Any, name: str, default: Any = None) -> Any:
    """兼容 snapshot 中的对象或 dict。"""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class NullRenderer:
    """关闭可视化或缺少 matplotlib 时的空实现。"""

    def update(self, snapshot: Dict[str, Any]) -> None:
        return None

    def block_while_paused(self) -> None:
        return None

    def hold_until_closed(self) -> str:
        return "close"

    def prepare_replay(self) -> None:
        return None

    def consume_replay_request(self) -> bool:
        return False

    def close(self) -> None:
        return None

    @property
    def paused(self) -> bool:
        return False

    @property
    def closed(self) -> bool:
        return False


class Renderer:
    """
    matplotlib 鸟瞰渲染器。
    使用持久 artists，每帧改数据，避免反复 cla()。
    """

    def __init__(
        self,
        fig_size: Tuple[float, float] = FIG_SIZE,
        update_every_n: int = UPDATE_EVERY_N,
        trail_length: int = TRAIL_LENGTH,
        pause_sec: float = PAUSE_SEC,
        view_padding: float = VIEW_PADDING,
        hold_on_finish: bool = HOLD_ON_FINISH,
        pause_poll_sec: float = PAUSE_POLL_SEC,
    ):
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon, Rectangle

        self._plt = plt
        self._Polygon = Polygon
        self._Rectangle = Rectangle

        self.update_every_n = max(1, update_every_n)
        self.pause_sec = pause_sec
        self.view_padding = view_padding
        self.hold_on_finish = hold_on_finish
        self.pause_poll_sec = pause_poll_sec
        self._frame_count = 0
        self._closed = False
        self._paused = False
        self._holding = False
        self._replay_requested = False
        self._bounds_init = False
        self._xlim = (-10.0, 110.0)
        self._ylim = (-15.0, 15.0)
        self._base_title = (
            "AutoSim  |  Space=pause  Replay/r=replay  q=quit"
        )

        self._trail: Deque[Tuple[float, float]] = deque(maxlen=trail_length)
        self._trail_est: Deque[Tuple[float, float]] = deque(maxlen=trail_length)
        self._obstacle_patches: List[Any] = []
        self._fused_scatters: List[Any] = []
        self._pred_lines: List[Any] = []
        self._btn_replay = None

        # 交互后端才开 ion；Agg 等无头后端避免 pause 挂起
        self._interactive = self._plt.get_backend().lower() != "agg"
        if self._interactive:
            self._plt.ion()
        self.fig, self.ax = self._plt.subplots(figsize=fig_size)
        self.ax.set_aspect("equal", adjustable="box")
        self.ax.grid(True, linestyle="--", alpha=0.35)
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")
        self.ax.set_title(self._base_title)
        self.fig.subplots_adjust(bottom=0.14, right=0.98)
        if self._interactive:
            self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)
            from matplotlib.widgets import Button

            ax_btn = self.fig.add_axes([0.78, 0.02, 0.18, 0.06])
            self._btn_replay = Button(ax_btn, "Replay")
            self._btn_replay.on_clicked(self._on_replay_clicked)

        (self._line_waypoints,) = self.ax.plot(
            [], [], "s-", color="#7f7f7f", markersize=5, linewidth=1.0, label="waypoints"
        )
        self._route_link_lines: List[Any] = []
        (self._line_path,) = self.ax.plot(
            [], [], "-", color="#1f77b4", linewidth=1.2, alpha=0.85, label="dense path"
        )
        (self._line_trail,) = self.ax.plot(
            [], [], "-", color="#ff7f0e", linewidth=1.0, alpha=0.7, label="trail true"
        )
        (self._line_trail_est,) = self.ax.plot(
            [], [], "--", color="#17becf", linewidth=1.0, alpha=0.8, label="trail est"
        )
        (self._pt_lookahead,) = self.ax.plot(
            [], [], "*", color="#e377c2", markersize=14, label="lookahead"
        )
        self._ego_poly = self._Polygon(
            [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
            closed=True,
            facecolor="#ffbb78",
            edgecolor="#ff7f0e",
            linewidth=1.5,
            zorder=5,
            label="ego true",
        )
        self.ax.add_patch(self._ego_poly)
        self._ego_est_poly = self._Polygon(
            [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
            closed=True,
            facecolor="none",
            edgecolor="#17becf",
            linewidth=1.5,
            linestyle="--",
            zorder=6,
            label="ego est",
        )
        self.ax.add_patch(self._ego_est_poly)
        self._hud = self.ax.text(
            0.02,
            0.98,
            "",
            transform=self.ax.transAxes,
            va="top",
            ha="left",
            fontsize=9,
            family="monospace",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.75},
        )
        self.ax.legend(loc="lower right", fontsize=8)

    def update(self, snapshot: Dict[str, Any]) -> None:
        if self._closed:
            return

        self._frame_count += 1
        if (self._frame_count - 1) % self.update_every_n != 0:
            return

        vehicle = snapshot.get("vehicle") or {}
        x = float(vehicle.get("x", 0.0))
        y = float(vehicle.get("y", 0.0))
        yaw = float(vehicle.get("yaw", 0.0))
        speed = float(vehicle.get("speed", 0.0))

        waypoints = list(snapshot.get("waypoints") or [])
        path = list(snapshot.get("path") or [])
        lookahead = snapshot.get("lookahead")
        obstacles = list(snapshot.get("obstacles") or [])
        fused = list(snapshot.get("fused") or [])

        route_links = list(snapshot.get("route_links") or [])
        if route_links:
            self._redraw_route_links(route_links)
            self._line_waypoints.set_data([], [])
        elif waypoints:
            self._clear_route_link_lines()
            wx, wy = zip(*waypoints)
            self._line_waypoints.set_data(wx, wy)
        else:
            self._clear_route_link_lines()
            self._line_waypoints.set_data([], [])

        if path:
            px, py = zip(*path)
            self._line_path.set_data(px, py)
        else:
            self._line_path.set_data([], [])

        self._trail.append((x, y))
        if self._trail:
            tx, ty = zip(*self._trail)
            self._line_trail.set_data(tx, ty)

        vehicle_est = snapshot.get("vehicle_est")
        err_xy = None
        if vehicle_est is not None:
            ex = float(vehicle_est.get("x", 0.0))
            ey = float(vehicle_est.get("y", 0.0))
            eyaw = float(vehicle_est.get("yaw", 0.0))
            self._trail_est.append((ex, ey))
            if self._trail_est:
                etx, ety = zip(*self._trail_est)
                self._line_trail_est.set_data(etx, ety)
            self._ego_est_poly.set_xy(self._ego_triangle(ex, ey, eyaw))
            self._ego_est_poly.set_visible(True)
            err_xy = math.hypot(ex - x, ey - y)
        else:
            self._line_trail_est.set_data([], [])
            self._ego_est_poly.set_visible(False)

        if lookahead is not None:
            self._pt_lookahead.set_data([lookahead[0]], [lookahead[1]])
        else:
            self._pt_lookahead.set_data([], [])

        self._ego_poly.set_xy(self._ego_triangle(x, y, yaw))
        self._redraw_obstacles(obstacles)
        self._redraw_fused(fused)
        self._redraw_predictions(list(snapshot.get("predictions") or []))
        self._update_bounds(waypoints, path, obstacles, x, y)

        t = float(snapshot.get("t", 0.0))
        state = snapshot.get("state", "?")
        v_cmd = float(snapshot.get("v_cmd", 0.0))
        steer = float(snapshot.get("steer", 0.0))
        speed_limit = snapshot.get("speed_limit")
        if speed_limit is None:
            limit_str = "  n/a"
        else:
            limit_str = f"{float(speed_limit):5.2f}"
        err_line = f"  loc_err={err_xy:5.2f}m" if err_xy is not None else ""
        pause_tag = "  [PAUSED]" if self._paused else ""
        self._hud.set_text(
            f"t={t:5.2f}s  state={state}{pause_tag}\n"
            f"speed={speed:5.2f} m/s  v_cmd={v_cmd:5.2f}  limit={limit_str}\n"
            f"steer={math.degrees(steer):6.2f} deg  pos=({x:6.2f},{y:5.2f})"
            f"{err_line}"
        )
        self._refresh_title()

        self.ax.set_xlim(*self._xlim)
        self.ax.set_ylim(*self._ylim)
        if self._interactive:
            self.fig.canvas.draw_idle()
            if self.pause_sec > 0:
                self._plt.pause(self.pause_sec)
        else:
            # Agg / 无头：只画到 canvas，不 pause，避免测试挂起
            self.fig.canvas.draw()

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def closed(self) -> bool:
        return self._closed

    def prepare_replay(self) -> None:
        """重播前清空轨迹与暂停状态（不关窗）。"""
        self._replay_requested = False
        self._paused = False
        self._holding = False
        self._frame_count = 0
        self._bounds_init = False
        self._trail.clear()
        self._trail_est.clear()
        self._line_trail.set_data([], [])
        self._line_trail_est.set_data([], [])
        self._clear_patches(self._obstacle_patches)
        self._clear_patches(self._fused_scatters)
        self._clear_patches(self._pred_lines)
        self._clear_route_link_lines()
        self._refresh_title()
        if self._interactive and not self._closed:
            self.fig.canvas.draw_idle()

    def consume_replay_request(self) -> bool:
        """若用户请求重播则消费标志并返回 True。"""
        if not self._replay_requested:
            return False
        self._replay_requested = False
        self._paused = False
        return True

    def block_while_paused(self) -> None:
        """主循环调用：暂停期间阻塞仿真，仍处理 GUI 事件。"""
        if not self._interactive or self._closed:
            return
        while self._paused and self._fig_alive() and not self._replay_requested:
            self._refresh_title()
            self.fig.canvas.draw_idle()
            self._plt.pause(self.pause_poll_sec)
        if self._replay_requested:
            self._paused = False

    def hold_until_closed(self) -> str:
        """
        仿真结束后保持窗口。
        :return: \"replay\" 重播；\"close\" 关闭/退出
        """
        if self._closed:
            return "close"
        if not self._interactive or not self.hold_on_finish:
            self.close()
            return "close"

        self._holding = True
        self._paused = False
        self._replay_requested = False
        self._refresh_title()
        self.fig.canvas.draw_idle()
        print("[visualize] 仿真结束：点 Replay / 按 r 重播，或关窗 / q 退出")
        outcome = "close"
        try:
            while self._fig_alive():
                if self._replay_requested:
                    self._replay_requested = False
                    outcome = "replay"
                    break
                self._plt.pause(self.pause_poll_sec)
        finally:
            self._holding = False
            if outcome != "replay":
                self.close()
        return outcome

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._paused = False
        self._holding = False
        try:
            self._plt.close(self.fig)
        except Exception:
            pass

    def _request_replay(self) -> None:
        if self._closed:
            return
        self._replay_requested = True
        self._paused = False
        self._refresh_title()
        if self._interactive:
            self.fig.canvas.draw_idle()

    def _on_replay_clicked(self, _event: Any) -> None:
        self._request_replay()

    def _on_key_press(self, event: Any) -> None:
        if event is None or self._closed:
            return
        key = getattr(event, "key", None)
        if key == " ":
            if self._holding:
                return
            self._paused = not self._paused
            self._refresh_title()
            self.fig.canvas.draw_idle()
        elif key in ("r", "R"):
            self._request_replay()
        elif key in ("q", "escape"):
            if self._holding:
                self.close()
            elif self._paused:
                self._paused = False
                self._refresh_title()

    def _fig_alive(self) -> bool:
        try:
            return (not self._closed) and self.fig.number in self._plt.get_fignums()
        except Exception:
            return False

    def _refresh_title(self) -> None:
        if self._holding:
            title = "AutoSim — FINISHED  |  Replay/r 重播  |  q/关窗退出"
        elif self._paused:
            title = "AutoSim — PAUSED  |  Space=resume  Replay/r=replay"
        else:
            title = self._base_title
        self.ax.set_title(title)

    def _ego_triangle(
        self, x: float, y: float, yaw: float
    ) -> List[Tuple[float, float]]:
        """车头朝向的等腰三角形（车体坐标：前尖）。"""
        L = VEHICLE_LENGTH
        W = VEHICLE_WIDTH
        local = [
            (0.5 * L, 0.0),
            (-0.5 * L, 0.5 * W),
            (-0.5 * L, -0.5 * W),
        ]
        c, s = math.cos(yaw), math.sin(yaw)
        return [(x + c * lx - s * ly, y + s * lx + c * ly) for lx, ly in local]

    def _clear_patches(self, patches: List[Any]) -> None:
        for p in patches:
            try:
                p.remove()
            except Exception:
                pass
        patches.clear()

    def _redraw_obstacles(self, obstacles: Sequence[Any]) -> None:
        self._clear_patches(self._obstacle_patches)
        for obs in obstacles:
            ox = _snap_get(obs, "x")
            oy = _snap_get(obs, "y")
            w = _snap_get(obs, "width")
            h = _snap_get(obs, "height")
            if ox is None or oy is None or w is None or h is None:
                continue
            ox, oy, w, h = float(ox), float(oy), float(w), float(h)
            rect = self._Rectangle(
                (ox - 0.5 * w, oy - 0.5 * h),
                w,
                h,
                linewidth=1.0,
                edgecolor="#8c564b",
                facecolor="#c49c94",
                alpha=0.55,
                zorder=3,
            )
            self.ax.add_patch(rect)
            self._obstacle_patches.append(rect)

    def _redraw_fused(self, fused: Sequence[Any]) -> None:
        self._clear_patches(self._fused_scatters)
        for obs in fused:
            ox = _snap_get(obs, "x")
            oy = _snap_get(obs, "y")
            if ox is None or oy is None:
                continue
            source = _snap_get(obs, "source", "unknown")
            color = _SOURCE_COLOR.get(source, "#9467bd")
            (sc,) = self.ax.plot(
                [float(ox)],
                [float(oy)],
                "o",
                markersize=9,
                markerfacecolor="none",
                markeredgecolor=color,
                markeredgewidth=1.5,
                zorder=4,
            )
            self._fused_scatters.append(sc)

    def _redraw_predictions(self, predictions: Sequence[Any]) -> None:
        self._clear_patches(self._pred_lines)
        for pred in predictions:
            traj = _snap_get(pred, "trajectory") or ()
            if len(traj) < 2:
                continue
            xs = [float(p[0]) for p in traj]
            ys = [float(p[1]) for p in traj]
            (ln,) = self.ax.plot(
                xs,
                ys,
                "--",
                color="#9467bd",
                linewidth=1.4,
                alpha=0.85,
                zorder=4,
            )
            self._pred_lines.append(ln)

    def _clear_route_link_lines(self) -> None:
        self._clear_patches(self._route_link_lines)

    @staticmethod
    def _color_for_speed_limit(v: float, v_min: float, v_max: float) -> str:
        """限速低→橙红，高→青绿。"""
        if v_max <= v_min + 1e-9:
            t = 0.5
        else:
            t = max(0.0, min(1.0, (v - v_min) / (v_max - v_min)))
        # t=0 → #d62728, t=1 → #2ca02c
        r = int(214 + (44 - 214) * t)
        g = int(39 + (160 - 39) * t)
        b = int(40 + (44 - 40) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _redraw_route_links(self, route_links: Sequence[Any]) -> None:
        self._clear_route_link_lines()
        limits = [
            float(link.get("speed_limit", 0.0))
            for link in route_links
            if isinstance(link, dict)
        ]
        v_min = min(limits) if limits else 0.0
        v_max = max(limits) if limits else 1.0
        for i, link in enumerate(route_links):
            if not isinstance(link, dict):
                continue
            pts = list(link.get("points") or [])
            if len(pts) < 2:
                continue
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            v = float(link.get("speed_limit", 0.0))
            color = self._color_for_speed_limit(v, v_min, v_max)
            label = "route links" if i == 0 else None
            (ln,) = self.ax.plot(
                xs,
                ys,
                "s-",
                color=color,
                markersize=4,
                linewidth=2.0,
                alpha=0.9,
                zorder=2,
                label=label,
            )
            self._route_link_lines.append(ln)

    def _update_bounds(
        self,
        waypoints: List[Tuple[float, float]],
        path: List[Tuple[float, float]],
        obstacles: Sequence[Any],
        x: float,
        y: float,
    ) -> None:
        xs: List[float] = [x]
        ys: List[float] = [y]
        for px, py in waypoints:
            xs.append(px)
            ys.append(py)
        for px, py in path:
            xs.append(px)
            ys.append(py)
        for obs in obstacles:
            ox = _snap_get(obs, "x")
            oy = _snap_get(obs, "y")
            if ox is None or oy is None:
                continue
            ox, oy = float(ox), float(oy)
            w = float(_snap_get(obs, "width", 0.0) or 0.0)
            h = float(_snap_get(obs, "height", 0.0) or 0.0)
            xs.extend([ox - 0.5 * w, ox + 0.5 * w])
            ys.extend([oy - 0.5 * h, oy + 0.5 * h])

        pad = self.view_padding
        xmin, xmax = min(xs) - pad, max(xs) + pad
        ymin, ymax = min(ys) - pad, max(ys) + pad
        # 保证最小视野，避免起步时过度放大
        if xmax - xmin < 40.0:
            mid = 0.5 * (xmin + xmax)
            xmin, xmax = mid - 20.0, mid + 20.0
        if ymax - ymin < 20.0:
            mid = 0.5 * (ymin + ymax)
            ymin, ymax = mid - 10.0, mid + 10.0

        if not self._bounds_init:
            self._xlim = (xmin, xmax)
            self._ylim = (ymin, ymax)
            self._bounds_init = True
            return

        # 自车接近边界时扩展
        x0, x1 = self._xlim
        y0, y1 = self._ylim
        margin = 0.5 * pad
        if x < x0 + margin or x > x1 - margin or y < y0 + margin or y > y1 - margin:
            self._xlim = (min(x0, xmin), max(x1, xmax))
            self._ylim = (min(y0, ymin), max(y1, ymax))


def create_renderer() -> Any:
    """
    工厂：ENABLE_VISUALIZE=False 或未安装 matplotlib 时返回 NullRenderer。
    开关从 viz_config 模块属性读取，便于测试时动态关闭。
    """
    if not viz_config.ENABLE_VISUALIZE:
        return NullRenderer()
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("[visualize] matplotlib 未安装，跳过鸟瞰渲染（pip install matplotlib）")
        return NullRenderer()
    return Renderer()
