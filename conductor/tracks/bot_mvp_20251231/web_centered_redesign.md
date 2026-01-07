# 웹 중심 재설계 로드맵 (개인용 최적화)

**현황 분석 결과**: 이미 웹 인터페이스가 70% 구축됨
**전환 목표**: 텔레그램 봇 의존도 제거, 웹 대시보드를 메인 인터페이스로 전환

---

## 📊 현재 구조 분석

### ✅ 이미 구현된 웹 기능
1. **`/download`** - 웹 다운로드 페이지 (URL 입력 → 텔레그램 업로드)
2. **`/watch/{short_id}`** - 비디오 스트리밍 (Range 요청 지원)
3. **`/gallery`** - 갤러리 (썸네일 그리드)
4. **`/dashboard`** - 대시보드 (통계 + 최근 영상)
5. **`/search`** - 검색 (필터링 지원)
6. **`/edit/{video_id}`** - 비디오 메타데이터 편집
7. **`/api/web-download`** - 웹 다운로드 API (이미 작동 중!)
8. **`/api/upload-file`** - 로컬 파일 업로드

### ❌ 텔레그램 봇에만 있는 기능
1. **플레이리스트 다운로드** - 봇에서만 처리
2. **품질 선택 인터랙션** - 인라인 버튼으로만 가능
3. **진행률 실시간 업데이트** - 봇 메시지 수정
4. **큐 관리** (`/queue` 명령어) - 웹 UI 없음
5. **즐겨찾기 관리** - 웹 UI 없음

### 🔄 중복된 기능
- 검색: 봇 `/search` + 웹 `/search`
- 라이브러리: 봇 `/library` + 웹 `/gallery`
- 통계: 봇 `/stats` + 웹 `/dashboard`

---

## 🎯 재설계 전략

### 핵심 원칙
```
1. 웹 = 메인 인터페이스 (모든 기능)
2. 텔레그램 = 저장소 (Bin Channel) + 선택적 알림
3. 모든 다운로드는 백그라운드 큐로 처리
4. 실시간 진행률은 WebSocket 또는 SSE 사용
```

### 아키텍처 변경
```
Before (현재):
사용자 → 텔레그램 봇 → yt-dlp → Bin Channel
                     ↓
                웹 스트리밍

After (재설계):
사용자 → 웹 대시보드 → 백그라운드 큐 → yt-dlp → Bin Channel
                          ↓                    ↓
                    실시간 진행률         웹 스트리밍
```

---

## Phase 9: 웹 대시보드 완성 (필수)

**목표**: 웹에서 모든 다운로드 작업 처리 가능하도록

### Task 9.1: 다운로드 페이지 개선

#### Sub-tasks:
- [ ] Sub-task: 품질 선택 UI 추가 (드롭다운 또는 라디오 버튼)
  ```html
  <!-- /download 페이지에 추가 -->
  <select id="quality">
    <option value="best">최고 화질</option>
    <option value="1080">1080p</option>
    <option value="720">720p</option>
    <option value="480">480p</option>
    <option value="audio">MP3 (오디오만)</option>
  </select>
  ```

- [ ] Sub-task: 플레이리스트 감지 및 선택 UI 구현
  ```javascript
  // URL 입력 시 자동으로 플레이리스트 확인
  // 플레이리스트 항목 리스트 표시
  // "전체 다운로드" vs "선택 다운로드" 버튼
  ```

- [ ] Sub-task: 다운로드 버튼 클릭 → 백그라운드 큐 추가
  ```python
  # /api/web-download 수정
  # 즉시 다운로드 대신 큐에 추가
  # task_id 반환
  ```

**검증 프로토콜:**
1. 웹 `/download` 접속
2. YouTube URL 입력 → 품질 선택 → 다운로드 시작
3. 플레이리스트 URL 입력 → 목록 표시 → 전체/개별 선택
4. 큐에 추가 확인

---

