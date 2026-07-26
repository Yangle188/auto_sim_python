import os
import json

def load_scaffold_config(json_path: str = "scaffold_config.json") -> dict:
    """加载脚手架配置json"""
    with open(json_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def build_project_scaffold(file_paths: list, skip_exist: bool, enable_log: bool):
    for filepath in file_paths:
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        if os.path.exists(filepath):
            if enable_log:
                print(f"[info] 跳过 文件已存在：{filepath}")
            continue

        with open(filepath, "w", encoding="utf-8") as f:
            pass
        if enable_log:
            print(f"[info]创建 {filepath}")

    print("\n✅ 项目脚手架构建完成！")


if __name__ == "__main__":
    config = load_scaffold_config()
    file_list = config["file_list"]
    skip_exist_file = config["skip_exist_file"]
    print_log = config["print_log"]

    build_project_scaffold(file_list, skip_exist_file, print_log)