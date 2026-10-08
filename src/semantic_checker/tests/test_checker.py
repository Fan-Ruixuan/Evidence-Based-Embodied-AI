# -*- coding: utf-8 -*-
"""零训练规则校验器单元测试（unittest 风格，pytest 同样可直接运行）。

覆盖：四条规则各自的拦截与放行边界、熔断开关、LLM 柔性复核钩子、
以及阶段一文本模拟解析器。

运行：
    python -m unittest discover -s src/semantic_checker/tests -t src -v
    # 或 pytest src/semantic_checker/tests -q
"""
import unittest

from semantic_checker.checker import SemanticChecker
from semantic_checker.parser import parse_action
from semantic_checker.schema import ActionCandidate, SpatialRelation


def relation(subject, rel, obj="", frame="unknown", conf=None, observed=None):
    return SpatialRelation(subject=subject, relation=rel, object=obj,
                           reference_frame=frame, confidence=conf, observed=observed)


def good_action():
    """完整证据的标准放行动作。"""
    return ActionCandidate("grasp", "杯子",
                           [relation("杯子", "visible", frame="table",
                                     conf=0.9, observed=True)])


class TestVisibilityRule(unittest.TestCase):
    """R1 遮挡误判（看不见当不存在）。"""

    def test_pass_with_complete_evidence(self):
        v = SemanticChecker().check(good_action())
        self.assertTrue(v.passed)
        self.assertEqual(v.rule_id, "PASS")

    def test_explicit_occlusion_blocked_with_suggestion(self):
        action = ActionCandidate("grasp", "杯子",
                                 [relation("杯子", "occluded", obj="书本")])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertTrue(v.blocked_by_rule)
        self.assertEqual(v.rule_id, "R1_VISIBILITY")
        self.assertIn("书本", v.suggestion)  # 定向修正建议必须指名遮挡物

    def test_hedged_visibility_blocked(self):
        # "应该可见" -> observed=False（推测），不允许凭推测伸手
        action = ActionCandidate("grasp", "杯子",
                                 [relation("杯子", "visible", conf=0.9, observed=False)])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertIn("推测", v.reason)

    def test_missing_observed_field_blocked(self):
        action = ActionCandidate("grasp", "杯子",
                                 [relation("杯子", "visible", conf=0.9)])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertIn("观测性质", v.reason)

    def test_missing_confidence_field_blocked(self):
        action = ActionCandidate("grasp", "杯子",
                                 [relation("杯子", "visible", observed=True)])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertIn("置信度", v.reason)


class TestReferenceFrameRule(unittest.TestCase):
    """R2 参考系混淆（"左边"是谁的左边）。"""

    def test_directional_relation_without_frame_blocked(self):
        action = ActionCandidate("grasp", "积木",
                                 [relation("积木", "left_of", obj="水杯",
                                           conf=0.9, observed=True)])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertEqual(v.rule_id, "R2_REFERENCE_FRAME")

    def test_directional_relation_with_frame_passes(self):
        action = ActionCandidate("grasp", "积木",
                                 [relation("积木", "left_of", obj="水杯", frame="table",
                                           conf=0.9, observed=True)])
        self.assertTrue(SemanticChecker().check(action).passed)


class TestEvidenceSufficiencyRule(unittest.TestCase):
    """R3 证据不足强行规划。"""

    def test_no_evidence_blocked(self):
        v = SemanticChecker().check(ActionCandidate("grasp", "工具箱", []))
        self.assertFalse(v.passed)
        self.assertEqual(v.rule_id, "R3_EVIDENCE_SUFFICIENCY")

    def test_irrelevant_evidence_blocked(self):
        # 证据存在但与目标无关，视同证据不足
        action = ActionCandidate("grasp", "杯子",
                                 [relation("遥控器", "visible", conf=0.9, observed=True)])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertEqual(v.rule_id, "R3_EVIDENCE_SUFFICIENCY")


