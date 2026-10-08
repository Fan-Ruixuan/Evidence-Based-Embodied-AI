# -*- coding: utf-8 -*-
"""让 pytest 能从仓库根目录导入 src/semantic_checker 包。"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
