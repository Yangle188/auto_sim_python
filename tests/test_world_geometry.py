# tests/test_world_geometry.py
import math

from simulator.config import LANE_WIDTH, REAR_OVERHANG, VEHICLE_LENGTH, VEHICLE_WIDTH
from simulator.geometry import ego_footprint_world, lane_boundaries, offset_polyline
from simulator.world import SimulationWorld


def test_lane_and_vehicle_constants():
    assert LANE_WIDTH == 3.2
    assert VEHICLE_WIDTH == 1.96
    assert VEHICLE_WIDTH < LANE_WIDTH


def test_lane_boundaries_width():
    center = [(0.0, 0.0), (10.0, 0.0)]
    lane = lane_boundaries(center, LANE_WIDTH)
    half = LANE_WIDTH / 2.0
    # 直线车道：左右边界应在 y=±half
    assert abs(lane["left"][0][1] - half) < 1e-9
    assert abs(lane["right"][0][1] + half) < 1e-9
    assert abs(lane["left"][1][1] - half) < 1e-9


def test_offset_preserves_length_approx():
    pts = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)]
    left = offset_polyline(pts, 1.6)
    assert len(left) == 3
    assert left[0][1] > 0


def test_ego_footprint_rear_axle_origin():
    """后轴在原点时，矩形应跨过后轴且宽度为 VEHICLE_WIDTH。"""
    corners = ego_footprint_world(0.0, 0.0, 0.0)
    ys = [c[1] for c in corners]
    xs = [c[0] for c in corners]
    assert abs(max(ys) - VEHICLE_WIDTH / 2) < 1e-9
    assert abs(min(ys) + VEHICLE_WIDTH / 2) < 1e-9
    assert min(xs) == -REAR_OVERHANG
    assert abs(max(xs) - (VEHICLE_LENGTH - REAR_OVERHANG)) < 1e-9


def test_ego_footprint_rotated():
    corners = ego_footprint_world(10.0, 5.0, math.pi / 2)
    # yaw=90°：车头朝 +y，后轴 (10,5)；宽沿 x
    xs = [c[0] for c in corners]
    assert abs(max(xs) - (10.0 + VEHICLE_WIDTH / 2)) < 1e-9
    assert abs(min(xs) - (10.0 - VEHICLE_WIDTH / 2)) < 1e-9


def test_world_lane_and_geom_api():
    world = SimulationWorld()
    world.set_reference_path([(0.0, 0.0), (40.0, 0.0)])
    assert world.lane_width == 3.2
    lane = world.get_lane_boundaries()
    assert len(lane["left"]) == 2
    geom = world.get_vehicle_geom()
    assert geom["width"] == 1.96
    assert geom["ref_point"] == "rear_axle"
    assert world.vehicle.get_state()["ref_point"] == "rear_axle"
