# main.py
"""CLI 入口：SimSession + matplotlib 鸟瞰（可选）。"""
from sim_server.scene_schema import default_scene_config
from sim_server.session import SimSession
from visualize.renderer import create_renderer


def _run_episode(renderer, session: SimSession | None = None) -> str:
    """
    跑一轮仿真。
    :return: \"finished\" | \"replay\" | \"closed\"
    """
    if session is None:
        session = SimSession(default_scene_config())
    else:
        session.reset()

    session.start()
    outcome = "finished"

    print("=" * 70)
    print("自动驾驶仿真系统启动")
    print("=" * 70)

    while True:
        if getattr(renderer, "closed", False):
            outcome = "closed"
            break

        renderer.block_while_paused()
        if renderer.consume_replay_request():
            outcome = "replay"
            break

        if session.status == "finished":
            break

        snap = session.step_once()
        if snap is None:
            if session.status == "finished":
                break
            continue

        renderer.update(snap)
        print(session.log_line(snap))

    session.print_summary()
    session._teardown_hmi()
    return outcome


def main():
    renderer = create_renderer()
    episode = 0
    while True:
        episode += 1
        if episode > 1:
            print(f"\n>>> 第 {episode} 次播放\n")
        renderer.prepare_replay()
        outcome = _run_episode(renderer)

        if outcome == "closed":
            break
        if outcome == "replay":
            continue

        hold = renderer.hold_until_closed()
        if hold != "replay":
            break


if __name__ == "__main__":
    main()