### Task 9.2: 실시간 진행률 표시 (WebSocket 또는 SSE)

#### Sub-tasks:
- [ ] Sub-task: Server-Sent Events (SSE) 엔드포인트 구현
  ```python
  @app.get("/stream/progress/{task_id}")
  async def stream_progress(task_id: str):
      async def event_generator():
          while True:
              task = await queue_manager.get_task(task_id)
              if not task:
                  break

              data = {
                  "status": task.status.value,
                  "progress": task.progress,
                  "title": task.video_title
              }

              yield f"data: {json.dumps(data)}\n\n"

              if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                  break

              await asyncio.sleep(1)

      return StreamingResponse(
          event_generator(),
          media_type="text/event-stream"
      )
  ```

- [ ] Sub-task: 프론트엔드 SSE 클라이언트 구현
  ```javascript
  // download.html에 추가
  function watchProgress(taskId) {
      const eventSource = new EventSource(`/stream/progress/${taskId}`);

      eventSource.onmessage = (event) => {
          const data = JSON.parse(event.data);
          updateProgressBar(data.progress);
          updateStatus(data.status);
      };
  }
  ```

- [ ] Sub-task: yt-dlp 진행률 → QueueManager 연동
  ```python
  # downloader.py 수정
  def progress_hook(d):
      if d['status'] == 'downloading':
          progress = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
          asyncio.create_task(
              queue_manager.update_progress(task_id, progress)
          )
  ```

**검증 프로토콜:**
1. 웹에서 다운로드 시작
2. 진행률 바 실시간 업데이트 확인
3. 다운로드 완료 → 자동으로 갤러리 링크 표시

---

### Task 9.3: 큐 관리 페이지 추가

#### Sub-tasks:
- [ ] Sub-task: `/queue` 웹 페이지 템플릿 생성
  ```html
  <!-- templates/queue.html -->
  <div class="queue-container">
    <h2>📋 다운로드 큐</h2>

    <!-- 현재 다운로드 -->
    <div class="current-download">
      <h3>⬇️ 다운로드 중</h3>
      <div id="current-task">
        <!-- JavaScript로 동적 업데이트 -->
      </div>
    </div>

    <!-- 대기 중 -->
    <div class="queue-list">
      <h3>⏳ 대기 중 (<span id="queue-count">0</span>)</h3>
      <ul id="queue-items">
        <!-- JavaScript로 동적 업데이트 -->
      </ul>
    </div>
  </div>
  ```

- [ ] Sub-task: 큐 상태 API 엔드포인트 추가
  ```python
  @app.get("/api/queue/{user_id}")
  async def get_queue_status_api(user_id: int):
      from src.queue_manager import get_queue_status
      status = await get_queue_status(user_id)
      return {"success": True, "data": status}
  ```

- [ ] Sub-task: 큐 제어 기능 (일시정지/취소/재시작)
  ```python
  @app.post("/api/queue/{task_id}/pause")
  async def pause_task(task_id: str):
      success = await queue_manager.pause_task(task_id)
      return {"success": success}

  @app.post("/api/queue/{task_id}/cancel")
  async def cancel_task(task_id: str):
      success = await queue_manager.cancel_task(task_id)
      return {"success": success}
  ```

**검증 프로토콜:**
1. 여러 영상 동시 다운로드 요청
2. `/queue` 페이지에서 실시간 상태 확인
3. 일시정지/취소 버튼 작동 확인

---

### Task 9.4: 즐겨찾기 웹 UI 추가

#### Sub-tasks:
- [ ] Sub-task: `/favorites` 웹 페이지 생성
  ```html
  <!-- templates/favorites.html -->
  <!-- gallery.html 레이아웃 재사용 -->
  ```

- [ ] Sub-task: 갤러리/검색에 즐겨찾기 버튼 추가
  ```html
  <!-- 각 비디오 카드에 추가 -->
  <button class="fav-btn" data-video-id="{{ video.id }}">
    ⭐ 즐겨찾기
  </button>
  ```

