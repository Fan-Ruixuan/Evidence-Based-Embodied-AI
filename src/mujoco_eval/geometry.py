# -*- coding: utf-8 -*-
"""几何真值：用 MuJoCo 射线求杯子在相机视角下的可见比例。

不依赖 VLM、也不依赖渲染：从相机向杯子表面采样点发射射线，
若第一个命中体不是杯子，则该采样点被遮挡。可见比例 < 阈值即判为遮挡。
"""
import math

import mujoco
import numpy as np

from .scene import CUP_RADIUS, CUP_CENTER


def build_model(book_xy, camera_pos):
    """由场景描述构建 MjModel（静态场景，无需 step）。"""
    from .scene import scene_xml
    return mujoco.MjModel.from_xml_string(scene_xml(book_xy, camera_pos))


def cup_sample_points(n_ring=12):
    """杯子表面采样点：顶沿、中部环、顶面中心。"""
    cx, cy, cz = CUP_CENTER
    pts = [np.array([cx, cy, cz + CUP_RADIUS * 0 + 0.0])]  # 顶面中心（杯口）
    for k in range(n_ring):
        a = 2.0 * math.pi * k / n_ring
        dx, dy = CUP_RADIUS * math.cos(a), CUP_RADIUS * math.sin(a)
        pts.append(np.array([cx + dx, cy + dy, cz]))                      # 顶沿
        pts.append(np.array([cx + dx, cy + dy, cz - CUP_RADIUS * 0.8]))   # 中部环
    return np.array(pts)


def visibility_ratio(model, data, sample_points, camera_name="vlm_cam"):
    """返回杯子采样点中"第一命中体是杯子"的比例（0~1）。"""
    cam_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, camera_name)
    cup_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "cup_geom")
    cam_pos = np.array(data.cam_xpos[cam_id], dtype=np.float64)

    visible = 0
    geomid = np.array([-1], dtype=np.int32)
    geomgroup = np.ones(6, dtype=np.uint8)  # 启用全部几何组；None 会禁用所有碰撞组
    for p in sample_points:
        vec = p - cam_pos
        dist = float(np.linalg.norm(vec))
        if dist < 1e-8:
            continue
        vec = vec / dist
        hit = mujoco.mj_ray(model, data, cam_pos, vec, geomgroup, 1, -1, geomid)
        # 第一条命中的几何体是杯子 -> 该方向上杯子可见（被书挡住则首个命中是书）
        if geomid[0] == cup_geom:
            visible += 1
    return visible / float(len(sample_points))


def is_occluded(ratio, threshold=0.5):
    """可见比例低于阈值即视为遮挡目标。"""
    return ratio < threshold


def camera_position(azimuth_deg, distance=0.80, elevation_deg=8.0,
                    target=CUP_CENTER):
    """绕目标点的球面相机位置。"""
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return (
        target[0] + distance * math.cos(el) * math.cos(az),
        target[1] + distance * math.cos(el) * math.sin(az),
        target[2] + distance * math.sin(el),
    )
