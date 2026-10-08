# -*- coding: utf-8 -*-
"""数据结构：空间关系元组与动作候选。

设计原则（总纲 3.3）：自由文本必须先变成结构化空间关系，
且"可信度、观测性质"必须入结构——令模型先自我举证。
"""
from dataclasses import dataclass, field
from typing import List, Optional

# 关系类型（阶段一仅覆盖演示所需的最小集合）
RELATION_VISIBLE = "visible"        # 目标可见
RELATION_OCCLUDED = "occluded"      # 目标被遮挡
RELATION_ON = "on"                  # 在...之上
RELATION_UNDER = "under"            # 在...之下
RELATION_BEHIND = "behind"          # 在...之后
RELATION_LEFT_OF = "left_of"        # 在...左边
RELATION_RIGHT_OF = "right_of"      # 在...右边

# 方向性关系：必须显式声明参考坐标系，否则视为"参考系混淆"
DIRECTIONAL_RELATIONS = {RELATION_LEFT_OF, RELATION_RIGHT_OF,
                         RELATION_BEHIND, RELATION_UNDER}

# 参考坐标系：unknown 表示未声明（校验规则会拦截）
FRAME_UNKNOWN = "unknown"


@dataclass
class SpatialRelation:
    """空间关系元组：一次证据陈述的最小单位。"""

    subject: str                       # 实体，如 "杯子"
    relation: str                      # 关系类型，见 RELATION_*
    object: str = ""                   # 关系对象，如遮挡物 "书本"
    reference_frame: str = FRAME_UNKNOWN  # 参考坐标系：robot_view / table / world / self
    confidence: Optional[float] = None # 可信度 0~1；None 表示未标注（不允许的缺省）
    observed: Optional[bool] = None    # 观测性质：True=亲眼所见，False=推测；None=未标注

    def is_about(self, target: str) -> bool:
        """该证据是否与目标实体相关。"""
        return self.subject == target or (self.object == target and self.relation != RELATION_OCCLUDED)


@dataclass
class ActionCandidate:
    """规划器产出的候选动作，必须携带证据元组。"""

    action: str                        # 动作类型，如 "grasp" / "move_to"
    target: str                        # 动作目标实体
    evidence: List[SpatialRelation] = field(default_factory=list)

    def evidence_about_target(self) -> List[SpatialRelation]:
        """与动作目标直接相关的证据。"""
        return [e for e in self.evidence if e.is_about(self.target)]


@dataclass
class Verdict:
    """校验结论：放行 / 拦截，附带原因与定向修正建议。"""

    passed: bool
    rule_id: str = ""                  # 命中的规则；放行时为 "PASS"
    reason: str = ""
    suggestion: str = ""
    blocked_by_rule: bool = False      # True=规则硬拦截；False=语义模型柔性复核拦截
    circuit_open: bool = False         # True=熔断触发，未进入实际校验

    def __str__(self) -> str:
        if self.passed:
            return "[放行] 证据合规"
        tag = "熔断" if self.circuit_open else ("规则拦截" if self.blocked_by_rule else "复核拦截")
        msg = "[{}] {}".format(tag, self.reason)
        if self.suggestion:
            msg += " | 修正建议：{}".format(self.suggestion)
        return msg
