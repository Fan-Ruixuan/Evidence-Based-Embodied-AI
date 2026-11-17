# -*- coding: utf-8 -*-
"""MuJoCo 场景与几何真值的冒烟测试。

无 MuJoCo 环境时整组跳过，保证 `python -m unittest ...` 在纯文本环境也能跑。
"""
import unittest

try:
    import mujoco  # noqa: F401
    HAS_MUJOCO = True
except ImportError:  # pragma: no cover
    HAS_MUJOCO = False


@unittest.skipUnless(HAS_MUJOCO, "未安装 mujoco，跳过仿真测试")
class TestGeometryTruth(unittest.TestCase):

    def _ratio(self, book_xy):
        import mujoco
        from mujoco_eval.geometry import (build_model, camera_position,
                                          cup_sample_points, visibility_ratio)
        model = build_model(book_xy, camera_position(0))
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        return visibility_ratio(model, data, cup_sample_points())

    def test_book_between_camera_and_cup_occludes(self):
        # 相机在 +x 方向，书放在杯子与相机之间
        self.assertLess(self._ratio((0.16, 0.0)), 0.5)

    def test_book_beside_cup_does_not_occlude(self):
        # 书放在侧面，杯子应完整可见
        self.assertGreaterEqual(self._ratio((0.0, 0.30)), 0.95)


if __name__ == "__main__":
    unittest.main()
