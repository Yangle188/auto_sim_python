# tests/test_lane_map.py
from map.demo_lane_maps import build_highway_3lane_map, build_urban_arterial_map, get_lane_map
from map.lane_map import lanes_from_centerline, project_to_polyline


def test_highway_three_lanes_and_neighbors():
    lm = build_highway_3lane_map()
    assert lm.map_id == "highway_3lane"
    assert len(lm.lanes) == 9  # 3 sections × 3 lanes
    left = lm.get("HW_S0_L0")
    mid = lm.get("HW_S0_L1")
    right = lm.get("HW_S0_L2")
    assert left.right_lane_id == mid.lane_id
    assert mid.left_lane_id == left.lane_id
    assert mid.right_lane_id == right.lane_id
    assert left.left_marking == "solid"
    assert right.right_marking == "solid"
    assert mid.left_marking == "dashed"
    # 实线段分隔为 solid
    solid_mid = lm.get("HW_S1_L1")
    assert solid_mid.left_marking == "solid"
    assert solid_mid.right_marking == "solid"
    # successor 链
    chain = lm.follow_lane_chain("HW_S0_L1")
    assert chain == ["HW_S0_L1", "HW_S1_L1", "HW_S2_L1"]
    assert lm.get("HW_S2_L1").speed_limit == 8.0


def test_urban_has_junction_and_stop_lines():
    lm = build_urban_arterial_map()
    assert "UR_J0" in lm.junctions
    j = lm.junctions["UR_J0"]
    assert len(j.stop_lines) >= 2
    assert get_lane_map("urban_arterial") is not None
    assert "UR_TURN_EL_N" in lm.lanes
    assert "UR_NB_OUT_L1" in lm.lanes
    approach = lm.get("UR_EW0_L1")
    assert len(approach.successors) == 2
    assert approach.successors[0] == "UR_EW1_L1"
    assert approach.successors[1] == "UR_TURN_EL_N"
    straight = lm.follow_lane_chain("UR_EW0_L1", prefer_maneuver="straight")
    assert straight == ["UR_EW0_L1", "UR_EW1_L1", "UR_EW2_L1"]
    left = lm.follow_lane_chain("UR_EW0_L1", prefer_maneuver="left")
    assert left == ["UR_EW0_L1", "UR_TURN_EL_N", "UR_NB_OUT_L1"]


def test_adapter_from_centerline():
    lm = lanes_from_centerline(
        "adapt",
        [(0.0, 0.0), (100.0, 0.0)],
        num_lanes=3,
        speed_limit=10.0,
    )
    assert len(lm.lanes) == 3
    s, lat, _ = project_to_polyline(50.0, 0.0, lm.get("adapt_L1").points)
    assert abs(lat) < 0.2
    assert s > 40.0
