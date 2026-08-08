"""P4：感知闭环教学开关。"""
from sim_server.scene_schema import RouteLinkIn, SceneConfig
from sim_server.session import SimSession
from hmi.hmi_manager import CODE_TEACH


def _simple_scene(**kwargs) -> SceneConfig:
    base = dict(
        route_id="teach_p4",
        links=[
            RouteLinkIn(
                link_id="L1",
                points=[(0.0, 0.0), (120.0, 0.0)],
                speed_limit=10.0,
            )
        ],
        obstacles=[],
        duration_s=20.0,
    )
    base.update(kwargs)
    return SceneConfig(**base)


def test_teaching_flags_default_and_toggle():
    sess = SimSession(_simple_scene())
    sess.start()
    assert sess.status_payload()["use_truth_leads"] is True
    assert sess.status_payload()["use_est_pose_lateral"] is False

    r = sess.set_teaching_flags(use_truth_leads=False, use_est_pose_lateral=True)
    assert r["ok"] is True
    assert r["use_truth_leads"] is False
    assert r["use_est_pose_lateral"] is True
    assert any(a["code"] == CODE_TEACH for a in sess.hmi.get_active_alerts())
    snap = sess.step_once()
    assert snap is not None
    assert snap["use_truth_leads"] is False
    assert snap["use_est_pose_lateral"] is True


def test_scene_config_seeds_teaching_flags():
    sess = SimSession(
        _simple_scene(use_truth_leads=False, use_est_pose_lateral=True)
    )
    sess.start()
    assert sess._use_truth_leads is False
    assert sess._use_est_pose_lateral is True
    st = sess.status_payload()
    assert st["use_truth_leads"] is False
    assert st["use_est_pose_lateral"] is True


def test_acc_without_truth_leads_still_steps():
    """关闭真值 leads 后仿真仍可推进（ACC 走感知路径）。"""
    from sim_server.scene_schema import ObstacleIn

    scene = _simple_scene(
        use_truth_leads=False,
        obstacles=[
            ObstacleIn(x=40.0, y=0.0, width=2.0, height=4.0),
        ],
    )
    sess = SimSession(scene)
    sess.start()
    for _ in range(50):
        snap = sess.step_once()
        assert snap is not None
    assert snap["use_truth_leads"] is False


def test_set_teaching_logs_leads_cover_aeb():
    sess = SimSession(_simple_scene())
    sess.start()
    r = sess.set_teaching_flags(use_truth_leads=False)
    assert r["ok"] is True
    msgs = [a.get("msg", "") for a in sess.hmi.get_active_alerts()]
    assert any("AEB" in m or "感知" in m for m in msgs)
