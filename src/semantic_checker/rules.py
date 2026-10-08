# -*- coding: utf-8 -*-
"""确定性规则集（阶段一，零训练）。

四条规则对应总纲 3.1 的三类典型病灶：
  R1 遮挡误判（看不见当不存在）     -> VisibilityRule
  R2 参考系混淆（"左边"是谁的左边） -> ReferenceFrameRule
  R3/R4 证据不足强行规划            -> EvidenceSufficiencyRule / ConfidenceRule

每条规则只做确定性检查，不做任何学习/推断；拦截时必带定向修正建议。
"""
from typing import List, Optional

from .schema import (ActionCandidate, SpatialRelation,
                     DIRECTIONAL_RELATIONS, FRAME_UNKNOWN,
                     RELATION_OCCLUDED, RELATION_VISIBLE)

LOW_CONFIDENCE_THRESHOLD = 0.5  # 低于该值的证据视为不可靠（可配置）


class RuleResult(object):
    def __init__(self, passed, reason="", suggestion=""):
        # type: (bool, str, str) -> None
        self.passed = passed
        self.reason = reason
        self.suggestion = suggestion


class Rule(object):
    rule_id = "BASE"

    def check(self, action):
        # type: (ActionCandidate) -> RuleResult
        raise NotImplementedError


class VisibilityRule(Rule):
    """R1 遮挡误判：目标必须有"亲眼所见且带置信度"的可见证据。

    拦截三种情形：
      a) 证据明确指出目标被遮挡 -> 禁止抓取，建议先移开遮挡物；
      b) 目标声称可见，但缺观测性质或缺置信度 -> "遮挡"字段缺失，先自我举证；
      c) 目标声称可见但为推测（observed=False）-> 看不见当不存在。
    """

    rule_id = "R1_VISIBILITY"

    def check(self, action):
        # type: (ActionCandidate) -> RuleResult
        related = action.evidence_about_target()
        visible_evidence = [e for e in related if e.relation == RELATION_VISIBLE]

        # a) 明确遮挡
        for e in related:
            if e.relation == RELATION_OCCLUDED:
                occluder = e.object or "未知物体"
                return RuleResult(
                    False,
                    reason="目标「{}」被遮挡（遮挡物：{}），禁止执行 {}".format(
                        action.target, occluder, action.action),
                    suggestion="先移开遮挡物「{}」，确认可见后重新规划".format(occluder),
                )

        # b/c) 可见性声称不可靠
        for e in visible_evidence:
            if e.observed is None:
                return RuleResult(
                    False,
                    reason="目标「{}」的可见性声称缺少观测性质字段（亲眼所见/推测未标注）".format(action.target),
                    suggestion="补充观测性质与置信度后重报；未自我举证前不受理",
                )
            if e.confidence is None:
                return RuleResult(
                    False,
                    reason="目标「{}」的可见性声称缺少置信度字段".format(action.target),
                    suggestion="为可见性证据补充置信度后重报",
                )
            if e.observed is False:
                return RuleResult(
                    False,
                    reason="目标「{}」的可见性为推测而非亲眼所见，拒绝凭推测执行 {}".format(
                        action.target, action.action),
                    suggestion="先移动视角确认目标可见，或改走熔断交还人工",
                )

        if not visible_evidence:
            # 情形合并进 R3：目标完全无可见性证据由 EvidenceSufficiencyRule 处理
            return RuleResult(True)
        return RuleResult(True)


class ReferenceFrameRule(Rule):
    """R2 参考系混淆：方向性关系必须显式声明参考坐标系。"""

    rule_id = "R2_REFERENCE_FRAME"

    def check(self, action):
        # type: (ActionCandidate) -> RuleResult
        for e in action.evidence:  # type: SpatialRelation
            if e.relation in DIRECTIONAL_RELATIONS and e.reference_frame == FRAME_UNKNOWN:
                return RuleResult(
                    False,
                    reason="证据「{} {} {}」为方向性关系但未声明参考坐标系".format(
                        e.subject, e.relation, e.object or ""),
                    suggestion="明确参考系（robot_view / table / world / self）后重报，"
                               "避免「左边」是机器人还是桌面的混淆",
                )
        return RuleResult(True)


class EvidenceSufficiencyRule(Rule):
    """R3 证据不足强行规划：候选动作必须至少携带一条与目标相关的证据。"""

    rule_id = "R3_EVIDENCE_SUFFICIENCY"

    def check(self, action):
        # type: (ActionCandidate) -> RuleResult
        if not action.evidence_about_target():
            return RuleResult(
                False,
                reason="候选动作「{} {}」没有任何与目标相关的空间证据，属证据不足强行规划".format(
                    action.action, action.target),
                suggestion="先由 VLM 输出结构化空间元组（含观测性质与置信度）再发起动作",
            )
        return RuleResult(True)


class ConfidenceRule(Rule):
    """R4 低置信度：目标证据的可信度不得低于阈值。"""

    rule_id = "R4_CONFIDENCE"

    def __init__(self, threshold=LOW_CONFIDENCE_THRESHOLD):
        # type: (float) -> None
        self.threshold = threshold

    def check(self, action):
        # type: (ActionCandidate) -> RuleResult
        related = [e for e in action.evidence_about_target()
                   if e.confidence is not None]
        if related and all(e.confidence < self.threshold for e in related):
            worst = min(e.confidence for e in related)
            return RuleResult(
                False,
                reason="目标「{}」全部证据置信度过低（最低 {:.2f} < 阈值 {:.2f}）".format(
                    action.target, worst, self.threshold),
                suggestion="补充更可靠观测，或承认看不清、走熔断交还人工",
            )
        return RuleResult(True)


DEFAULT_RULES = [VisibilityRule(), ReferenceFrameRule(),
                 EvidenceSufficiencyRule(), ConfidenceRule()]  # type: List[Rule]
