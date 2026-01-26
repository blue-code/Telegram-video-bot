// TVB Navigation Component
// 모든 페이지에서 사용 가능한 반응형 네비게이션

(function() {
    // 네비게이션 HTML 생성
    function createNavigation(userId, currentPage = '') {
        const navHTML = `
            <link rel="stylesheet" href="/static/theme.css">
            <style>
                .tvb-nav {
                    --nav-bg: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(12, 74, 110, 0.88));
                    --nav-accent: #f59e0b;
                    --nav-ink: #f8fafc;
                    --nav-ink-muted: rgba(248, 250, 252, 0.6);
                    --nav-border: rgba(148, 163, 184, 0.2);
                    font-family: "Pretendard", "Noto Sans KR", "Apple SD Gothic Neo",
                        "Malgun Gothic", "Nanum Gothic", sans-serif;
                    background: var(--nav-bg);
                    border-bottom: 1px solid var(--nav-border);
                    position: sticky;
                    top: 0;
                    z-index: 1000;
                    margin-bottom: 32px;
                    box-shadow: 0 24px 60px rgba(15, 23, 42, 0.35);
                }

                .tvb-nav::after {
                    content: "";
                    display: block;
                    height: 3px;
                    background: linear-gradient(90deg, var(--nav-accent), rgba(56, 189, 248, 0.2));
                    opacity: 0.9;
                }

                .tvb-nav-container {
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 16px 24px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 16px;
                }

                .tvb-nav-brand {
                    font-weight: 800;
                    color: var(--nav-ink);
                    text-decoration: none;
                    font-size: 1.25rem;
                    letter-spacing: -0.03em;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    text-transform: uppercase;
                }

                .tvb-nav-brand span {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 32px;
                    height: 32px;
                    border-radius: 10px;
                    background: rgba(245, 158, 11, 0.18);
                    border: 1px solid rgba(245, 158, 11, 0.4);
                }

                .tvb-nav-toggle {
                    display: none;
                    background: rgba(15, 23, 42, 0.5);
                    border: 1px solid var(--nav-border);
                    border-radius: 10px;
                    color: var(--nav-ink);
                    font-size: 1.4rem;
                    cursor: pointer;
                    padding: 6px 10px;
                    transition: all 0.2s;
                }

                .tvb-nav-toggle:hover {
                    border-color: rgba(245, 158, 11, 0.6);
                    transform: translateY(-1px);
                }

                .tvb-nav-links {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                    flex-wrap: wrap;
                    justify-content: flex-end;
                }

                .tvb-nav-links a {
                    color: var(--nav-ink-muted);
                    text-decoration: none;
                    font-size: 0.85rem;
                    font-weight: 600;
                    padding: 8px 14px;
                    border-radius: 999px;
                    border: 1px solid transparent;
                    transition: all 0.2s ease;
                    background: rgba(15, 23, 42, 0.35);
                }

                .tvb-nav-links a:hover {
                    color: var(--nav-ink);
                    border-color: rgba(245, 158, 11, 0.45);
                    background: rgba(15, 23, 42, 0.6);
                }

                .tvb-nav-links a.active {
                    color: #0f172a;
                    background: var(--nav-accent);
                    border-color: var(--nav-accent);
                    font-weight: 700;
                    box-shadow: 0 10px 24px rgba(245, 158, 11, 0.3);
                }

                /* 모바일 메뉴 (900px 이하) */
                @media (max-width: 900px) {
                    .tvb-nav-toggle {
                        display: block;
                    }

                    .tvb-nav-links {
                        display: none;
                        position: absolute;
                        top: 100%;
                        left: 0;
                        right: 0;
                        flex-direction: column;
                        background: rgba(15, 23, 42, 0.98);
                        border-bottom: 1px solid var(--nav-border);
                        padding: 20px;
                        gap: 12px;
                        align-items: stretch;
                    }

                    .tvb-nav-links.open {
                        display: flex !important;
                    }

                    .tvb-nav-links a {
                        text-align: center;
                        padding: 12px;
                        border-radius: 14px;
                        background: rgba(30, 41, 59, 0.7);
                        border: 1px solid var(--nav-border);
                    }
                }
            </style>

            <nav class="tvb-nav">
                <div class="tvb-nav-container">
                    <a class="tvb-nav-brand" href="/dashboard/${userId}">
                        <span>📚</span> TVB
                    </a>
                    <button class="tvb-nav-toggle" id="tvb-nav-toggle-btn" type="button">☰</button>
                    <div class="tvb-nav-links" id="tvb-nav-links">
                        <a href="/dashboard/${userId}" ${currentPage === 'dashboard' ? 'class="active"' : ''}>대시보드</a>
                        <a href="/gallery/${userId}" ${currentPage === 'gallery' ? 'class="active"' : ''}>갤러리</a>
                        <a href="/favorites/${userId}" ${currentPage === 'favorites' ? 'class="active"' : ''}>즐겨찾기</a>
                        <a href="/encoded/${userId}" ${currentPage === 'encoded' ? 'class="active"' : ''}>인코딩됨</a>
                        <a href="/books/${userId}" ${currentPage === 'books' ? 'class="active"' : ''}>eBook</a>
                        <a href="/comics/${userId}" ${currentPage === 'comics' ? 'class="active"' : ''}>만화책</a>
                        <a href="/files/${userId}" ${currentPage === 'files' ? 'class="active"' : ''}>파일</a>
                        <a href="/search?user_id=${userId}" ${currentPage === 'search' ? 'class="active"' : ''}>검색</a>
                        <a href="/download?user_id=${userId}" ${currentPage === 'download' ? 'class="active"' : ''}>업로드</a>
                    </div>
                </div>
            </nav>
        `;

        return navHTML;
    }

    // 네비게이션 토글 함수
    window.toggleTVBNav = function() {
        const navLinks = document.getElementById('tvb-nav-links');

        if (!navLinks) {
            console.error('❌ Nav links element not found!');
            return;
        }

        const isOpen = navLinks.classList.contains('open');

        if (isOpen) {
            // 닫기
            navLinks.classList.remove('open');
            console.log('🔴 Menu CLOSED');
        } else {
            // 열기
            navLinks.classList.add('open');
            console.log('🟢 Menu OPENED');
        }
    };

    // 네비게이션 삽입 함수
    window.insertTVBNav = function(userId, currentPage = '') {
        const navContainer = document.getElementById('tvb-nav-container');
        if (navContainer) {
            navContainer.innerHTML = createNavigation(userId, currentPage);
            console.log('✅ Navigation inserted');

            // 이벤트 리스너 등록
            setTimeout(() => {
                const toggle = document.getElementById('tvb-nav-toggle-btn');

                if (toggle) {
                    toggle.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('🔘 Toggle button clicked');
                        toggleTVBNav();
                    });
                    console.log('✅ Toggle button event registered');
                }
            }, 10);
        }
    };

    // 외부 클릭 시 메뉴 닫기
    document.addEventListener('click', function(event) {
        const navLinks = document.getElementById('tvb-nav-links');
        const toggle = document.getElementById('tvb-nav-toggle-btn');

        if (!navLinks || !toggle) return;

        // 메뉴가 닫혀있으면 무시
        if (!navLinks.classList.contains('open')) {
            return;
        }

        // 토글 버튼 클릭은 무시
        if (toggle.contains(event.target)) {
            return;
        }

        // 메뉴 내부 클릭은 무시
        if (navLinks.contains(event.target)) {
            return;
        }

        // 외부 클릭 → 메뉴 닫기
        navLinks.classList.remove('open');
        console.log('🔴 Menu CLOSED (outside click)');
    });
})();
