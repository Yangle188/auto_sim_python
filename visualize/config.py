# visualize/config.py
# 是否启用鸟瞰可视化（False 时 main 跳过渲染）
ENABLE_VISUALIZE = True

# 图像尺寸（英寸）
FIG_SIZE = (10.0, 6.0)

# 每隔多少仿真帧刷新一次画面（1 = 每帧）
UPDATE_EVERY_N = 2

# 自车历史轨迹保留点数
TRAIL_LENGTH = 80

# 交互刷新暂停秒数（0 表示尽量快；有 GUI 时可略大于 0）
PAUSE_SEC = 0.001

# 坐标轴相对场景边界的边距（m）
VIEW_PADDING = 8.0

# 自车外形与车道宽度：与 simulator 保持一致（后轴中心为参考点）
from simulator.config import (  # noqa: E402
    LANE_WIDTH,
    REAR_OVERHANG,
    VEHICLE_LENGTH,
    VEHICLE_WIDTH,
)

# 仿真结束后是否保持窗口，直到用户关闭（或按 q）
HOLD_ON_FINISH = True

# 空格暂停时事件轮询间隔（s）
PAUSE_POLL_SEC = 0.05