- [ ] Sub-task: 즐겨찾기 추가/제거 API
  ```python
  @app.post("/api/favorites/{video_id}")
  async def toggle_favorite(video_id: int, user_id: int = Body(...)):
      is_fav = await is_favorite(user_id, video_id)
      if is_fav:
          await remove_favorite(user_id, video_id)
      else:
          await add_favorite(user_id, video_id)
      return {"success": True, "is_favorite": not is_fav}
  ```

**검증 프로토콜:**
1. 갤러리에서 ⭐ 버튼 클릭
2. `/favorites` 페이지 확인
3. 제거 버튼 작동 확인

---

## Phase 10: 텔레그램 봇 역할 축소 (선택)

**목표**: 봇을 알림 전용으로 전환 (다운로드 기능 제거)

### Task 10.1: 봇 명령어 간소화

#### Sub-tasks:
- [ ] Sub-task: 다운로드 관련 명령어 비활성화
  ```python
  # bot.py 수정
  # handle_message() - URL 감지 제거
  # handle_callback() - 품질 선택 제거
  ```

- [ ] Sub-task: 웹 링크 안내 메시지로 대체
  ```python
  async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
      text = update.effective_message.text
      url_pattern = r'https?://...'
      urls = re.findall(url_pattern, text)

      if urls:
          await update.effective_message.reply_text(
              f"🌐 웹 대시보드에서 다운로드하세요!\n"
              f"{BASE_URL}/download?url={urls[0]}"
          )
  ```

- [ ] Sub-task: 유지할 명령어만 보존
  ```python
  # 유지:
  # /start - 웹 링크 안내
  # /help - 웹 사용법
  # /stats - 간단한 통계
  # /link - 웹 대시보드 링크

  # 제거:
  # /library, /search, /favorites (웹으로 대체)
  # /queue (웹으로 대체)
  # 모든 다운로드 관련 기능
  ```

**검증 프로토콜:**
1. 봇에 URL 전송 → 웹 링크 안내 메시지 확인
2. 기존 다운로드 명령어 비활성화 확인
3. 웹에서만 다운로드 가능 확인

---

### Task 10.2: 다운로드 완료 알림 (선택)

#### Sub-tasks:
- [ ] Sub-task: 다운로드 완료 시 텔레그램 알림
  ```python
  # queue_manager.py 수정
  async def complete_task(self, task_id: str, success: bool = True):
      # ... 기존 로직 ...

      if success:
          # 텔레그램 알림 전송
          from telegram import Bot
          bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

          await bot.send_message(
              chat_id=task.user_id,
              text=(
                  f"✅ 다운로드 완료!\n\n"
                  f"🎬 {task.video_title}\n"
                  f"🌐 시청: {BASE_URL}/watch/{short_id}"
              )
          )
  ```

- [ ] Sub-task: 알림 설정 옵션 (웹 설정 페이지)
  ```html
  <!-- /settings 페이지 -->
  <label>
    <input type="checkbox" id="notify-download"> 다운로드 완료 시 알림
  </label>
  <label>
    <input type="checkbox" id="notify-error"> 다운로드 실패 시 알림
  </label>
  ```

**검증 프로토콜:**
1. 웹에서 다운로드 시작
2. 완료 후 텔레그램 알림 수신 확인
3. 설정 페이지에서 알림 끄기 → 알림 안 옴 확인

---

## Phase 11: 고급 웹 기능 추가 (선택)

### Task 11.1: 드래그 앤 드롭 업로드

#### Sub-tasks:
- [ ] Sub-task: 드래그 앤 드롭 존 구현
  ```javascript
  // download.html
  const dropZone = document.getElementById('drop-zone');

  dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      const files = e.dataTransfer.files;
      uploadFiles(files);
  });
  ```

