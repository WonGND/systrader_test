# M2 게이트 보고 (1차) — 본문 정독 결과 + 대표 전략 후보 15개

- 작성일: 2026-08-26
- 마일스톤: M2 (트랙 분류 + 대표 전략 선정)
- 입력: shortlist 32건 본문 전문 (사용자 로컬 아카이브 → 세션 전달, 저장소 비커밋)
- 상태: **후보 15개 제시 — 사용자 10개 확정 대기**

---

## 0. 핵심 보고: Track A 실제 개수

**Track A (native_overseas) 후보 = 12개.**
원문이 해외 ETF/지수를 직접 대상으로 삼은 글이 예상보다 많았다.
**Track A ≥ 3 이므로 M4 축소 실행 조건에 해당하지 않는다** (보조 대조군 불필요).
단, 원문 성과 수치가 **텍스트로** 존재해 M4 오차 대조가 가능한 글은 5건이고,
나머지는 수치가 이미지에만 있어 M4를 "정합성 확인" 수준으로 수행하게 된다(표의 M4 열 참조).

## 1. 후보 15개 표

정렬: Track A 우선 → 재현 가능성 순. ✓* = 원문 성과 수치가 텍스트에 존재(오차 대조 가능),
✓ = 규칙 재현 가능하나 원문 수치는 이미지(정합성 확인만). 치환 건수는 Track B만 해당
(Track A는 원문 티커 그대로 사용).

| # | 제목 (발행연도) | 트랙 | 유형 | surv. risk | M4 재현 | 치환 | WL 밖 치환 | 비고 |
|---|---|---|---|---|---|---|---|---|
| C1 | 자산군 비중 배분 × 평균 모멘텀 스코어 (14)(17) (2014/2016) | **A** | asset_allocation | low | ✓* (CAGR 9%, MDD -8.52% 텍스트) | 0 | 없음 | 두 글 연속물 — 병합 1스펙 제안. 유니버스·로직·파이썬 코드 완전 명시 (SPY/EFA/EEM/IEF/TLT/SHY 및 확장판) |
| C2 | 동적 영구/올웨더 포트폴리오 (72) (2020) | **A** | asset_allocation | low | ✓* (CAGR/Sharpe/MDD 표가 텍스트) | 0 | 없음 | SPY/TLT/GLD/AGG + SPY/IEF/TLT/GLD/DBC, 평균 모멘텀 스코어 로직 명시. **M4 최적 대상** |
| C3 | Accelerating dual momentum (60) (2018) | **A** | momentum | low | ✓ (수치 이미지) | 0 | 없음 | SPY/SCZ/TLT/TIP, 1·3·6개월 평균 모멘텀. **발행이 인샘플 내 → OOS 가장 깨끗** |
| C4 | 역추세 전략 RSI(2) system (39) (2017) | **A** | mean_reversion | low | ✓ (수치 이미지) | 0 | 없음 | 미국 ETF 7종 + 파이썬 코드 완전. 장기추세 5단계 분산 + RSI(2) |
| C5 | 단순 이평선 돌파 (35) (2017) | **A** | trend_following | low | ✓ (수치 이미지) | 0 | 없음 | 미국 ETF 8×5 타임프레임 분산 + 채권, 코드 완전 |
| C6 | Hybrid asset allocation (136) (2023) | **A** | momentum/AA | low | ✓* (연 15%, MDD -10%대 텍스트) | 0 | 없음 | 로직 명시. **공격형 8자산 목록이 원문에 없음** → Q7 확인 필요 |
| C7 | 주중·월말 계절성 절대 수익 (115) (2021) | **A** | market_timing | low | ✓ (수치 이미지) | 0 | 없음 | SPY(월말+200MA)/TLT(목요일+5MA) 규칙 명시. SPY·TLT 동시 신호 시 배분 미명시 → Q8 |
| C8 | 나스닥-국채 스프레드 역추세 (2024) | **A** | mean_reversion | low | ✓* (연 10.5%, Sharpe 0.88 텍스트) | 0 | 없음 | QQQ/TLT 비율 3일 RSI 15/85·70/30. 원판만(레버리지판 QLD/UBT 제외). 발행 2024 → OOS 오염 |
| C9 | 과최적화를 피하는 CAGR 26% 역추세 (2024) | **A** | mean_reversion | low | ✓ (원판 Sharpe 2.11 언급) | 0 | 없음 | IBS+하한선 규칙 6줄 완전 명시. **단일 ETF(QQQ/SPY) 원판만** — 개별주 확장판은 생존편향 재현 불가로 제외. 발행 2024 |
| C10 | Larry Connors RSI(2) 역추세 (2024) | **A** | mean_reversion | low | ✓ (일부 수치 텍스트) | 0 | 없음 | 단순판(SPY/QQQ, 200MA+RSI2<5)만. TQQQ 버전·개별주 확장판 제외. C4와 동일 계열 → C4 우선 |
| C11 | 상관관계 상품 모멘텀 (152) (2024) | **A** | momentum (L/S) | low | ✓ (상대 성과만) | 0 | 없음 | DBA/DBB/DBE/DBP, 20/250일 상관 필터. **숏 포지션 필요** → 엔진 확장 부담 |
| C12 | Defense First 자산배분 (2025) | **A** | momentum/AA | low | ✓ (수치 이미지) | 0 | 없음 | TLT/GLD/PDBC/UUP/SPY/BIL, 규칙 완전. PDBC 상장 2014 → 인샘플 짧음. 발행 2025 → OOS 오염 최대 |
| C13 | Modified PAA 절대 수익 (31) (2017) | **B** | asset_allocation/hybrid | low | — (Track B는 M4 제외) | 3 | **없음** (단순화판 기준) | 국내 유니버스이나 로직 자산군 독립. 원문 코드가 "국가+채권만" 단순판도 실행 — KOSPI→SPY(WL), 10년국채→IEF(WL), 3년국채→SHY(WL)로 이식. CAGR 8%/MDD -5% 텍스트 |
| C14 | 비대칭 모멘텀 (41) (2017) | **B** | momentum | low~med | — | 5+ | **있음** (국내 섹터·팩터·레버리지·인버스·원달러) | 로직(선정 12M/비중 1~3M)은 독립적이나 유니버스 치환이 무거움 → 채택 시 전면 질문 필요 |
| C15 | 마켓 타이밍+변동성 조절 양방향 돌파 (53) (2018) | **B?** | volatility | low | — | 2 | **있음** (코스닥→?, 인버스) | 규칙·성과 수치 텍스트 완전. 단 파라미터(3,5,8,13 이평)가 "코스닥 특성" 근거로 설정 → 이식 시 정체성 훼손 소지. **needs_user_confirm** |

