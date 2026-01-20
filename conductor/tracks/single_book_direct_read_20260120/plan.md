# Implementation Plan: Single-Book Series Direct Read

이 계획은 1권만 포함된 시리즈(단권 도서)를 클릭했을 때 상세 페이지를 거치지 않고 바로 리더가 열리도록 개선하는 작업을 단계별로 정의합니다.

## Phase 1: Database & Backend Logic (TDD)
시리즈 목록 조회 시 각 시리즈의 도서 개수와 첫 번째 도서의 ID를 함께 가져오도록 백엔드 로직을 수정합니다.

- [x] Task: DB 쿼리 수정 및 데이터 모델 업데이트 9b9c135
    - [x] `src/db.py`의 시리즈 목록 조회 쿼리 수정 (book_count 및 first_book_id 포함) 9b9c135
- [x] Task: Backend API/Route 로직 검증 및 수정 9b9c135
    - [x] **Red Phase**: `tests/test_book_series.py`에 단권 시리즈의 `first_book_id`가 올바르게 반환되는지 확인하는 테스트 케이스 작성 (현재 실패 예상) 9b9c135
    - [x] **Green Phase**: `src/server.py`의 `/books/series` 라우트에서 수정된 DB 데이터를 템플릿으로 올바르게 전달하도록 수정 9b9c135
    - [x] **Refactor**: 데이터 구조 및 쿼리 최적화 9b9c135
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Database & Backend Logic' (Protocol in workflow.md)

## Phase 2: Frontend Template Update
템플릿에서 도서 개수에 따라 동적으로 링크를 생성하도록 수정합니다.

- [x] Task: `books_series.html` 템플릿 수정 9b9c135
    - [x] **Red Phase**: 템플릿 렌더링 테스트 코드 작성 (단권일 때 `/books/read/` 링크가 생성되는지 검증) 9b9c135
    - [x] **Green Phase**: `templates/books_series.html`에서 `book_count == 1` 조건문 추가 및 `href` 속성 변경 9b9c135
    - [x] **Fix**: 링크 URL 수정 (`/books/read` -> `/read`) 16de3db
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Frontend Template Update' (Protocol in workflow.md)

## Phase 3: Final Integration & Regression Testing
전체적인 동작을 확인하고 기존 기능에 영향이 없는지 검증합니다.

- [x] Task: 통합 테스트 수행 9b9c135
    - [x] 실제 환경과 유사한 mock 데이터를 활용하여 단권/다권 시리즈 클릭 시나리오 전체 테스트 9b9c135
- [x] Task: UI/UX 최종 점검 9b9c135
    - [x] 모바일 기기 및 다양한 브라우저에서 링크 동작 확인 9b9c135
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Integration & Regression Testing' (Protocol in workflow.md)
