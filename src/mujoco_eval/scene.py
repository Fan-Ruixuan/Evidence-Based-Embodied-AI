# -*- coding: utf-8 -*-
"""MuJoCo 桌面场景：桌面 + 杯子 + 书本 + 相机。

不依赖任何外部网格资源，场景完全由 MJCF 基本几何体构成，
保证任何人 clone 后可直接复现（无需下载模型库）。
"""
import math

CUP_RADIUS = 0.045
CUP_HALF_HEIGHT = 0.06
TABLE_TOP_Z = 0.60
CUP_CENTER = (0.0, 0.0, TABLE_TOP_Z + CUP_HALF_HEIGHT)

BOOK_HALF = (0.10, 0.07, 0.05)  # 一摞书，约 10cm 高，足以在低视角下遮挡杯子


def _look_at_xyaxes(pos, target):
    """计算相机 xyaxes：MuJoCo 相机沿自身 -Z 看，+Y 为上。"""
    fx, fy, fz = target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]
    n = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx / n, fy / n, fz / n
    zx, zy, zz = -fx, -fy, -fz            # 相机 +Z 指向视线反方向
    # x = up × z，up=(0,0,1)
    xx, xy, xz = -zy, zx, 0.0
    m = math.sqrt(xx * xx + xy * xy + xz * xz)
    xx, xy, xz = xx / m, xy / m, xz / m
    # y = z × x
    yx, yy, yz = zy * xz - zz * xy, zz * xx - zx * xz, zx * xy - zy * xx
    return " ".join("{:.6f}".format(v) for v in (xx, xy, xz, yx, yy, yz))


def scene_xml(book_xy, camera_pos, camera_target=CUP_CENTER, camera_name="vlm_cam"):
    """生成单帧场景 XML。书本只做视觉遮挡，不参与动力学仿真。"""
    bx, by = book_xy
    bz = TABLE_TOP_Z + BOOK_HALF[2]
    xyaxes = _look_at_xyaxes(camera_pos, camera_target)
    return """
<mujoco model="occlusion_scene">
  <visual>
    <global offwidth="640" offheight="480"/>
    <quality shadowsize="2048"/>
  </visual>
  <worldbody>
    <light name="key" pos="0.4 -0.4 1.4" dir="-0.4 0.4 -1" diffuse="0.8 0.8 0.8"/>
    <light name="fill" pos="-0.5 0.5 1.2" dir="0.5 -0.5 -1" diffuse="0.35 0.35 0.35"/>
    <geom name="floor" type="plane" size="2 2 0.05" rgba="0.55 0.58 0.62 1"/>
    <geom name="table" type="box" size="0.6 0.45 0.025" pos="0 0 0.575"
          rgba="0.72 0.62 0.50 1"/>
    <body name="cup" pos="0 0 {cup_z}">
      <geom name="cup_geom" type="cylinder" size="{r} {h}" rgba="0.90 0.90 0.92 1"/>
    </body>
    <body name="book" pos="{bx} {by} {bz}">
      <geom name="book_geom" type="box" size="{bhx} {bhy} {bhz}" rgba="0.20 0.38 0.72 1"/>
    </body>
    <camera name="{cam}" pos="{cx} {cy} {cz}" xyaxes="{axes}" fovy="45"/>
  </worldbody>
</mujoco>
""".format(
        cup_z=CUP_CENTER[2], r=CUP_RADIUS, h=CUP_HALF_HEIGHT,
        bx=bx, by=by, bz=bz,
        bhx=BOOK_HALF[0], bhy=BOOK_HALF[1], bhz=BOOK_HALF[2],
        cam=camera_name,
        cx=camera_pos[0], cy=camera_pos[1], cz=camera_pos[2],
        axes=xyaxes,
    )