**유형 커버리지**: momentum(C3,C14) / mean_reversion(C4,C8,C9,C10) / asset_allocation(C1,C2,C6,C13) / trend_following(C5) / market_timing(C7) / volatility(C15) — 4대 유형 최소 1개씩 충족.

## 2. 정독했으나 후보 제외한 17건과 사유

| 글 | 사유 코드 | 상세 |
|---|---|---|
| AI ETF 동적 자산배분 (110) (2021) | not_a_strategy | ETF 소개글. 전략은 "(2)편에서" — 규칙 없음 |
| 동적 자산 배분 전략의 몰락? (32) (2017) | not_a_strategy | IVY 비평 에세이. 자체 전략 규칙 없음 |
| 변동성 돌파 핵심 원리 (48) (2017) | duplicate_or_continuation | 원리 설명. 규칙은 "링크1·2" 및 후속편 의존 |
| Target volatility (19) (2014) | not_a_strategy | 기법(공식) 설명. 백테스트 대상 전략 아님. 파라미터를 우리가 채우면 추측 위반 |
| 최고의 방어 자산군 (117) (2022) | not_a_strategy | 자산군 분석 소개글 |
| 리밸런싱 효과 (20)(21) (2018) | not_a_strategy + domestic | 심리/원칙 에세이 + 국내 개별주 단타(뉴지스탁) 전제 |
| MDD 근접 포트폴리오 (105) (2021) | not_reproducible | allocatesmartly 50개 전략의 메타 전략 — 기초 전략 데이터 없이 재현 불가 |
| 리밸런싱 언제? (70)(71) (2019) | not_a_strategy | 리밸런싱 타이밍 연구. **M3 엔진 설계 참고자료로 채택** (portfolio tranching, TOM) |
| 이긴 전략들 (4) (2017) | excluded_domestic_only + surv. high | 국내 개별 종목(시총 필터) 모멘텀 현상 연구. 개별주 스크리닝 = 생존편향 high |
| 다중 타임프레임 추세추종 (2025) | not_reproducible | BTC 1시간봉·90일 — 장중 데이터 필요, yfinance 일봉 불가, 암호자산(WL 금지) |
| 평균 노이즈 변동성 돌파 (56) (2018) | not_reproducible | 암호화폐 4종 + 장중 돌파 체결 필요 |
| 환노출 dynamic permanent portfolio (2024) | scope_conflict | 원화/달러 환노출이 전략 정체성 — 프로젝트 규약(USD 기준, 원화 미고려)과 정면 충돌 |
| 럼버-골드 비율 (2025) | data + 저자 부정 결론 | lumber 선물 장기 데이터 확보 곤란(WL 밖), 저자 스스로 "실용 가치 상실" 결론 |
| SPY 장중 모멘텀·점심 효과 등 (스크리닝 단계 제외분) | not_reproducible | 장중 데이터 필요 (M2 1차 스크리닝에서 기록) |

