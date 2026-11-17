# -*- coding: utf-8 -*-
"""命令行入口：跑仿真实验、渲染示例图、输出指标。

用法：
    python src/mujoco_eval/run.py
    python src/mujoco_eval/run.py --render
"""
import argparse
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import mujoco

from mujoco_eval.evaluate import (build_scenarios, render_markdown, run_all,
                                  write_csv)
from mujoco_eval.geometry import build_model, camera_position
from mujoco_eval.scene import CUP_CENTER


def render_example(book_angle_deg, book_distance, camera_azimuth, out_path):
    """渲染一张示例图（需要可用的 OpenGL 上下文）。"""
    import numpy as np
    from PIL import Image

    cam_pos = camera_position(camera_azimuth)
    rad = np.radians(book_angle_deg)
    book_xy = (book_distance * np.cos(rad), book_distance * np.sin(rad))
    model = build_model(book_xy, cam_pos)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    renderer = mujoco.Renderer(model, height=480, width=640)
    try:
        renderer.update_scene(data, camera="vlm_cam")
        Image.fromarray(renderer.render()).save(out_path)
    finally:
        renderer.close()


def main():
    parser = argparse.ArgumentParser(description="MuJoCo 遮挡场景批量评估")
    parser.add_argument("--out-dir", default="experiments",
                        help="指标与报告输出目录（默认 experiments）")
    parser.add_argument("--render", action="store_true",
                        help="额外渲染遮挡/可见示例图到 assets/sim/")
    args = parser.parse_args()

    scenarios = build_scenarios()
    n_occ = sum(1 for s in scenarios if s.occluded)
    n_vis = len(scenarios) - n_occ
    print("场景总数 {}：遮挡 {} / 可见 {}".format(len(scenarios), n_occ, n_vis))

    rows = run_all(scenarios)
    os.makedirs(args.out_dir, exist_ok=True)
    write_csv(rows, os.path.join(args.out_dir, "sim_metrics.csv"))

    report = render_markdown(rows, len(scenarios), n_occ, n_vis)
    report_path = os.path.join(args.out_dir, "sim_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)
    print("CSV -> {}".format(os.path.join(args.out_dir, "sim_metrics.csv")))
    print("报告 -> {}".format(report_path))

    if args.render:
        assets = Path("assets/sim")
        assets.mkdir(parents=True, exist_ok=True)
        occluded = next(s for s in scenarios if s.ratio == 0.0)
        visible = next(s for s in scenarios if s.ratio == 1.0)
        render_example(occluded.azimuth + occluded.book_angle,
                       occluded.book_distance, occluded.azimuth,
                       str(assets / "occluded.png"))
        render_example(visible.azimuth + visible.book_angle,
                       visible.book_distance, visible.azimuth,
                       str(assets / "visible.png"))
        print("示例图 -> {}".format(assets))


if __name__ == "__main__":
    main()
