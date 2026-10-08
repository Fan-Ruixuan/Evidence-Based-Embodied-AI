# -*- coding: utf-8 -*-
"""阶段一演示：零训练规则校验器拦截三类典型病灶 + 熔断。

对应总纲 3.1 的三类错误：
  1) 遮挡误判：杯子被书本挡住仍规划去拿；
  2) 参考系混淆：'左边'是谁的左边；
  3) 证据不足强行规划：画面没有证据也敢出动作。

运行：python src/semantic_checker/demo.py
"""
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semantic_checker.checker import SemanticChecker
from semantic_checker.parser import parse_action

CASES = [
    # (编号, 指令文本, 预期, 说明)
    ("用例1", "亲眼看见杯子可见，置信度0.9。抓取杯子", "放行",
     "证据齐全：亲眼所见 + 置信度 0.9"),
    ("用例2", "杯子应该可见，抓取杯子", "拦截(R1)",
     "遮挡误判：可见性是推测（'应该'），看不见当不存在"),
    ("用例3", "杯子被书本挡住了，抓取杯子", "拦截(R1)",
     "明确遮挡：证据自陈'被书本挡住'仍去抓"),
    ("用例4", "杯子可见，抓取杯子", "拦截(R1)",
     "字段缺失：声称可见但无观测性质、无置信度，先自我举证"),
    ("用例5", "积木在左边，抓取积木", "拦截(R2)",
     "参考系混淆：'左边'未声明是谁的左边"),
    ("用例6", "抓取工具箱", "拦截(R3)",
     "证据不足强行规划：画面没有任何证据就出动作"),
]


def main():
    print("=" * 72)
    print("零训练前置语义校验器 · 阶段一文本模拟演示")
    print("规则优先于模型：确定性规则硬拦截，拦截必带定向修正建议")
    print("=" * 72)

    for name, text, expect, note in CASES:
        action = parse_action(text)
        verdict = SemanticChecker().check(action)
        print("\n{} 指令：{}".format(name, text))
        print("      解析 -> 动作={} 目标={} 证据数={}".format(
            action.action, action.target, len(action.evidence)))
        print("      预期：{}（{}）".format(expect, note))
        print("      结果：{}".format(verdict))

    # 熔断演示：连续失败达到阈值后，即使动作本身合规也不受理
    print("\n" + "-" * 72)
    print("熔断演示：连续 3 次未通过 -> 第 4 次即使证据合规也被熔断拦下")
    print("-" * 72)
    checker = SemanticChecker(circuit_threshold=3)
    for text in ["杯子应该可见，抓取杯子",        # 拦截 1
                 "杯子被书本挡住了，抓取杯子",    # 拦截 2
                 "抓取工具箱",                    # 拦截 3 -> 熔断打开
                 "亲眼看见杯子可见，置信度0.9。抓取杯子"]:  # 合规动作
        verdict = checker.check(parse_action(text))
        print("\n指令：{}".format(text))
        print("结果：{}".format(verdict))
    print("\n人工确认环境后 checker.reset() 恢复 ->",
          (checker.reset() or "已恢复，consecutive_failures = {}".format(
              checker.breaker.consecutive_failures)))


if __name__ == "__main__":
    main()
