# -*- coding: utf-8 -*-
"""阶段一文本模拟：自由文本指令 -> 结构化空间关系元组。

用正则把一段 VLM 风格的描述解析为 SpatialRelation / ActionCandidate。
刻意保持"笨"：只做词面映射，不做任何推断——解析不到的字段就留空，
交给规则校验器拦截。这正说明"字段缺失可被确定性发现"。
"""
import re
from typing import List, Optional

from .schema import (ActionCandidate, SpatialRelation,
                     FRAME_UNKNOWN, RELATION_BEHIND, RELATION_LEFT_OF,
                     RELATION_OCCLUDED, RELATION_ON, RELATION_RIGHT_OF,
                     RELATION_VISIBLE)

# 动作词 -> 动作类型
_ACTION_PATTERNS = [
    (re.compile(u"(?:抓取|拿起|抓起|捡起)"), "grasp"),
    (re.compile(u"(?:移动|搬运)到"), "move_to"),
    (re.compile(u"(?:按下|按压)"), "press"),
]

# 目标词：抓取动词后面的名词短语（演示用极简分词，取两三个字组成的词）
_TARGET_RE = re.compile(u"[\u4e00-\u9fff]{1,6}?")

# 可见/遮挡句式：subject 前可带"亲眼"类前缀、后可带"应该"类推测词
_VISIBLE_RE = re.compile(
    u"(?:亲眼看见|亲眼|看见|看到|确认)?"
    u"([\u4e00-\u9fff]{1,6}?)"
    u"(?:应该|大概|可能|似乎|好像|估计|想必)?"
    u"(?:可见|看得见|能看见|看见了)")
_OCCLUDED_RE = re.compile(u"([\u4e00-\u9fff]{1,6}?)被([\u4e00-\u9fff]{1,6}?)(?:挡住|遮挡|挡着|盖住)")
_ON_RE = re.compile(u"([\u4e00-\u9fff]{1,6}?)在([\u4e00-\u9fff]{1,6}?)上")
_BEHIND_RE = re.compile(u"([\u4e00-\u9fff]{1,6}?)在([\u4e00-\u9fff]{1,6}?)(?:后面|后边)")
_LEFT_RE = re.compile(u"([\u4e00-\u9fff]{1,6}?)(?:的)?(?:左边|左侧|左手边)")
_RIGHT_RE = re.compile(u"([\u4e00-\u9fff]{1,6}?)(?:的)?(?:右边|右侧|右手边)")

# 参考系线索：提到"以桌面/桌子为准" -> table；"以机器人/我" -> robot_view / self
_FRAME_TABLE_RE = re.compile(u"(?:以|相对于)(?:桌面|桌子|台面)")
_FRAME_ROBOT_RE = re.compile(u"(?:以|相对于)?机器人(?:视角|为准)?")

# 观测性质线索：推测词 -> observed=False；亲眼词 -> observed=True
_HEDGE_RE = re.compile(u"(?:应该|大概|可能|似乎|好像|估计|听说|想必)")
_EYEWITNESS_RE = re.compile(u"(?:亲眼|看见|看到|确认)")

# 置信度线索：如 "置信度0.9" / "90%把握"
_CONF_RE = re.compile(u"(?:置信度|把握)(?:为|是|约)?\\s*([01](?:\\.\\d+)?|\\d{1,3})\\s*(?:%)?")


def _conf_value(raw):
    # type: (str) -> float
    v = float(raw)
    return v / 100.0 if v > 1.0 else v


def _frame_for(text, default=FRAME_UNKNOWN):
    # type: (str, str) -> str
    if _FRAME_TABLE_RE.search(text):
        return "table"
    if _FRAME_ROBOT_RE.search(text):
        return "robot_view"
    return default


def parse_relations(text):
    # type: (str) -> List[SpatialRelation]
    """把描述文本解析为空间关系元组列表（解析不到的字段保持空缺）。"""
    relations = []  # type: List[SpatialRelation]
    frame = _frame_for(text)

    conf_match = _CONF_RE.search(text)
    confidence = _conf_value(conf_match.group(1)) if conf_match else None
    if _HEDGE_RE.search(text):
        observed = False       # 出现推测词 -> 观测性质记为"推测"
    elif _EYEWITNESS_RE.search(text):
        observed = True
    else:
        observed = None        # 未标注：故意留空，交由规则拦截

    for m in _OCCLUDED_RE.finditer(text):
        relations.append(SpatialRelation(subject=m.group(1), relation=RELATION_OCCLUDED,
                                         object=m.group(2), reference_frame=frame,
                                         confidence=confidence, observed=observed))
    for m in _VISIBLE_RE.finditer(text):
        relations.append(SpatialRelation(subject=m.group(1), relation=RELATION_VISIBLE,
                                         reference_frame=frame,
                                         confidence=confidence, observed=observed))
    for m in _ON_RE.finditer(text):
        relations.append(SpatialRelation(subject=m.group(1), relation=RELATION_ON,
                                         object=m.group(2), reference_frame=frame,
                                         confidence=confidence, observed=observed))
    for m in _BEHIND_RE.finditer(text):
        relations.append(SpatialRelation(subject=m.group(1), relation=RELATION_BEHIND,
                                         object=m.group(2), reference_frame=frame,
                                         confidence=confidence, observed=observed))
    for m in _LEFT_RE.finditer(text):
        relations.append(SpatialRelation(subject=m.group(1), relation=RELATION_LEFT_OF,
                                         reference_frame=frame,
                                         confidence=confidence, observed=observed))
    for m in _RIGHT_RE.finditer(text):
        relations.append(SpatialRelation(subject=m.group(1), relation=RELATION_RIGHT_OF,
                                         reference_frame=frame,
                                         confidence=confidence, observed=observed))
    return relations


def parse_action(text):
    # type: (str) -> Optional[ActionCandidate]
    """从指令文本解析候选动作（动作 + 目标），并挂上 parse_relations 的证据。"""
    action_type = None  # type: Optional[str]
    for pattern, atype in _ACTION_PATTERNS:
        if pattern.search(text):
            action_type = atype
            break
    if action_type is None:
        return None

    # 目标 = 动作词之后的第一个名词片段（极简处理，够演示用）
    after = re.split(u"(?:抓取|拿起|抓起|捡起|移动|搬运|按下|按压)", text, maxsplit=1)[-1]
    m = re.match(u"\\s*([\u4e00-\u9fff]{1,6}?)(?:，|,|。|之前|然后|$)", after)
    target = m.group(1) if m else ""
    if not target:
        m2 = _TARGET_RE.match(after.strip())
        target = m2.group(0) if m2 else ""

    return ActionCandidate(action=action_type, target=target,
                           evidence=parse_relations(text))
