# Plan: Telegram Bot MVP (bot_mvp_20251231)

이 계획은 TDD(테스트 주도 개발) 원칙을 따르며, 각 단계의 마지막에는 사용자 검증 단계가 포함됩니다.

## Phase 1: 기반 구조 및 DB 연동 [checkpoint: ddd2d8d]
- [x] Task: 프로젝트 환경 설정 (requirements.txt, .env 설정) a103c11
- [x] Task: 몽고디비 아틀라스 연동 모듈 작성 (Motor 사용) ad47c11
  - [x] Sub-task: DB 연결 테스트 코드 작성
  - [x] Sub-task: DB 연결 및 기본 CRUD 로직 구현
- [x] Task: Conductor - User Manual Verification 'Phase 1: Database Setup' (Protocol in workflow.md)

## Phase 2: 미디어 처리 (yt-dlp ## Phase 2: 미디어 처리 (yt-dlp & FFmpeg) FFmpeg) [checkpoint: e951411]
- [x] Task: yt-dlp 통합 및 영상 정보 추출 로직 구현 7b558cd
  - [x] Sub-task: 정보 추출 기능 테스트 코드 작성
  - [x] Sub-task: URL 분석 및 메타데이터 반환 기능 구현
- [x] Task: FFmpeg 기반 영상 분할 로직 구현 a498b0d
  - [x] Sub-task: 영상 분할 기능 테스트 코드 작성
  - [x] Sub-task: 대용량 영상 자동 분할 로직 구현
- [x] Task: Conductor - User Manual Verification 'Phase 2: Media Processing' (Protocol in workflow.md)

## Phase 3: 텔레그램 봇 핵심 기능
- [x] Task: 봇 기본 명령어 (/start, /help) 및 비동기 루프 설정 d9c7bdb
  - [ ] Sub-task: 명령어 핸들러 테스트 코드 작성
  - [ ] Sub-task: 핸들러 및 봇 초기화 구현
- [ ] Task: URL 수신 및 인라인 버튼 메뉴 구현
  - [ ] Sub-task: 메뉴 생성 및 콜백 핸들러 테스트 코드 작성
  - [ ] Sub-task: 화질 선택 메뉴 및 상태 관리 구현
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Bot Interaction' (Protocol in workflow.md)

## Phase 4: 다운로드 & 업로드 파이프라인
- [ ] Task: 진행률 바가 포함된 다운로드 로직 구현
  - [ ] Sub-task: 다운로드 콜백 테스트 코드 작성
  - [ ] Sub-task: 실시간 메시지 업데이트 로직 구현
- [ ] Task: 텔레그램 파일 업로드 및 File ID 저장 로직 구현
  - [ ] Sub-task: 업로드 및 DB 저장 테스트 코드 작성
  - [ ] Sub-task: 최종 파일 전송 및 DB 기록 구현
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Full Pipeline' (Protocol in workflow.md)

## Phase 5: 다시보기 및 스트리밍 (MVP 완성)
- [ ] Task: 저장된 영상을 URL 기반으로 즉시 재전송하는 기능 구현
  - [ ] Sub-task: File ID 조회 및 전송 테스트 코드 작성
  - [ ] Sub-task: 캐시(DB) 확인 및 재전송 로직 구현
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Streaming & MVP' (Protocol in workflow.md)