- [ ] Sub-task: 다중 파일 업로드 지원
  ```python
  @app.post("/api/upload-multiple")
  async def upload_multiple_files(
      files: List[UploadFile] = File(...),
      user_id: Optional[int] = Form(None)
  ):
      # 각 파일을 큐에 추가
      task_ids = []
      for file in files:
          task_id = await add_upload_to_queue(file, user_id)
          task_ids.append(task_id)
      return {"success": True, "task_ids": task_ids}
  ```

**검증 프로토콜:**
1. 파일 드래그 → 드롭 존에 드롭
2. 여러 파일 동시 선택 → 업로드
3. 큐에서 순차 처리 확인

---

### Task 11.2: 자동 새로고침 (갤러리/대시보드)

#### Sub-tasks:
- [ ] Sub-task: 갤러리 자동 새로고침 (새 영상 추가 시)
  ```javascript
  // gallery.html
  setInterval(async () => {
      const response = await fetch(`/api/videos?user_id=${userId}&last_id=${lastVideoId}`);
      const data = await response.json();

      if (data.new_videos.length > 0) {
          prependNewVideos(data.new_videos);
      }
  }, 10000); // 10초마다
  ```

- [ ] Sub-task: 대시보드 통계 실시간 업데이트
  ```javascript
  // dashboard.html
  const eventSource = new EventSource(`/stream/stats/${userId}`);
  eventSource.onmessage = (event) => {
      const stats = JSON.parse(event.data);
      updateDashboardStats(stats);
  };
  ```

**검증 프로토콜:**
1. 갤러리 페이지 열어두기
2. 다른 탭에서 다운로드
3. 갤러리 자동 업데이트 확인

---

### Task 11.3: 모바일 반응형 UI 최적화

#### Sub-tasks:
- [ ] Sub-task: 모바일 레이아웃 개선
  ```css
  /* 모바일 우선 CSS */
  @media (max-width: 768px) {
      .gallery-grid {
          grid-template-columns: repeat(2, 1fr);
      }
      .video-card {
          font-size: 0.9rem;
      }
  }
  ```

- [ ] Sub-task: 터치 제스처 지원
  ```javascript
  // 스와이프로 영상 삭제
  // 롱 프레스로 옵션 메뉴
  ```

**검증 프로토콜:**
1. 모바일 브라우저 접속
2. 모든 페이지 레이아웃 확인
3. 터치 제스처 작동 확인

---

## 🗺️ 전체 로드맵 요약

### 필수 구현 (Phase 9)
```
Week 1-2: Task 9.1 - 다운로드 페이지 개선
         - 품질 선택 UI
         - 플레이리스트 지원
         - 큐 시스템 연동

Week 3: Task 9.2 - 실시간 진행률
        - SSE 구현
        - 프론트엔드 연동

Week 4: Task 9.3 - 큐 관리 페이지
        Task 9.4 - 즐겨찾기 웹 UI
```

### 선택 구현 (Phase 10-11)
```
Week 5: Task 10.1 - 봇 간소화
        Task 10.2 - 알림 기능

Week 6+: Task 11.x - 고급 기능
         - 드래그 앤 드롭
         - 자동 새로고침
         - 모바일 최적화
```

---

## 📐 새로운 웹 아키텍처

### 페이지 구조
```
/ (루트)
├── /dashboard          ← 메인 페이지 (통계 + 최근 영상)
├── /download           ← 다운로드 (URL 입력 + 품질 선택)
├── /queue              ← 큐 관리 (진행률 + 제어)
├── /gallery            ← 전체 갤러리
├── /favorites          ← 즐겨찾기
├── /search             ← 검색
├── /watch/{short_id}   ← 스트리밍
└── /settings           ← 설정 (알림 옵션 등)
```

### API 엔드포인트
```
POST /api/web-download        ← URL 다운로드 (큐 추가)
POST /api/upload-file          ← 파일 업로드 (큐 추가)
GET  /api/queue/{user_id}      ← 큐 상태 조회
POST /api/queue/{task_id}/pause   ← 일시정지
POST /api/queue/{task_id}/cancel  ← 취소
GET  /stream/progress/{task_id}   ← SSE 진행률
POST /api/favorites/{video_id}    ← 즐겨찾기 토글
```

