#!/usr/bin/env python3
"""
一键启动 AutoSim Web：必要时构建前端，再启动 FastAPI 并打开浏览器。

用法:
  python run_web.py              # 有 dist 直接开；没有则 npm build
  python run_web.py --rebuild    # 强制重新 build
  python run_web.py --no-browser
  python run_web.py --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DIST = WEB / "dist"
DIST_INDEX = DIST / "index.html"
VENV_PY = ROOT / ".venv" / "bin" / "python"


def _python() -> str:
    if VENV_PY.is_file():
        return str(VENV_PY)
    return sys.executable


def _in_project_venv() -> bool:
    """不能用 Path.resolve() 比 executable：venv 的 python 常是指向系统解释器的符号链接。"""
    try:
        return Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
    except OSError:
        return False


def _ensure_venv_python() -> None:
    """
    若项目有 .venv 且当前不在其中，则用 venv 重新 exec。
    避免「系统 python 跑脚本、依赖却装进 .venv」导致 ModuleNotFoundError。
    """
    if not VENV_PY.is_file():
        return
    if _in_project_venv():
        return
    want = str(VENV_PY)
    print(f"[run_web] 切换到项目虚拟环境: {want}")
    os.execv(want, [want, str(Path(__file__).resolve()), *sys.argv[1:]])


def _which_npm() -> str | None:
    found = shutil.which("npm")
    if found:
        return found
    # 本机便携 Node（此前安装路径）
    candidates = [
        Path.home() / ".local" / "node" / "bin" / "npm",
        Path("/opt/homebrew/bin/npm"),
        Path("/usr/local/bin/npm"),
    ]
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def _node_bin_dir(npm: str) -> Path:
    """
    找到与 npm 配套的 bin 目录（内含 node）。

    注意：不要对 npm 路径盲目 resolve()——便携安装里 npm 常是指向
    lib/node_modules/npm/bin/npm-cli.js 的符号链接，resolve 后的目录没有 node，
    会导致 `#!/usr/bin/env node` 报 No such file or directory。
    """
    npm_path = Path(npm)
    candidates = [npm_path.parent]
    try:
        resolved = npm_path.resolve()
        candidates.append(resolved.parent)
        # .../lib/node_modules/npm/bin/npm-cli.js → .../bin
        for parent in resolved.parents:
            bin_dir = parent / "bin"
            if (bin_dir / "node").is_file():
                candidates.append(bin_dir)
                break
    except OSError:
        pass
    for d in candidates:
        if (d / "node").is_file():
            return d
    return npm_path.parent


def _npm_env(npm: str) -> dict:
    env = os.environ.copy()
    bin_dir = str(_node_bin_dir(npm))
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def _run_npm(npm: str, args: list[str], env: dict) -> None:
    """优先用同目录 node 直接跑 npm-cli.js，避免依赖 PATH 里的 env node。"""
    bin_dir = _node_bin_dir(npm)
    node = bin_dir / "node"
    npm_cli = Path(npm).resolve()
    # 仅当 resolve 后是 JS 入口时用 node 执行；bash wrapper（部分 Homebrew）走原命令
    if node.is_file() and npm_cli.is_file() and npm_cli.suffix == ".js":
        subprocess.check_call([str(node), str(npm_cli), *args], cwd=WEB, env=env)
        return
    subprocess.check_call([npm, *args], cwd=WEB, env=env)


def ensure_web_build(rebuild: bool) -> None:
    if DIST_INDEX.is_file() and not rebuild:
        print(f"[run_web] 使用已有前端构建: {DIST}")
        return

    npm = _which_npm()
    if npm is None:
        if DIST_INDEX.is_file():
            print("[run_web] 未找到 npm，继续使用已有 web/dist")
            return
        print(
            "[run_web] 错误: 需要构建前端但未找到 npm。\n"
            "  请安装 Node.js，或将 npm 加入 PATH。\n"
            "  也可手动: cd web && npm install && npm run build"
        )
        sys.exit(1)

    print(f"[run_web] 使用 npm: {npm}")
    env = _npm_env(npm)
    if not (WEB / "node_modules").is_dir():
        print("[run_web] npm install …")
        _run_npm(npm, ["install"], env)
    print("[run_web] npm run build …")
    _run_npm(npm, ["run", "build"], env)
    if not DIST_INDEX.is_file():
        print("[run_web] 错误: build 完成但未找到 web/dist/index.html")
        sys.exit(1)
    print("[run_web] 前端构建完成")


def open_browser_later(url: str, delay: float = 1.2) -> None:
    def _open() -> None:
        time.sleep(delay)
        print(f"[run_web] 打开浏览器: {url}")
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    _ensure_venv_python()

    parser = argparse.ArgumentParser(description="一键启动 AutoSim Web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--rebuild", action="store_true", help="强制重新 npm build")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--skip-build", action="store_true", help="跳过前端构建检查")
    args = parser.parse_args()

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    if not args.skip_build:
        ensure_web_build(rebuild=args.rebuild)

    # 确保依赖可导入（已保证在 venv 内时，install 与 import 同一解释器）
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        print("[run_web] 缺少 Python 依赖，正在 pip install -r requirements.txt …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
        )
        import importlib

        importlib.invalidate_caches()
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401

    url = f"http://{args.host}:{args.port}"
    print("=" * 60)
    print(" AutoSim Web")
    print(f"  解释器  : {sys.executable}")
    print(f"  UI / API : {url}")
    print(f"  Docs     : {url}/docs")
    print(f"  启动仿真 : 浏览器点「开始」，或空格键")
    print("=" * 60)

    if not args.no_browser:
        open_browser_later(url)

    import uvicorn

    uvicorn.run(
        "sim_server.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
