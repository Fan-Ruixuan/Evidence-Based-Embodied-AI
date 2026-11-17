# -*- coding: utf-8 -*-
"""感知基线：把"场景真值"映射为候选动作 + 自我举证。

真实 VLM 可替换本模块的接口（输入图像、输出 ActionCandidate）。
内置两个基线用于消融：
  - OraclePerception：完美感知，用于检验校验器本身不误拦；
  - NoisyVLM：带漏检率 recall 与自我举证诚实度 honesty 的模拟感知，
    用于观察"校验器的收益有多依赖模型愿意承认不确定"。
"""
import random

from semantic_checker.schema import (ActionCandidate, SpatialRelation,
                                     RELATION_OCCLUDED, RELATION_VISIBLE)

CONFIDENT = 0.9


class OraclePerception(object):
    """完美感知：遮挡必报遮挡，可见则完整标注。"""

    name = "oracle"

    def perceive(self, scenario):
        # type: (object) -> ActionCandidate
        if scenario.occluded:
            rel = SpatialRelation(subject="杯子", relation=RELATION_OCCLUDED,
                                  object="书本", reference_frame="robot_view",
                                  confidence=CONFIDENT, observed=True)
        else:
            rel = SpatialRelation(subject="杯子", relation=RELATION_VISIBLE,
                                  reference_frame="robot_view",
                                  confidence=CONFIDENT, observed=True)
        return ActionCandidate(action="grasp", target="杯子", evidence=[rel])


class NoisyVLM(object):
    """模拟 VLM：遮挡漏检率 + 不确定时是否如实标注。

    recall  : P(正确报出遮挡 | 真遮挡)。漏检时会自信地声称"可见"。
    honesty : P(诚实标注字段 | 没有直接遮挡证据)。不诚实时随机漏掉
              "观测性质"或"置信度"字段——这正是规则校验器能拦下的信号。
    """

    name = "noisy_vlm"

    def __init__(self, recall=0.7, honesty=0.8, seed=0):
        self.recall = recall
        self.honesty = honesty
        self.rng = random.Random(seed)

    def perceive(self, scenario):
        # type: (object) -> ActionCandidate
        if scenario.occluded and self.rng.random() < self.recall:
            rel = SpatialRelation(subject="杯子", relation=RELATION_OCCLUDED,
                                  object="书本", reference_frame="robot_view",
                                  confidence=CONFIDENT, observed=True)
            return ActionCandidate(action="grasp", target="杯子", evidence=[rel])

        # 漏检或无遮挡：声称可见
        honest = self.rng.random() < self.honesty
        if honest:
            observed, confidence = True, CONFIDENT
        elif self.rng.random() < 0.5:
            observed, confidence = None, CONFIDENT      # 漏"观测性质"
        else:
            observed, confidence = True, None           # 漏"置信度"

        rel = SpatialRelation(subject="杯子", relation=RELATION_VISIBLE,
                              reference_frame="robot_view",
                              confidence=confidence, observed=observed)
        return ActionCandidate(action="grasp", target="杯子", evidence=[rel])


def build_perception(name, **kwargs):
    """按名称构建感知基线。"""
    if name == "oracle":
        return OraclePerception()
    if name == "noisy":
        return NoisyVLM(**kwargs)
    raise ValueError("unknown perception: {}".format(name))