### 백그라운드 작업자
```python
# worker.py (새 파일)
async def process_download_queue():
    while True:
        for user_id in queue_manager.queues.keys():
            task = await queue_manager.get_next_task(user_id)
            if task:
                await download_and_upload(task)
        await asyncio.sleep(1)

# server.py에서 시작
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_download_queue())
```

---

## 🎨 UI/UX 개선 방향

### 다운로드 페이지 목표
```
Before (현재):
URL 입력 → 제출 → 기다림 → 결과

After (재설계):
URL 입력 → 품질 선택 → 큐 추가
         ↓
      실시간 진행률 표시 (같은 페이지)
         ↓
      완료 → "시청하기" 버튼 표시
```

### 갤러리 페이지 목표
```
- 썸네일 그리드 (이미 있음 ✅)
- ⭐ 즐겨찾기 버튼 각 카드에
- 🗑️ 삭제 버튼 (hover 시 표시)
- 필터: 전체/즐겨찾기/최근
- 정렬: 최신순/조회순/이름순
```

### 큐 페이지 목표
```
현재 다운로드:
━━━━━━━━━━━━━━━━ 75% (45초 남음)
🎬 제목...
[⏸ 일시정지] [❌ 취소]

대기 중 (3):
1. 🎬 영상 1 (720p)
2. 🎬 영상 2 (1080p)
3. 🎬 영상 3 (MP3)
```

---

## 🚀 시작하기

### 현재 우선순위
1. **Task 9.1** - 다운로드 페이지 개선 (가장 중요!)
2. **Task 9.2** - 실시간 진행률
3. **Task 9.3** - 큐 관리 페이지

**Phase 9만 완료해도 웹에서 모든 기능 사용 가능합니다!**

### 다음 단계
```bash
# 1. Task 9.1부터 시작
# 2. download.html 수정 - 품질 선택 UI 추가
# 3. /api/web-download 수정 - 큐 시스템 연동
# 4. 프론트엔드 JavaScript로 SSE 진행률 표시
```

**텔레그램 봇은 Phase 10에서 간소화 (선택사항)**

---

## 💡 장점 요약

### 웹 중심 전환 후
✅ **사용성**: 브라우저에서 모든 작업 완료
✅ **접근성**: PC/모바일 어디서나 동일한 경험
✅ **효율성**: 큐 시스템으로 대량 다운로드 관리
✅ **확장성**: 나중에 친구와 공유 시 웹 링크만 전송
✅ **개인화**: 설정, 테마, 레이아웃 커스터마이징

### 텔레그램 역할
🔔 **알림**: 다운로드 완료 알림 (선택)
💾 **저장소**: Bin Channel (영구 저장)
📱 **옵션**: 간단한 조회 (선택)

---

## 📝 참고 사항

### 기존 코드 재사용
- **`/api/web-download`**: 이미 작동 중 → 큐 연동만 추가
- **갤러리/대시보드**: 완성됨 → 즐겨찾기 버튼만 추가
- **스트리밍**: Range 요청 지원 완료 ✅

### 새로 추가할 파일
```
templates/queue.html         - 큐 관리 페이지
templates/favorites.html     - 즐겨찾기 페이지
static/css/dashboard.css     - 통합 CSS
static/js/queue.js           - 큐 관리 JavaScript
static/js/sse-client.js      - SSE 진행률 클라이언트
```

### 환경 변수 추가
```env
# .env
WEB_NOTIFICATIONS=true        # 웹 푸시 알림 활성화
TELEGRAM_NOTIFICATIONS=false  # 텔레그램 알림 비활성화 (개인용)
MAX_CONCURRENT_DOWNLOADS=3    # 동시 다운로드 수
```
