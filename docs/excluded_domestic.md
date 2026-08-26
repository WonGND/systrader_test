# EXCLUDED — DOMESTIC ONLY (Track C)

국내 시장 고유 요소에 의존하여 해외 이식 시 전략 정체성이 훼손되는 글의 누적 목록.
**분류만 하고 백테스트하지 않는다** (scope_policy Track C).

**주의**: Track A 개수를 채우기 위해 Track C를 Track B로 재분류하지 않는다
(CLAUDE.md §11).

---

## 제외 사유 코드
- `KOSDAQ_SMALLCAP` — 코스닥/소형주 필터 의존 (미국 시장에 등가 없음)
- `DOMESTIC_REGULATION` — 국내 공매도·세제·거래 규제 의존
- `DOMESTIC_FLOW_METRIC` — 국내 특정 수급 지표(외국인/기관 순매수 등) 의존
- `KRX_MICROSTRUCTURE` — 상하한가·동시호가 등 KRX 고유 시장 구조 의존
- `DOMESTIC_FUNDAMENTAL_SOURCE` — 국내 전용 재무 데이터 소스 의존

---

| # | 제목 | URL | 전략 유형 | 제외 사유 코드 | 상세 근거 |
|---|---|---|---|---|---|
| 1 | 주식시장을 이긴 전략들 (4) - 모멘텀전략과 역모멘텀전략 (2017) | https://stock79.tistory.com/entry/%EC%A3%BC%EC%8B%9D%EC%8B%9C%EC%9E%A5%EC%9D%84-%EC%9D%B4%EA%B8%B4-%EC%A0%84%EB%9E%B5%EB%93%A4-4-%EB%AA%A8%EB%A9%98%ED%85%80%EC%A0%84%EB%9E%B5%EA%B3%BC-%EC%97%AD%EB%AA%A8%EB%A9%98%ED%85%80%EC%A0%84%EB%9E%B5 | momentum 연구 | KOSDAQ_SMALLCAP + 개별주 스크리닝 | 국내 거래소/코스닥 시총 필터 개별 종목 대상. 원문: "거래소의 시가총액 5,000억 원 이상인 종목과 코스닥의 시가총액 1,500억 원 이상인 종목들" — 생존편향 구조적 제거 불가 |

> 주: shortlist 32건 중 국내 고유 요소 의존이 확인된 것은 상기 1건.
> 코스닥 단타 시리즈(46, 47, 66, 97, 98 등)는 1차 스크리닝에서 shortlist 미포함으로
> 본문 미정독 상태 — M6 배치 처리 시 정독 후 정식 분류 예정.
