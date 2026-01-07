# 개인용 고급 기능 로드맵

**목표:** FileToLink 핵심 기능 (1,2,6,7) 구현
**대상:** 개인 사용 최적화
**기간:** Phase 9-10

---

## 현재 상태 분석

### ✅ 이미 구현된 기능
- **[1] 웹 링크 변환**: Phase 7 완료 (FastAPI 스트리밍)
- **[2] Private Channel**: Phase 6 완료 (Bin Channel)

### 🔄 추가 구현 필요
- **[6] Multi-Client**: 개인용이므로 우선순위 낮음 → Phase 10 (선택)
- **[7] URL 단축**: 간단한 hash 기반 → Phase 9

### 💡 개인용 관점 우선순위 조정
```
개인 사용 특성:
- Rate limit 걱정 없음 → Multi-client 불필요
- 외부 공유 적음 → URL 단축 간소화
- 빠른 접근성 중요 → 웹 스트리밍 최적화

권장 순서:
1. Phase 9: 웹 링크 최적화 + 간단한 URL 단축
2. Phase 10: Multi-Client (나중에 필요시)
```

---

## Phase 9: 웹 링크 최적화 및 URL 단축 🎯

**목표:** Bin Channel + 웹 스트리밍 통합 완성 + 짧은 URL 생성

### Task 9.1: Bin Channel ↔ 웹 스트리밍 통합 검증
**목적:** Phase 6과 7이 제대로 연동되는지 확인

#### Sub-tasks:
- [ ] Sub-task: Bin Channel 업로드 후 스트리밍 링크 자동 생성 테스트 코드 작성
  - 파일 업로드 → message_id 저장 → /watch/{id} 링크 생성 확인
  - DB에 web_link 필드 추가 확인

- [ ] Sub-task: 봇 응답에 스트리밍 링크 버튼 추가 구현
  ```python
  # 예시:
  # [📱 텔레그램에서 보기] [🌐 브라우저에서 보기]
  ```

- [ ] Sub-task: 기존 캐시된 영상도 스트리밍 링크 제공하도록 개선
  - URL 재요청 시 캐시 확인 → 스트리밍 링크도 함께 제공

**검증 프로토콜:**
1. 새 영상 다운로드 → Bin Channel 확인 → 웹 링크 클릭 → 재생 확인
2. 같은 URL 재요청 → 캐시 사용 → 웹 링크 정상 작동 확인

---

### Task 9.2: URL 단축 기능 (개인용 간소화)
**목적:** 긴 스트리밍 URL을 짧게 변환

#### Sub-tasks:
- [ ] Sub-task: Hash 기반 짧은 ID 생성 로직 테스트 코드 작성
  ```python
  # 예시:
  # /watch/507f1f77bcf86cd799439011 → /w/a7b3c9
  # hashlib.sha256(message_id).hexdigest()[:6]
  ```

- [ ] Sub-task: 짧은 URL 라우팅 구현 (FastAPI)
  ```python
  @app.get("/w/{short_id}")
  async def short_watch(short_id: str):
      # short_id → message_id 조회 → /watch/{message_id} 리다이렉트
  ```

- [ ] Sub-task: DB에 short_id 필드 추가 및 매핑 테이블 구현
  ```python
  # MongoDB:
  # { "short_id": "a7b3c9", "message_id": "507f..." }
  ```

- [ ] Sub-task: 봇 응답 메시지에 짧은 URL 표시
  ```
  🌐 스트리밍: http://localhost:8000/w/a7b3c9
  ```

**검증 프로토콜:**
1. 영상 다운로드 → 짧은 URL 확인
2. 짧은 URL 클릭 → 리다이렉트 → 재생 확인
3. DB에서 short_id 매핑 확인

---

### Task 9.3: 공유 기능 개선 (개인용 최적화)
**목적:** 모바일/PC 간 빠른 접근

#### Sub-tasks:
- [ ] Sub-task: QR 코드 생성 기능 추가 (선택)
  ```python
  # qrcode 라이브러리 사용
  # QR 이미지를 봇 메시지에 첨부
  ```

- [ ] Sub-task: 스트리밍 페이지에 다운로드 버튼 추가
  ```html
  <!-- watch.html에 다운로드 링크 추가 -->
  <a href="/download/{message_id}">💾 다운로드</a>
  ```

