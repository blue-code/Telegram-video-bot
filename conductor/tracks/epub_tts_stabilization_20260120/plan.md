# Implementation Plan: EPUB TTS Stabilization & Comprehensive Testing

이 계획은 EPUB 리더의 TTS 기능에서 발생하는 고질적인 안정성 문제를 해결하고, 실리콘벨리 표준의 엄격한 테스트 및 검증 체계를 구축하는 것을 목표로 합니다.

## Phase 1: Infrastructure & API Enhancement
백엔드 TTS API의 안정성을 높이고, 테스트 환경을 구축합니다.

- [x] Task: TTS API 개선 및 취소 메커니즘 확인 11fc6b6
    - [x] `src/server.py`의 `/api/tts/synthesize`가 대량의 동시 요청이나 급격한 중단 시 리소스를 안전하게 해제하는지 검토 11fc6b6
- [x] Task: 프런트엔드 테스트 환경 구축 (Playwright) 11fc6b6
    - [x] `tests/e2e/tts_test.py` (또는 별도 설정)를 통해 브라우저 기반 자동화 테스트 환경 준비 11fc6b6
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure & API Enhancement' (Protocol in workflow.md)

## Phase 2: Singleton Audio Architecture (Frontend)
오디오 객체와 재생 상태를 중앙에서 통제하는 싱글톤 컨트롤러를 구현합니다.

- [x] Task: `AudioController` 클래스 설계 및 구현 2f3c9f0
    - [x] **Red Phase**: 재생 중 새로운 요청이 오면 기존 재생이 중단되는지 검증하는 테스트 작성 2f3c9f0
    - [x] **Green Phase**: `reader.html` 내부에 싱글톤 패턴의 오디오 관리자 구현 (AbortController 활용) 2f3c9f0
    - [x] **Refactor**: 전역 이벤트 리스너(ended, error)를 한곳에서 관리하도록 정리 2f3c9f0
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Singleton Audio Architecture' (Protocol in workflow.md)

## Phase 3: Audio Queue & Text Deduplication Logic
순차적 재생 보장과 페이지 간 텍스트 중복 방지 로직을 구현합니다.

- [x] Task: 오디오 재생 큐(Queue) 시스템 구현 02fa5e6
    - [x] 재생할 문장들을 큐에 담고 하나씩 처리하는 로직 구현 (목소리 겹침 방지) 02fa5e6
- [x] Task: 정밀 CFI 계산 및 텍스트 추출 개선 02fa5e6
    - [x] **Red Phase**: 페이지 전환 시 마지막 문장이 겹치는 시나리오 테스트 케이스 작성 02fa5e6
    - [x] **Green Phase**: `epub.js`의 CFI Range 기능을 사용하여 정확한 문장 시작점 계산 02fa5e6
    - [x] **Green Phase**: 문자열 비교 알고리즘을 통한 2차 중복 제거 필터 적용 02fa5e6
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Audio Queue & Text Deduplication Logic' (Protocol in workflow.md)

## Phase 4: Auto-Paging Integration & Debug Panel
오디오 재생과 페이지 넘김 이벤트를 완벽하게 동기화하고 가시성을 확보합니다.

- [x] Task: 상태 기반 자동 페이지 넘김(Auto-Paging) 안정화 0ca136a
    - [x] 오디오 재생 완료 시점과 다음 페이지 로딩 간의 Race Condition 해결 0ca136a
- [x] Task: 실시간 TTS 디버그 패널 추가 0ca136a
    - [x] 현재 재생 중인 문장, CFI 범위, 큐 상태 등을 리더 화면 상단에 표시 (개발/검증용) 0ca136a
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Auto-Paging Integration & Debug Panel' (Protocol in workflow.md)

## Phase 5: Final Comprehensive Testing & Hardening
다양한 엣지 케이스를 포함한 전체 시나리오를 검증합니다.

- [x] Task: 20년차 시니어 수준의 '완전무결' 테스트 수행 855d501
    - [x] 매우 빠른 페이지 넘김, 네트워크 단절 후 복구, 긴 문장 재생 중 수면 타이머 작동 등 스트레스 테스트 수행 855d501
- [x] Task: 코드 리팩토링 및 주석(Rationale 위주) 강화 855d501
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Final Comprehensive Testing' (Protocol in workflow.md)
