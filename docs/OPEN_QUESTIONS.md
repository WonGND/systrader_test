# OPEN QUESTIONS

사용자 확인이 필요한 미결 항목. 각 항목에는 **권장안**을 반드시 붙인다(CLAUDE.md §10).
해소된 항목은 삭제하지 말고 "resolved" 표시 후 결정을 DECISIONS.md로 옮긴다.

---

## 상태 범례
- `blocking` — 답변 전까지 다음 단계 진행 불가
- `non-blocking` — 권장안 기본값으로 진행 가능하나 확인받는 편이 나음
- `resolved` — 해소됨 (DECISIONS.md 참조)

---

## M0 — 착수 / 구조 조사

전문과 근거는 `reports/M0_survey_and_M1_plan.md` §5 참조.
**2026-08-07 사용자 답변 "추천대로"로 Q1~Q5 전부 권장안으로 확정** (DECISIONS.md 기록).

| # | 상태 | 질문 | 확정 내용 |
|---|---|---|---|
| Q1 | resolved | 크롤링 실행 위치 | **로컬 Windows 실행**. 원격 세션은 코드 작성·커밋만. allowlist 추가는 선택적 병행 |
| Q2 | resolved | DOM 셀렉터 실측 방법 | **읽기 전용 탐침 `src/crawler/probe.py`** 커밋 완료 → 사용자가 로컬 1회 실행 후 출력 전달 |
| Q3 | resolved | 카테고리 URL 확보 | **탐침이 카테고리 목록을 자동 열거** (이름·URL·표시 글 수 출력) |
| Q4 | resolved | 아카이브 형식·이미지 범위 | 원본 HTML + 추출 텍스트 병행(`encoding="utf-8"`), 이미지 바이너리 미다운로드(URL·개수·alt만), `index.jsonl` + `checkpoint.json` |
| Q5 | resolved | 이미지 의존 판별 보수성 | 보수적 판별 + 자동 판별은 플래그일 뿐, M2에서 사람이 검토(사유·이미지 위치 병기) |

### 현재 대기 중
| # | 상태 | 내용 |
|---|---|---|
| W1 | blocking | **사용자의 로컬 탐침 실행 결과 대기** — `python "src\crawler\probe.py" --out "reports\probe_output.txt"` 출력 전달 필요 |
| W2 | blocking | 탐침 결과 검토 후 **M1 크롤링 본실행 승인** |

---

## 관련 블로커 (질문 아님, `docs/STATE.md` 참조)
- **B-01** 실행 환경 네트워크 정책으로 외부 도메인 접근 불가 → STEP 3 미수행
- **B-02** `query1.finance.yahoo.com` 차단 → M3 실데이터 대조·M5 OOS 영향

---

## M2 — 스펙/트랙 분류 (예정)

| # | 상태 | 질문 | 권장안 |
|---|---|---|---|
| (M2 진입 시 작성) | | | |