- [ ] Sub-task: 즐겨찾기/북마크 기능 (선택)
  ```
  /bookmark - 자주 보는 영상 목록 저장
  ```

**검증 프로토콜:**
1. 모바일에서 QR 스캔 → 재생 확인
2. 스트리밍 페이지에서 다운로드 → 파일 저장 확인

---

### Task 9.4: Conductor - User Manual Verification 'Phase 9'

**검증 항목:**
1. ✅ Bin Channel에 파일 업로드 확인
2. ✅ 웹 스트리밍 링크 생성 확인
3. ✅ 짧은 URL로 접근 가능 확인
4. ✅ 캐시된 영상도 웹 링크 제공 확인
5. ✅ 모바일/PC 모두 재생 확인

**자동화 테스트:**
```bash
pytest tests/test_web_integration.py -v
pytest tests/test_url_shortener.py -v
pytest --cov=src --cov-report=html
```

**수동 검증 순서:**
1. 새 YouTube URL 전송
2. 품질 선택 → 다운로드 완료 대기
3. 봇 응답에서 [🌐 브라우저에서 보기] 버튼 클릭
4. 브라우저에서 재생 확인
5. 같은 URL 재전송 → 캐시 사용 → 웹 링크 확인
6. 짧은 URL 복사 → 다른 브라우저/기기에서 접속
7. QR 코드 스캔 (모바일) → 재생 확인

---

## Phase 10: Multi-Client 아키텍처 (선택) ⚙️

**⚠️ 개인용 주의사항:**
- 단일 사용자이므로 불필요할 가능성 높음
- Telegram API rate limit 걱정 없음
- 복잡도 증가 vs 실용성 낮음
- **권장: 나중에 필요시 구현**

### Task 10.1: Multi-Client 설계 및 환경 설정

#### Sub-tasks:
- [ ] Sub-task: 추가 Bot Token 발급 및 환경 변수 설정
  ```env
  # .env
  BOT_TOKEN_1=...  # 주 봇
  BOT_TOKEN_2=...  # 보조 봇 1
  BOT_TOKEN_3=...  # 보조 봇 2
  ```

- [ ] Sub-task: Client Pool 관리 클래스 설계 테스트 코드 작성
  ```python
  class ClientPool:
      def __init__(self, tokens: List[str])
      async def get_available_client() -> Bot
      async def release_client(client: Bot)
  ```

- [ ] Sub-task: Client Pool 구현 및 로드 밸런싱 로직
  - Round-robin 방식으로 클라이언트 순환
  - 각 클라이언트 사용 횟수 추적

**검증 프로토콜:**
1. 여러 봇 토큰으로 초기화 확인
2. Client Pool에서 사용 가능한 클라이언트 반환 확인

---

### Task 10.2: 파일 업로드 Multi-Client 적용

#### Sub-tasks:
- [ ] Sub-task: 대용량 파일 업로드 시 Client Pool 사용 테스트
  ```python
  # 파일 업로드 시 available client 자동 선택
  client = await pool.get_available_client()
  await client.send_video(...)
  await pool.release_client(client)
  ```

- [ ] Sub-task: Failover 처리 구현
  - 클라이언트 에러 시 다른 클라이언트로 재시도
  - 최대 재시도 횟수 설정

- [ ] Sub-task: Bin Channel 업로드 시 클라이언트 분산
  - 대량 업로드 시 여러 클라이언트로 병렬 처리

**검증 프로토콜:**
1. 대용량 파일 업로드 → 다른 클라이언트 사용 확인
2. 클라이언트 에러 시뮬레이션 → Failover 작동 확인

---

### Task 10.3: 모니터링 및 통계

#### Sub-tasks:
- [ ] Sub-task: 클라이언트별 사용 통계 수집
  ```python
  # 각 클라이언트의 업로드 횟수, 에러 횟수 기록
  stats = {
      "client_1": {"uploads": 10, "errors": 0},
      "client_2": {"uploads": 8, "errors": 1}
  }
  ```

- [ ] Sub-task: /admin_stats 명령어 구현 (개인용)
  ```
  📊 Client Stats:
  🤖 Client 1: 10 uploads, 0 errors
  🤖 Client 2: 8 uploads, 1 error
  ```

**검증 프로토콜:**
1. /admin_stats 실행 → 통계 확인
2. 여러 파일 업로드 후 통계 업데이트 확인

