// TVB Navigation Component
// 모든 페이지에서 사용 가능한 반응형 네비게이션

(function() {
    // 네비게이션 HTML 생성
    function createNavigation(userId, currentPage = '') {
        const navHTML = `
            <style>
                /* iPhone Safari 호환성 */
                html, body {
                    overflow-x: hidden;
                    position: relative;
                }

                .tvb-nav {
                    background: rgba(0,0,0,0.35);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    padding: 12px 16px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    position: relative;
                    z-index: 1000;
                }

                .tvb-nav-container {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    position: relative;
                    z-index: 1001;
                }

                .tvb-nav-brand {
                    font-weight: 700;
                    color: #fff;
                    text-decoration: none;
                    font-size: 20px;
                    flex-shrink: 0;
                }

                .tvb-nav-toggle {
                    display: none;
                    background: rgba(255,255,255,0.1);
                    border: 2px solid rgba(255,255,255,0.2);
                    border-radius: 8px;
                    color: #fff;
                    font-size: 24px;
                    cursor: pointer;
                    padding: 8px 12px;
                    transition: all 0.3s;
                    -webkit-tap-highlight-color: transparent;
                }

                .tvb-nav-toggle:active {
                    background: rgba(255,255,255,0.3);
                    transform: scale(0.95);
                }

                .tvb-nav-links {
                    display: flex;
                    gap: 5px;
                    align-items: center;
                    flex-wrap: wrap; /* 허용된 공간 내 줄바꿈 */
                }

                .tvb-nav-links a {
                    color: #fff;
                    text-decoration: none;
                    font-size: 14px;
                    padding: 6px 12px;
                    border-radius: 999px;
                    background: rgba(255,255,255,0.08);
                    white-space: nowrap;
                    transition: all 0.3s;
                }

                .tvb-nav-links a:hover {
                    background: rgba(255,255,255,0.25);
                }

                .tvb-nav-links a.active {
                    background: rgba(102, 126, 234, 0.5);
                    font-weight: 600;
                    border: 1px solid rgba(102, 126, 234, 0.8);
                }

                /* 모바일 메뉴 (768px 이하) */
                @media (max-width: 768px) {
                    .tvb-nav {
                        position: relative;
                        isolation: isolate;
                    }

                    .tvb-nav-toggle {
                        display: block;
                        z-index: 10001;
                        position: relative;
                    }

                    .tvb-nav-links {
                        display: none;
                        position: fixed;
                        top: 70px;
                        left: 10px;
                        right: 10px;
                        width: calc(100vw - 20px);
                        flex-direction: column;
                        background: #1a1a1a;
                        border-radius: 12px;
                        padding: 16px;
                        gap: 8px;
                        z-index: 10000;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.9);
                        border: 2px solid rgba(255,255,255,0.2);
                        transform: translateZ(0);
                        -webkit-transform: translateZ(0);
                        pointer-events: auto;
                    }

                    .tvb-nav-links.open {
                        display: flex !important;
                    }

                    .tvb-nav-links a {
                        width: 100%;
                        text-align: center;
                        padding: 14px 12px;
                        font-size: 16px;
                        display: block;
                        border-radius: 8px;
                        background: rgba(255,255,255,0.05);
                        pointer-events: auto;
                        cursor: pointer;
                    }

                    .tvb-nav-links a:active {
                        background: rgba(255,255,255,0.2);
                    }
                }

                /* 작은 태블릿 (600px 이하) */
                @media (max-width: 600px) {
                    .tvb-nav-brand {
                        font-size: 18px;
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