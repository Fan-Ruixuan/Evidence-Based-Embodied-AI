# -*- coding: utf-8 -*-
"""行之有据 · 零训练前置语义校验器（阶段一：文本模拟）。

公开接口：
    SemanticChecker   双轨校验 + 熔断
    parse_action      自由文本 -> ActionCandidate（阶段一正则模拟）
    ActionCandidate / SpatialRelation / Verdict
"""
from .schema import ActionCandidate, SpatialRelation, Verdict
from .rules import DEFAULT_RULES, VisibilityRule, ReferenceFrameRule, \
    EvidenceSufficiencyRule, ConfidenceRule
from .checker import SemanticChecker, CircuitBreaker
from .parser import parse_action, parse_relations

__version__ = "0.1.0"

__all__ = [
    "SemanticChecker", "CircuitBreaker",
    "ActionCandidate", "SpatialRelation", "Verdict",
    "DEFAULT_RULES", "VisibilityRule", "ReferenceFrameRule",
    "EvidenceSufficiencyRule", "ConfidenceRule",
    "parse_action", "parse_relations",
]