## 3. 스펙 작성 전 확인 질문 (채택 시에만 유효)

| # | 대상 | 질문 | 권장안 |
|---|---|---|---|
| Q7 | C6 (HAA) | 공격형 8자산 목록이 원문에 없음. 외부 표준(SPY,IWM,EFA,EEM,VNQ,DBC,IEF,TLT — Keller 논문)을 사용자 승인 하에 채울지? | **승인 요청**: 원 논문 유니버스를 `user_approved`로 기록 (원문 비인용 명시) |
| Q8 | C7 (계절성) | SPY·TLT 신호 동시 발생 시 자금 배분이 원문에 없음 | **50:50 분할**을 `assumption_needed` 가정값으로 리포트 명기 |
| Q9 | C15 (양방향 돌파) | 코스닥 특화 파라미터의 해외 이식이 정체성을 훼손하는지 | 채택 보류(예비). 채택 원하시면 코스닥→광의지수(SPY) 치환 + 파라미터 원문 유지로 질문 재상정 |

## 4. 추천 10개 (확정 요청)

**권장 조합** — Track A 9 + Track B 1, 4대 유형 커버, M4 텍스트 대조 가능 4건 포함:

> **C1, C2, C3, C4, C5, C6, C7, C8, C9, C13**

- 제외 추천 사유: C10(C4와 동일 계열 중복), C11(숏 엔진 확장 부담), C12(OOS 오염 최대 + PDBC 인샘플 부족), C14(화이트리스트 밖 치환 5건+), C15(정체성 훼손 소지)
- C6 채택 시 Q7, C7 채택 시 Q8 승인이 함께 필요

## 5. 다음 단계

1. 사용자 10개 확정 (+ Q7/Q8 답변)
2. 확정 10개의 strategy_spec JSON 생성 (`data/specs/`) — 모든 값 필드에 source_quote + confidence
3. 스키마 검증 통과 확인 → M2 게이트 종결 보고
4. M3 (백테스트 엔진 + 회귀 테스트) 착수

---

## 6. M2 게이트 종결 보고 (2026-08-26 갱신)

### 완료 항목
- 사용자 확정: **C1~C9 + C13** (2026-08-26, "추천대로") + Q7·Q8 승인
- 전략 스펙 JSON 10건 생성: `data/specs/c01-*.json` ~ `c13-*.json`

### 검증 근거
- **source_quote 181건 전부를 전달받은 원문 번들과 기계 대조** — 불일치 0
  (원문의 NBSP 공백까지 원문 그대로 보존; 대조 실패 시 생성 자체가 중단되는 구조)
- **JSON Schema(draft 2020-12) 검증: 10건 전부 0오류** — evidence 필수 필드,
  null→assumption 규칙, ported→port_note 필수, mapping_source 제한 등 스키마 강제 조건 통과
- Track A 9건 `m4_reproduction_eligible: true` / C13(ported) `false` + port_note 기록

### 잔여 사항 (비차단)
- `source.content_hash`가 `PENDING_LOCAL_INDEX` — 원문 해시는 로컬 인덱스에만 존재.
  사용자 로컬에서 `python -m src.extractor.fill_spec_meta` 1회 실행 후 커밋으로 충전 (W10)
- 각 스펙의 non-blocking open_questions(체결 시점 등)는 엔진 기본값(익일 시가)으로
  진행하고 리포트에 "가정값"으로 표기 — CLAUDE.md §5 규약 그대로

### 다음 단계
M3: 백테스트 엔진 + 회귀 테스트 (CLAUDE.md §6 전 항목). 합성 데이터 검증(원격)과
실데이터 대조(로컬 실행) 2단계로 분리 수행.