class TestConfidenceRule(unittest.TestCase):
    """R4 低置信度证据。"""

    def test_low_confidence_blocked(self):
        action = ActionCandidate("grasp", "杯子",
                                 [relation("杯子", "visible", conf=0.3, observed=True)])
        v = SemanticChecker().check(action)
        self.assertFalse(v.passed)
        self.assertEqual(v.rule_id, "R4_CONFIDENCE")


class TestCircuitBreaker(unittest.TestCase):
    """熔断：连续失败达阈值即拦下一切，一次放行即清零。"""

    def test_opens_after_consecutive_failures(self):
        checker = SemanticChecker(circuit_threshold=2)
        bad = ActionCandidate("grasp", "工具箱", [])
        for _ in range(2):
            self.assertFalse(checker.check(bad).passed)
        # 第 3 次：动作本身合规也被熔断拦下
        v = checker.check(good_action())
        self.assertFalse(v.passed)
        self.assertTrue(v.circuit_open)

    def test_success_resets_failure_count(self):
        checker = SemanticChecker(circuit_threshold=2)
        self.assertFalse(checker.check(ActionCandidate("grasp", "工具箱", [])).passed)
        self.assertTrue(checker.check(good_action()).passed)      # 计数清零
        self.assertFalse(checker.check(ActionCandidate("grasp", "工具箱", [])).passed)
        self.assertFalse(checker.check(ActionCandidate("grasp", "工具箱", [])).passed)
        self.assertTrue(checker.check(ActionCandidate("grasp", "工具箱", [])).circuit_open)


class TestLlmRecheckHook(unittest.TestCase):
    """LLM 柔性复核钩子：规则通过后模型仍可拦截。"""

    def test_recheck_can_block_after_rules_pass(self):
        def strict_recheck(action):
            return False, "复核认为目标区域光线不足"

        checker = SemanticChecker(llm_recheck=strict_recheck)
        v = checker.check(good_action())
        self.assertFalse(v.passed)
        self.assertFalse(v.blocked_by_rule)
        self.assertIn("光线不足", v.reason)

    def test_recheck_pass_keeps_verdict_clean(self):
        checker = SemanticChecker(llm_recheck=lambda a: (True, ""))
        self.assertTrue(checker.check(good_action()).passed)


class TestParser(unittest.TestCase):
    """阶段一文本模拟解析器。"""

    def test_extracts_occlusion(self):
        action = parse_action("杯子被书本挡住了，抓取杯子")
        self.assertIsNotNone(action)
        self.assertEqual(action.action, "grasp")
        self.assertEqual(action.target, "杯子")
        occluded = [e for e in action.evidence if e.relation == "occluded"]
        self.assertEqual(len(occluded), 1)
        self.assertEqual(occluded[0].object, "书本")

    def test_marks_hedged_claim_as_unobserved(self):
        action = parse_action("杯子应该可见，抓取杯子")
        visible = [e for e in action.evidence if e.relation == "visible"]
        self.assertTrue(visible)
        self.assertIs(visible[0].observed, False)

    def test_leaves_unannotated_fields_empty(self):
        action = parse_action("杯子可见，抓取杯子")
        visible = [e for e in action.evidence if e.relation == "visible"]
        self.assertTrue(visible)
        self.assertIsNone(visible[0].observed)
        self.assertIsNone(visible[0].confidence)

    def test_reads_confidence_and_frame(self):
        action = parse_action("以桌面为准，亲眼看见杯子可见，置信度0.9。抓取杯子")
        visible = [e for e in action.evidence if e.relation == "visible"]
        self.assertTrue(visible)
        self.assertEqual(visible[0].confidence, 0.9)
        self.assertIs(visible[0].observed, True)

    def test_subject_not_polluted_by_prefix(self):
        # 回归：前缀"亲眼看见"不得混入 subject，否则证据关联失败
        action = parse_action("亲眼看见杯子可见，置信度0.9。抓取杯子")
        visible = [e for e in action.evidence if e.relation == "visible"]
        self.assertTrue(visible)
        self.assertEqual(visible[0].subject, "杯子")


if __name__ == "__main__":
    unittest.main()
