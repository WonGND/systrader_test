# -*- coding: utf-8 -*-
"""M6 batch set = the M5 judgment set, plus the two candidates added at the
M5 gate (Q15): C10 (Larry Connors RSI(2), 단순판) and C12 (Defense First).

C11/C14/C15 from the M2 shortlist are NOT here and will not be added:
- C11 상관관계 상품 모멘텀 — 숏 포지션이 전략 정체성. 엔진은 롱온리다.
- C14 비대칭 모멘텀 — 국내 섹터·팩터·레버리지·인버스 등 화이트리스트 밖 치환 다수.
- C15 마켓타이밍+변동성 조절 — 파라미터가 "코스닥 특성" 근거라 이식 시 정체성 훼손.
사유는 reports/M6_final_report.md와 docs/DECISIONS.md에 기록한다.

The builders for C10/C12 land here once their specs exist (data/specs/c10*.json,
c12*.json). Until then this module is the M5 set — no placeholder rules are
invented (CLAUDE.md §1-1).
"""

from __future__ import annotations

from src.validate.strategies_m5 import (ALL_TICKERS as M5_TICKERS,
                                        BUILDERS as M5_BUILDERS)

# 스펙 승인 후 여기에 build_c10 / build_c12 를 추가한다.
PENDING_BUILDERS: list = []
PENDING_TICKERS: set = set()

BUILDERS = list(M5_BUILDERS) + PENDING_BUILDERS
ALL_TICKERS = sorted(set(M5_TICKERS) | PENDING_TICKERS)
