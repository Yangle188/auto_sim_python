# localization/ekf_localizer.py
"""
4 状态自行车模型 EKF：
  状态 x = [x, y, yaw, v]
  预测：运动学自行车模型 + 控制 (acc, steer)
  更新：含噪 GPS 位置观测
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

from config import DT
from simulator.config import WHEEL_BASE, MIN_SPEED, MAX_SPEED
from .config import (
    GPS_STD_XY,
    PROCESS_VAR_X,
    PROCESS_VAR_Y,
    PROCESS_VAR_YAW,
    PROCESS_VAR_V,
    P0_VAR_X,
    P0_VAR_Y,
    P0_VAR_YAW,
    P0_VAR_V,
    GPS_RNG_SEED,
)

Matrix = List[List[float]]
Vector = List[float]


def _eye(n: int) -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _zeros(r: int, c: int) -> Matrix:
    return [[0.0] * c for _ in range(r)]


def _mat_mul(a: Matrix, b: Matrix) -> Matrix:
    rows, mid, cols = len(a), len(b), len(b[0])
    out = _zeros(rows, cols)
    for i in range(rows):
        for k in range(mid):
            aik = a[i][k]
            if aik == 0.0:
                continue
            bk = b[k]
            oi = out[i]
            for j in range(cols):
                oi[j] += aik * bk[j]
    return out


def _mat_add(a: Matrix, b: Matrix) -> Matrix:
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def _mat_sub(a: Matrix, b: Matrix) -> Matrix:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def _transpose(a: Matrix) -> Matrix:
    return [list(row) for row in zip(*a)]


def _mat_vec(a: Matrix, v: Vector) -> Vector:
    return [sum(a[i][j] * v[j] for j in range(len(v))) for i in range(len(a))]


def _invert_2x2(m: Matrix) -> Matrix:
    a, b = m[0][0], m[0][1]
    c, d = m[1][0], m[1][1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ZeroDivisionError("2x2 matrix singular in EKF update")
    inv_det = 1.0 / det
    return [[d * inv_det, -b * inv_det], [-c * inv_det, a * inv_det]]


def _normalize_angle(yaw: float) -> float:
    """归一化到 (-pi, pi]."""
    while yaw <= -math.pi:
        yaw += 2.0 * math.pi
    while yaw > math.pi:
        yaw -= 2.0 * math.pi
    return yaw


def _diag(values: Sequence[float]) -> Matrix:
    n = len(values)
    m = _zeros(n, n)
    for i, v in enumerate(values):
        m[i][i] = float(v)
    return m


class EKFLocalizer:
    """
    扩展卡尔曼定位器。
    predict(acc, steer) → 里程计传播；update_gps(x, y) → 位置修正。
    """

    def __init__(
        self,
        wheel_base: float = WHEEL_BASE,
        gps_std: float = GPS_STD_XY,
        process_vars: Optional[Sequence[float]] = None,
        p0_vars: Optional[Sequence[float]] = None,
        rng_seed: Optional[int] = GPS_RNG_SEED,
    ):
        self.wheel_base = wheel_base
        self.gps_std = gps_std
        self.Q = _diag(
            list(process_vars)
            if process_vars is not None
            else [PROCESS_VAR_X, PROCESS_VAR_Y, PROCESS_VAR_YAW, PROCESS_VAR_V]
        )
        self.R = _diag([gps_std ** 2, gps_std ** 2])
        self._p0_vars = (
            list(p0_vars)
            if p0_vars is not None
            else [P0_VAR_X, P0_VAR_Y, P0_VAR_YAW, P0_VAR_V]
        )
        self._rng = random.Random(rng_seed)
        self.x: Vector = [0.0, 0.0, 0.0, 0.0]
        self.P: Matrix = _diag(self._p0_vars)

    def reset(
        self,
        x: float = 0.0,
        y: float = 0.0,
        yaw: float = 0.0,
        speed: float = 0.0,
    ) -> None:
        self.x = [float(x), float(y), _normalize_angle(float(yaw)), float(speed)]
        self.P = _diag(self._p0_vars)

    def get_state(self) -> dict:
        """与 Vehicle.get_state / PurePursuit 兼容的字典。"""
        return {
            "x": self.x[0],
            "y": self.x[1],
            "yaw": self.x[2],
            "speed": self.x[3],
        }

    def get_covariance(self) -> Matrix:
        return [row[:] for row in self.P]

    def simulate_gps(self, true_state: dict) -> Tuple[float, float]:
        """对真值位置加高斯噪声，生成 GPS 观测。"""
        nx = self._rng.gauss(0.0, self.gps_std)
        ny = self._rng.gauss(0.0, self.gps_std)
        return true_state["x"] + nx, true_state["y"] + ny

    def predict(
        self,
        acceleration: float,
        steer_angle: float,
        dt: float = DT,
    ) -> None:
        """
        欧拉离散自行车模型预测（便于雅可比）：
          x += v cosψ dt
          y += v sinψ dt
          ψ += (v/L) tanδ dt
          v += a dt
        """
        px, py, yaw, v = self.x
        L = self.wheel_base
        c = math.cos(yaw)
        s = math.sin(yaw)
        tan_d = math.tan(steer_angle)

        # 状态传播
        x_new = px + v * c * dt
        y_new = py + v * s * dt
        yaw_new = _normalize_angle(yaw + (v / L) * tan_d * dt)
        v_new = max(MIN_SPEED, min(MAX_SPEED, v + acceleration * dt))

        # F = ∂f/∂x
        F = _eye(4)
        F[0][2] = -v * s * dt
        F[0][3] = c * dt
        F[1][2] = v * c * dt
        F[1][3] = s * dt
        F[2][3] = (tan_d / L) * dt

        self.x = [x_new, y_new, yaw_new, v_new]
        self.P = _mat_add(_mat_mul(_mat_mul(F, self.P), _transpose(F)), self.Q)

    def update_gps(self, x_meas: float, y_meas: float) -> None:
        """仅位置观测的 EKF 更新。"""
        H = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]
        z = [x_meas, y_meas]
        z_pred = [self.x[0], self.x[1]]
        y_res = [z[0] - z_pred[0], z[1] - z_pred[1]]

        PHt = _mat_mul(self.P, _transpose(H))  # 4x2
        S = _mat_add(_mat_mul(H, PHt), self.R)  # 2x2
        S_inv = _invert_2x2(S)
        K = _mat_mul(PHt, S_inv)  # 4x2
        # GPS 只观测位置：不直接修正速度，避免估计车速被位置残差“拽飞”
        # 导致状态机 ACTIVE/STANDBY 抖动
        K[3][0] = 0.0
        K[3][1] = 0.0

        dx = _mat_vec(K, y_res)
        self.x = [
            self.x[0] + dx[0],
            self.x[1] + dx[1],
            _normalize_angle(self.x[2] + dx[2]),
            self.x[3],  # 速度仅由 predict(acc) 传播
        ]

        I = _eye(4)
        KH = _mat_mul(K, H)
        self.P = _mat_mul(_mat_sub(I, KH), self.P)
