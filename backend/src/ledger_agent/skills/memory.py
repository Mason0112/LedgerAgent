"""輕量級歷史分錄記憶檢索器 (Few-Shot Retrieval)。

不需外部向量資料庫即可運作：
- 賣方統編精準命中：高權重 (+10)
- 賣方名稱字元重疊度：中權重 (+5)
- 品項描述重疊度：一般權重 (+3)
未來若資料量達數萬筆，只需替換此類別實作為 pgvector 檢索即可。
"""

from __future__ import annotations

from ledger_agent.models.skill import HistoryExample
from ledger_agent.models.voucher import VoucherExtraction


class HistoryMemory:
    """從該公司 history.jsonl 挑選最相關的 Top-K 歷史核准分錄作為 Few-Shot。"""

    @classmethod
    def retrieve(
        cls,
        voucher: VoucherExtraction,
        examples: list[HistoryExample],
        top_k: int = 3,
    ) -> list[HistoryExample]:
        if not examples:
            return []

        query_vendor = voucher.vendor_name.lower()
        query_items = " ".join(item.description for item in voucher.items).lower()

        scored: list[tuple[float, HistoryExample]] = []
        for ex in examples:
            score = 0.0

            # 1. 賣方統編精準匹配
            if (
                voucher.vendor_tax_id
                and ex.vendor_tax_id
                and voucher.vendor_tax_id.strip() == ex.vendor_tax_id.strip()
            ):
                score += 10.0

            # 2. 賣方名稱相似度（中文 2-gram Jaccard 相似度）
            score += 5.0 * cls._bigram_similarity(query_vendor, ex.vendor_name.lower())

            # 3. 品項描述相似度
            score += 3.0 * cls._bigram_similarity(query_items, ex.items_summary.lower())

            if score > 0.3:
                scored.append((score, ex))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [ex for _, ex in scored[:top_k]]

    @staticmethod
    def _bigram_similarity(text_a: str, text_b: str) -> float:
        """計算兩段文字的字元 2-gram Jaccard 相似度（對中英文混合特別有效）。"""
        a_clean = "".join(ch for ch in text_a if not ch.isspace())
        b_clean = "".join(ch for ch in text_b if not ch.isspace())
        if len(a_clean) < 2 or len(b_clean) < 2:
            return 1.0 if a_clean and a_clean == b_clean else 0.0

        set_a = {a_clean[i : i + 2] for i in range(len(a_clean) - 1)}
        set_b = {b_clean[i : i + 2] for i in range(len(b_clean) - 1)}
        union = set_a | set_b
        return len(set_a & set_b) / len(union) if union else 0.0
