# -*- coding: utf-8 -*-
"""前置语义校验器：双轨校验 + 定向修正 + 熔断。

流程（总纲 3.3 + README 架构图）：
  候选动作 -> [熔断检查] -> [规则硬拦截] -> [语义模型柔性复核(可选)] -> 放行
                              | 拦截                    | 拦截
                              v                        v
                        记录失败计数 + 带原因与修正建议回传
                        连续失败 >= 阈值 -> 熔断，交还人工

阶段一中"语义模型柔性复核"是可注入的钩子（llm_recheck），默认为 None
即纯规则模式；接入真实 LLM 时传入 callable(ActionCandidate) -> (ok, reason)。
"""
from typing import Callable, List, Optional, Tuple

from .rules import DEFAULT_RULES, Rule
from .schema import ActionCandidate, Verdict


class CircuitBreaker(object):
    """熔断器：连续失败达到阈值即熔断；一次放行即清零。"""

    def __init__(self, threshold=3):
        # type: (int) -> None
        self.threshold = threshold
        self.consecutive_failures = 0

    @property
    def is_open(self):
        # type: () -> bool
        return self.consecutive_failures >= self.threshold

    def record_failure(self):
        # type: () -> None
        self.consecutive_failures += 1

    def record_success(self):
        # type: () -> None
        self.consecutive_failures = 0

    def reset(self):
        # type: () -> None
        self.consecutive_failures = 0


class SemanticChecker(object):
    """动作出口的"证据安全员"。只管语义、不碰几何。"""

    def __init__(self,
                 rules=None,                       # type: Optional[List[Rule]]
                 llm_recheck=None,                 # type: Optional[Callable[[ActionCandidate], Tuple[bool, str]]]
                 circuit_threshold=3,              # type: int
                 ):
        self.rules = list(rules) if rules is not None else list(DEFAULT_RULES)
        self.llm_recheck = llm_recheck  # 柔性复核钩子；None = 纯规则模式
        self.breaker = CircuitBreaker(threshold=circuit_threshold)

    def check(self, action):
        # type: (ActionCandidate) -> Verdict
        # 0) 熔断优先：熔断期间一切动作不受理（承认"看不清、不能动"）
        if self.breaker.is_open:
            return Verdict(
                passed=False,
                rule_id="CIRCUIT_BREAKER",
                reason="熔断生效：已连续 {} 次校验未通过，暂停自动执行，交还人工".format(
                    self.breaker.consecutive_failures),
                suggestion="人工确认环境后调用 breaker.reset() 恢复",
                circuit_open=True,
            )

        # 1) 规则硬拦截（确定性，规则优先于模型）
        for rule in self.rules:  # type: Rule
            result = rule.check(action)
            if not result.passed:
                self.breaker.record_failure()
                return Verdict(passed=False, rule_id=rule.rule_id,
                               reason=result.reason, suggestion=result.suggestion,
                               blocked_by_rule=True)

        # 2) 语义模型柔性复核（可选；规则已过才轮到模型）
        if self.llm_recheck is not None:
            ok, reason = self.llm_recheck(action)
            if not ok:
                self.breaker.record_failure()
                return Verdict(passed=False, rule_id="LLM_RECHECK",
                               reason=reason,
                               suggestion="复核未通过，回传原因供规划改写重试",
                               blocked_by_rule=False)

        # 3) 放行并清零计数
        self.breaker.record_success()
        return Verdict(passed=True, rule_id="PASS", reason="证据合规")

    def reset(self):
        # type: () -> None
        self.breaker.reset()
