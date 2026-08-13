# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""route_common 单点 helper 测试：per-model 锁表的 LRU 逐出上限。"""

from __future__ import annotations

import threading
from collections import OrderedDict

from app import route_common


def test_model_lock_returns_same_lock_per_model() -> None:
    assert route_common.model_lock("m_a") is route_common.model_lock("m_a")
    assert isinstance(route_common.model_lock("m_b"), type(threading.RLock()))


def test_locks_lru_eviction_beyond_cap() -> None:
    """锁表上限 1024：超出丢最旧；被访问的条目 move_to_end 不被逐出。"""
    original = route_common._locks
    route_common._locks = OrderedDict()
    try:
        cap = route_common.LOCKS_MAX
        for i in range(cap + 1):
            route_common.model_lock(f"m_{i:016x}")
        assert len(route_common._locks) == cap
        assert f"m_{0:016x}" not in route_common._locks  # 最旧被逐出
        assert f"m_{cap:016x}" in route_common._locks

        # 访问最旧的存活条目 → 移到最新；再插入一个 → 逐出次旧而非它
        kept = f"m_{1:016x}"
        route_common.model_lock(kept)
        route_common.model_lock(f"m_{cap + 1:016x}")
        assert kept in route_common._locks
        assert f"m_{2:016x}" not in route_common._locks
        assert len(route_common._locks) == cap
    finally:
        route_common._locks = original