---

### Task 10.4: Conductor - User Manual Verification 'Phase 10'

**검증 항목:**
1. ✅ 여러 봇 클라이언트 동시 초기화 확인
2. ✅ 파일 업로드 시 다른 클라이언트 사용 확인
3. ✅ Failover 작동 확인
4. ✅ 통계 명령어 정상 작동 확인

**자동화 테스트:**
```bash
pytest tests/test_multi_client.py -v
pytest tests/test_client_pool.py -v
```

**수동 검증 순서:**
1. 여러 봇 토큰 설정 후 봇 시작
2. 대용량 파일 업로드 → 로그에서 사용 클라이언트 확인
3. 한 봇 토큰 무효화 → Failover 작동 확인
4. /admin_stats → 통계 확인

---

## 구현 우선순위 (개인용)

### 필수 (Phase 9)
1. ✅ Bin Channel + 웹 스트리밍 통합 (Task 9.1)
2. ✅ URL 단축 (Task 9.2)
3. ⚠️ 공유 기능 (Task 9.3) - 선택적

### 선택 (Phase 10)
4. ⚠️ Multi-Client - **개인용으로는 불필요할 가능성 높음**
   - 필요한 경우: 여러 사람이 동시 사용, API rate limit 문제 발생 시

---

## 예상 일정

### Phase 9 (2-3일)
- Day 1: Task 9.1 (통합 검증)
- Day 2: Task 9.2 (URL 단축)
- Day 3: Task 9.3 (공유 기능) + Task 9.4 (검증)

### Phase 10 (선택, 2-3일)
- Day 1: Task 10.1 (Multi-Client 설계)
- Day 2: Task 10.2 (파일 업로드 적용)
- Day 3: Task 10.3 (모니터링) + Task 10.4 (검증)

---

## 기술 스택 추가

### 새로 추가될 라이브러리
```txt
# URL 단축용
hashlib (stdlib)

# QR 코드 생성용 (선택)
qrcode==7.4.2
pillow==10.1.0

# Multi-Client용 (Phase 10)
# 추가 라이브러리 불필요 (기존 python-telegram-bot 사용)
```

---

## 개인용 사용 시나리오

### 시나리오 1: PC → 모바일 스트리밍
1. PC에서 YouTube URL 전송
2. 다운로드 완료 → 짧은 URL 수신
3. 모바일에서 짧은 URL 접속 → 바로 재생

### 시나리오 2: 오프라인 보관
1. YouTube 영상 다운로드
2. Bin Channel에 영구 저장
3. 원본 삭제되어도 언제든지 재생 가능

### 시나리오 3: 외부 공유 (선택)
1. 친구에게 짧은 URL 전송
2. Telegram 앱 없이 브라우저에서 시청 가능

---

## 참고 사항

### FileToLink과의 차이점 (개인용 최적화)
| 기능 | FileToLink | 이 프로젝트 (개인용) |
|------|------------|---------------------|
| 웹 링크 | ✅ | ✅ Phase 9 |
| Bin Channel | ✅ | ✅ Phase 6 완료 |
| Multi-Client | ✅ | ⚠️ Phase 10 (선택) |
| URL 단축 | ✅ 외부 서비스 | ✅ 자체 hash (Phase 9) |
| Rate Limiting | ✅ 필수 | ❌ 불필요 |
| Admin Panel | ✅ 다중 관리자 | ❌ 개인용 |
| Token Auth | ✅ | ❌ 불필요 |
| YouTube 다운로드 | ❌ | ✅ 핵심 기능 |

### 개인용 장점
- ✅ 복잡도 낮음
- ✅ 유지보수 쉬움
- ✅ 필요한 기능만 구현
- ✅ YouTube 다운로드 + 웹 스트리밍 통합

---

## 다음 단계

**권장 순서:**
1. Phase 9 먼저 완료 (웹 링크 최적화)
2. 사용해보고 Multi-Client 필요성 판단
3. 필요 없으면 Phase 10 스킵
4. 대신 다른 기능 추가 고려:
   - 자막 다운로드
   - 썸네일 자동 생성
   - 시청 기록 관리
   - 플레이리스트 즐겨찾기

**지금 시작하려면:**
```bash
# 현재 plan.md에 Phase 9 추가
# Task 9.1부터 TDD로 진행
```
