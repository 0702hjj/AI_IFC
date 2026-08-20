"""goldlib —— 设计参考库：文件是事实源，golden.db 是可重建派生物（stdlib sqlite3）。

- reindex: 文件 → golden.db 重建（幂等：两次重建字节一致）
- query:   特征直查（pull 模式）
- reverse: 底稿 DXF → 反推 DSL 声明（learning 用）
- ingest:  新案例入库（vote/correct/challenge 三分支）
"""

__all__ = ["reindex", "query", "reverse", "ingest"]