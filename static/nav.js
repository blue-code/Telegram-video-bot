// TVB Navigation Component
// 모든 페이지에서 사용 가능한 반응형 네비게이션

(function() {
    // 네비게이션 HTML 생성
    function createNavigation(userId, currentPage = '') {
        const navHTML = `
            <link rel="stylesheet" href="/static/theme.css">
            <style>
                .tvb-nav {
                    background: var(--bg-glass);
                    backdrop-filter: var(--blur-glass);
                    -webkit-backdrop-filter: var(--blur-glass);
                    padding: 12px 0;
                    border-bottom: 1px solid var(--border-subtle);
                    position: sticky;
                    top: 0;
                    z-index: 1000;
                    margin-bottom: 30px;
                }

                .tvb-nav-container {
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 0 20px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }

                .tvb-nav-brand {
                    font-weight: 800;
                    color: var(--text-primary);
                    text-decoration: none;
                    font-size: 1.25rem;
                    letter-spacing: -0.02em;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }

                .tvb-nav-toggle {
                    display: none;
                    background: transparent;
                    border: 1px solid var(--border-subtle);
                    border-radius: var(--radius-sm);
                    color: var(--text-primary);
                    font-size: 1.5rem;
                    cursor: pointer;
                    padding: 4px 8px;
                    transition: all 0.2s;
                }

                .tvb-nav-toggle:hover {
                    background: var(--bg-surface);
                    border-color: var(--border-active);
                }

                .tvb-nav-links {
                    display: flex;
                    gap: 4px;
                    align-items: center;
                }

                .tvb-nav-links a {
                    color: var(--text-secondary);
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                    padding: 8px 12px;
                    border-radius: var(--radius-full);
                    transition: all 0.2s ease;
                }

                .tvb-nav-links a:hover {
                    color: var(--text-primary);
                    background: rgba(255, 255, 255, 0.05);
                }

                .tvb-nav-links a.active {
                    color: var(--bg-app);
                    background: var(--text-primary);
                    font-weight: 600;
                }

                /* 모바일 메뉴 (768px 이하) */
                @media (max-width: 768px) {
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
                        background: var(--bg-app);
                        border-bottom: 1px solid var(--border-subtle);
                        padding: 16px;
                        gap: 8px;
                        align-items: stretch;
                    }

                    .tvb-nav-links.open {
                        display: flex !important;
                    }

                    .tvb-nav-links a {
                        text-align: center;
                        padding: 12px;
                        border-radius: var(--radius-md);
                        background: var(--bg-surface);
                        border: 1px solid var(--border-subtle);
                    }
                    
                    .tvb-nav-links a.active {
                        background: var(--text-primary);
                        color: var(--bg-app);
                        border-color: var(--text-primary);
                    }
                }
            </style>

            <nav class="tvb-nav">
                <div class="tvb-nav-container">
                    <a class="tvb-nav-brand" href="/dashboard/${userId}">📚 TVB</a>
                    <button class="tvb-nav-toggle" id="tvb-nav-toggle-btn" type="button">☰</button>
                    <div class="tvb-nav-links" id="tvb-nav-links">
                        <a href="/dashboard/${userId}" ${currentPage === 'dashboard' ? 'class="active"' : ''}>대시보드</a>
                        <a href="/gallery/${userId}" ${currentPage === 'gallery' ? 'class="active"' : ''}>갤러리</a>
                        <a href="/favorites/${userId}" ${currentPage === 'favorites' ? 'class="active"' : ''}>⭐ 즐겨찾기</a>
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