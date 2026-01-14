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

## Phase 3: 텔레그램 봇 핵심 기능 [checkpoint: 294d2de]
- [x] Task: 봇 기본 명령어 (/start, /help) 및 비동기 루프 설정 d9c7bdb
  - [ ] Sub-task: 명령어 핸들러 테스트 코드 작성
  - [ ] Sub-task: 핸들러 및 봇 초기화 구현
- [x] Task: URL 수신 및 인라인 버튼 메뉴 구현 6e8222a
  - [x] Sub-task: 메뉴 생성 및 콜백 핸들러 테스트 코드 작성
  - [x] Sub-task: 화질 선택 메뉴 및 상태 관리 구현
- [x] Task: Conductor - User Manual Verification 'Phase 3: Bot Interaction' (Protocol in workflow.md)

## Phase 4: 다운로드 & 업로드 파이프라인 [checkpoint: 3891a1f]
- [x] Task: 진행률 바가 포함된 다운로드 로직 구현 3891a1f
  - [x] Sub-task: 다운로드 콜백 테스트 코드 작성
  - [x] Sub-task: 실시간 메시지 업데이트 로직 구현
- [x] Task: 텔레그램 파일 업로드 및 File ID 저장 로직 구현 3891a1f
  - [x] Sub-task: 업로드 및 DB 저장 테스트 코드 작성
  - [x] Sub-task: 최종 파일 전송 및 DB 기록 구현
- [x] Task: Conductor - User Manual Verification 'Phase 4: Full Pipeline' (Protocol in workflow.md) 3891a1f

## Phase 5: 다시보기 및 스트리밍 (MVP 완성)
- [x] Task: 저장된 영상을 URL 기반으로 즉시 재전송하는 기능 구현 799985e
  - [x] Sub-task: File ID 조회 및 전송 테스트 코드 작성
  - [x] Sub-task: 캐시(DB) 확인 및 재전송 로직 구현
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Streaming & MVP' (Protocol in workflow.md)

## Phase 6: 안정적인 저장소 (Bin Channel) [Pro]
- [x] Task: Bin Channel 연동 및 파일 관리 로직 구현 34afab1
  - [x] Sub-task: 채널 ID 설정 및 포워딩 테스트 코드 작성
  - [x] Sub-task: 다운로드 파일을 Bin Channel로 업로드하고 사용자에게 포워딩하는 로직 구현

## Phase 7: 웹 스트리밍 지원 (Direct Link) [Pro]
- [x] Task: FastAPI 기반 스트리밍 서버 구현 8c816f2
  - [x] Sub-task: 스트리밍 엔드포인트 테스트 코드 작성 (/watch/{id})
  - [x] Sub-task: Telegram FileStreamer 연동 및 재생 페이지(HTML) 구현

## Phase 8: 대량 처리 및 고급 기능 [Pro]
- [x] Task: 유튜브 플레이리스트 및 배치 다운로드 지원 a7a7d69
  - [x] Sub-task: 플레이리스트 URL 감지 및 메타데이터 추출 로직 구현
  - [x] Sub-task: 배치 다운로드 관리자(Queue) 구현
  - [x] Sub-task: 스트리밍 링크 버튼 추가 (Phase 7 연동)

## Phase 9: 모바일 최적화 및 관리
- [x] Task: 모바일 재생 최적화 (Re-encoding)
  - [x] Sub-task: 해상도 선택(720p/1080p/Original) 및 FFmpeg 인코딩 구현
  - [x] Sub-task: 실시간 인코딩 진행 상황 로깅 및 알림
- [x] Task: 인코딩된 영상 관리
  - [x] Sub-task: '인코딩됨' 전용 메뉴 및 관리(재생/삭제) 기능 구현
  - [x] Sub-task: 다운로드 시 최적화 파일 우선 제공 로직 추가

## Phase 10: 일반 파일 관리 및 안정성
- [x] Task: 일반 파일 관리 시스템
  - [x] Sub-task: 파일 업로드 API (15MB 분할 지원) 및 DB 연동
  - [x] Sub-task: 파일 관리 페이지 (검색, 필터, 정렬, 페이지네이션) 구현
- [x] Task: 다운로드 및 안정성 개선
  - [x] Sub-task: 다중 파일 ZIP 다운로드 및 대용량 파일 준비 알림 시스템
  - [x] Sub-task: 업로드 안정성 개선 (aiofiles 비동기 처리, Retry 로직)
  - [x] Sub-task: 오래된 다운로드 캐시 자동 삭제 (7일)

## Phase 11: eBook 라이브러리 및 리더
- [x] Task: eBook 라이브러리 구축
  - [x] Sub-task: EPUB 메타데이터(표지, 제목, 작가) 추출기 구현
  - [x] Sub-task: eBook 전용 그리드 뷰 및 검색 페이지 구현
- [x] Task: 웹 EPUB 리더 구현
  - [x] Sub-task: epub.js 기반 뷰어 및 터치/메뉴 인터페이스 구현
  - [x] Sub-task: 독서 진행 상황(CFI) 자동 저장 및 이어보기 기능 구현
  - [x] Sub-task: 뷰어 로딩 안정성 개선 (Blob loading)
