/**
 * Bookmarks and Series Management - Client Side
 * Handles completion status, bookmarks, and series creation for EPUB and Comics
 */

// ============================================================
// Read Completion Functions
// ============================================================

async function toggleCompletion(fileId, contentType, currentStatus) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch('/api/completion/mark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: fileId,
                content_type: contentType,
                is_completed: !currentStatus
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update completion status');
        }

        const data = await response.json();
        return data.data.is_completed;
    } catch (error) {
        console.error('Error toggling completion:', error);
        alert('읽음 상태 변경 실패');
        return currentStatus;
    }
}

async function getCompletionStatus(fileId, contentType) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/completion/status/${contentType}/${fileId}?user_id=${userId}`);

        if (!response.ok) {
            throw new Error('Failed to get completion status');
        }

        const data = await response.json();
        return data.is_completed;
    } catch (error) {
        console.error('Error getting completion status:', error);
        return false;
    }
}

// ============================================================
// Bookmark Functions
// ============================================================

async function createBookmark(fileId, contentType, position, title, note = null) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/bookmarks?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: fileId,
                content_type: contentType,
                bookmark_position: position,
                title: title,
                note: note
            })
        });

        if (!response.ok) {
            throw new Error('Failed to create bookmark');
        }

        const data = await response.json();
        if (!data || !Array.isArray(data.data)) {
            return [];
        }
        return data.data;
    } catch (error) {
        console.error('Error creating bookmark:', error);
        alert('북마크 생성 실패');
        return null;
    }
}

async function getBookmarks(fileId, contentType) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/bookmarks?user_id=${userId}&file_id=${fileId}&content_type=${contentType}`);

        if (!response.ok) {
            throw new Error('Failed to get bookmarks');
        }

        const data = await response.json();
        return data.data;
    } catch (error) {
        console.error('Error getting bookmarks:', error);
        return [];
    }
}

async function deleteBookmark(bookmarkId) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/bookmarks/${bookmarkId}?user_id=${userId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete bookmark');
        }

        return true;
    } catch (error) {
        console.error('Error deleting bookmark:', error);
        alert('북마크 삭제 실패');
        return false;
    }
}

// ============================================================
// Series Functions
// ============================================================

async function createSeries(title, description, contentType) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/series?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                description: description,
                content_type: contentType
            })
        });

        if (!response.ok) {
            throw new Error('Failed to create series');
        }

        const data = await response.json();
        return data.data;
    } catch (error) {
        console.error('Error creating series:', error);
        alert('시리즈 생성 실패');
        return null;
    }
}

async function getUserSeries(contentType = null) {
    try {
        const userId = getUserIdFromPage();
        let url = `/api/series?user_id=${userId}`;
        if (contentType) {
            url += `&content_type=${contentType}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Failed to get series');
        }

        const data = await response.json();
        return data.data;
    } catch (error) {
        console.error('Error getting series:', error);
        return [];
    }
}

async function addToSeries(seriesId, fileId, contentType, order = null) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/series/${seriesId}/items?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: fileId,
                content_type: contentType,
                item_order: order
            })
        });

        if (!response.ok) {
            throw new Error('Failed to add to series');
        }

        return true;
    } catch (error) {
        console.error('Error adding to series:', error);
        alert('시리즈 추가 실패');
        return false;
    }
}

async function removeFromSeries(seriesId, fileId) {
    try {
        const userId = getUserIdFromPage();
        const response = await fetch(`/api/series/${seriesId}/items/${fileId}?user_id=${userId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to remove from series');
        }

        return true;
    } catch (error) {
        console.error('Error removing from series:', error);
        alert('시리즈에서 제거 실패');
        return false;
    }
}

// ============================================================
// UI Helper Functions
// ============================================================

function getUserIdFromPage() {
    // Extract user_id from current URL or page context
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('user_id') || window.DEFAULT_USER_ID || '41509535';
}

function showSeriesSelectionModal(fileId, contentType) {
    // Show modal for selecting/creating series
    const modal = document.getElementById('series-modal');
    if (!modal) {
        createSeriesModal();
    }

    loadSeriesOptions(fileId, contentType);
    document.getElementById('series-modal').style.display = 'flex';
}

function createSeriesModal() {
    const modalHTML = `
        <div id="series-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 10000; align-items: center; justify-content: center;">
            <div style="background: white; padding: 30px; border-radius: 10px; max-width: 500px; width: 90%;">
                <h2 style="margin-top: 0;">시리즈에 추가</h2>

                <div id="series-list" style="max-height: 300px; overflow-y: auto; margin-bottom: 20px;">
                    <!-- Series options will be loaded here -->
                </div>

                <div style="margin-bottom: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
                    <h3 style="margin-top: 0;">새 시리즈 만들기</h3>
                    <input type="text" id="new-series-title" placeholder="시리즈 제목" style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 5px;">
                    <textarea id="new-series-desc" placeholder="설명 (선택)" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; resize: vertical;"></textarea>
                    <button onclick="createNewSeriesAndAdd()" style="margin-top: 10px; padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">생성 및 추가</button>
                </div>

                <button onclick="closeSeriesModal()" style="padding: 10px 20px; background: #666; color: white; border: none; border-radius: 5px; cursor: pointer;">취소</button>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

async function loadSeriesOptions(fileId, contentType) {
    const seriesList = document.getElementById('series-list');
    const series = await getUserSeries(contentType);

    if (series.length === 0) {
        seriesList.innerHTML = '<p style="color: #666;">아직 시리즈가 없습니다.</p>';
        return;
    }

    seriesList.innerHTML = series.map(s => `
        <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px; cursor: pointer; hover: background: #f5f5f5;" onclick="addToExistingSeries(${s.id}, '${fileId}', '${contentType}')">
            <strong>${s.title}</strong>
            ${s.description ? `<p style="margin: 5px 0 0 0; font-size: 0.9em; color: #666;">${s.description}</p>` : ''}
            <p style="margin: 5px 0 0 0; font-size: 0.85em; color: #999;">${s.completed_items || 0}/${s.total_items || 0} 완료</p>
        </div>
    `).join('');

    // Store current file info for later use
    window.currentSeriesFile = { fileId, contentType };
}

async function addToExistingSeries(seriesId, fileId, contentType) {
    const success = await addToSeries(seriesId, fileId, contentType);
    if (success) {
        alert('시리즈에 추가되었습니다!');
        closeSeriesModal();
        location.reload();  // Refresh to show updated series
    }
}

async function createNewSeriesAndAdd() {
    const title = document.getElementById('new-series-title').value.trim();
    const desc = document.getElementById('new-series-desc').value.trim();

    if (!title) {
        alert('시리즈 제목을 입력해주세요');
        return;
    }

    const { fileId, contentType } = window.currentSeriesFile;

    const series = await createSeries(title, desc || null, contentType);
    if (series) {
        const success = await addToSeries(series.id, fileId, contentType, 1);
        if (success) {
            alert('시리즈가 생성되고 책이 추가되었습니다!');
            closeSeriesModal();
            location.reload();
        }
    }
}

function closeSeriesModal() {
    document.getElementById('series-modal').style.display = 'none';
}

// ============================================================
// Visual Status Indicators
// ============================================================

function addCompletionBadge(element, isCompleted) {
    const badge = document.createElement('div');
    badge.className = 'completion-badge';
    badge.innerHTML = isCompleted ? '✓ 완료' : '';
    badge.style.cssText = `
        position: absolute;
        top: 10px;
        right: 10px;
        background: ${isCompleted ? '#4CAF50' : 'transparent'};
        color: white;
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 0.85em;
        font-weight: bold;
        z-index: 10;
    `;

    element.style.position = 'relative';
    element.appendChild(badge);
}

function updateCompletionBadge(element, isCompleted) {
    const badge = element.querySelector('.completion-badge');
    if (badge) {
        badge.innerHTML = isCompleted ? '✓ 완료' : '';
        badge.style.background = isCompleted ? '#4CAF50' : 'transparent';
    } else {
        addCompletionBadge(element, isCompleted);
    }
}

// ============================================================
// Bulk Series Creation Functions
// ============================================================

// Global state for bulk selection
window.bulkSelectionState = {
    enabled: true,  // Always enabled
    selectedItems: [],
    contentType: null,
    allSelected: false
};

// Initialize checkboxes on page load
function initializeCheckboxes(contentType) {
    const state = window.bulkSelectionState;
    state.contentType = contentType;
    state.enabled = true;

    // Add checkboxes to all cards
    addCheckboxesToCards(contentType);
}

function addCheckboxesToCards(contentType) {
    const cardSelector = contentType === 'epub' ? '.book-card' : '.comic-card';
    const cards = document.querySelectorAll(cardSelector);

    cards.forEach(card => {
        // Check if checkbox already exists
        const existingCheckbox = card.querySelector('.item-checkbox');
        if (existingCheckbox) return;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'item-checkbox';
        checkbox.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            width: 24px;
            height: 24px;
            cursor: pointer;
            z-index: 100;
            pointer-events: auto;
            background: white;
            border: 2px solid #667eea;
            border-radius: 4px;
        `;

        // Get file ID from onclick attribute
        const onclickAttr = card.getAttribute('onclick');
        let fileId;
        if (contentType === 'epub') {
            fileId = onclickAttr.match(/\/read\/(.+?)\?/)?.[1];
        } else {
            fileId = onclickAttr.match(/\/comic_reader\/(.+?)\?/)?.[1];
        }

        checkbox.dataset.fileId = fileId;
        checkbox.dataset.contentType = contentType;

        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();  // Prevent card click
            handleCheckboxChange(e.target);
        });

        const cover = card.querySelector('.book-cover, .comic-cover');
        if (cover) {
            cover.style.position = 'relative';
            cover.appendChild(checkbox);
        }
    });
}

function handleCheckboxChange(checkbox) {
    const state = window.bulkSelectionState;
    const fileId = checkbox.dataset.fileId;
    const contentType = checkbox.dataset.contentType;

    if (checkbox.checked) {
        // Add to selection
        if (!state.selectedItems.find(item => item.fileId === fileId)) {
            state.selectedItems.push({ fileId, contentType });
        }
    } else {
        // Remove from selection
        state.selectedItems = state.selectedItems.filter(item => item.fileId !== fileId);
    }

    // Show or hide bulk action panel based on selection
    if (state.selectedItems.length > 0) {
        showBulkActionPanel();
    } else {
        const panel = document.getElementById('bulk-action-panel');
        if (panel) panel.style.display = 'none';
    }

    updateBulkActionPanel();
    updateSelectAllButton();
}

function showBulkActionPanel() {
    let panel = document.getElementById('bulk-action-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'bulk-action-panel';
        panel.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            z-index: 10000;
            color: white;
            display: flex;
            gap: 15px;
            align-items: center;
        `;

        panel.innerHTML = `
            <span id="selection-count" style="font-weight: bold;">선택: 0개</span>
            <button onclick="createSeriesFromSelection()" style="padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold;">
                시리즈 생성
            </button>
            <button onclick="clearSelection()" style="padding: 10px 20px; background: rgba(255,255,255,0.2); color: white; border: none; border-radius: 8px; cursor: pointer;">
                선택 해제
            </button>
        `;

        document.body.appendChild(panel);
    } else {
        panel.style.display = 'flex';
    }

    updateBulkActionPanel();
}

function updateBulkActionPanel() {
    const state = window.bulkSelectionState;
    const countSpan = document.getElementById('selection-count');
    if (countSpan) {
        countSpan.textContent = `선택: ${state.selectedItems.length}개`;
    }
}

function updateSelectAllButton() {
    const btn = document.getElementById('select-all-btn');
    if (!btn) return;

    const state = window.bulkSelectionState;
    const checkboxes = document.querySelectorAll('.item-checkbox');

    if (checkboxes.length === 0) return;

    const allChecked = state.selectedItems.length === checkboxes.length;
    state.allSelected = allChecked;

    btn.textContent = allChecked ? '✗ 전체해제' : '✓ 전체선택';
    btn.style.background = allChecked ? 'rgba(244, 67, 54, 0.8)' : 'rgba(76, 175, 80, 0.8)';
}

function toggleSelectAll() {
    const state = window.bulkSelectionState;
    const checkboxes = document.querySelectorAll('.item-checkbox');

    if (state.allSelected) {
        // Uncheck all
        checkboxes.forEach(cb => {
            cb.checked = false;
        });
        state.selectedItems = [];
        state.allSelected = false;

        // Hide bulk action panel
        const panel = document.getElementById('bulk-action-panel');
        if (panel) panel.style.display = 'none';
    } else {
        // Check all
        state.selectedItems = [];
        checkboxes.forEach(cb => {
            cb.checked = true;
            const fileId = cb.dataset.fileId;
            const contentType = cb.dataset.contentType;
            if (!state.selectedItems.find(item => item.fileId === fileId)) {
                state.selectedItems.push({ fileId, contentType });
            }
        });
        state.allSelected = true;

        // Show bulk action panel
        showBulkActionPanel();
    }

    updateBulkActionPanel();
    updateSelectAllButton();
}

function clearSelection() {
    const state = window.bulkSelectionState;
    state.selectedItems = [];
    state.allSelected = false;

    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(cb => cb.checked = false);

    // Hide bulk action panel
    const panel = document.getElementById('bulk-action-panel');
    if (panel) panel.style.display = 'none';

    updateBulkActionPanel();
    updateSelectAllButton();
}

async function createSeriesFromSelection() {
    const state = window.bulkSelectionState;

    if (state.selectedItems.length === 0) {
        alert('선택된 파일이 없습니다.');
        return;
    }

    // Validation: Check if all items have same content type
    const contentTypes = new Set(state.selectedItems.map(item => item.contentType));
    if (contentTypes.size > 1) {
        alert('⚠️ 만화책과 EPUB를 같은 시리즈에 넣을 수 없습니다.\n같은 타입의 파일만 선택해주세요.');
        return;
    }

    const contentType = state.selectedItems[0].contentType;

    // Prompt for series details
    const title = prompt('시리즈 제목을 입력하세요:');
    if (!title || title.trim() === '') {
        return;
    }

    const description = prompt('시리즈 설명 (선택사항):') || '';

    // Create series
    const series = await createSeries(title.trim(), description.trim() || null, contentType);
    if (!series) {
        return;
    }

    // Add all selected items to the series
    let successCount = 0;
    for (let i = 0; i < state.selectedItems.length; i++) {
        const item = state.selectedItems[i];
        const success = await addToSeries(series.id, item.fileId, item.contentType, i + 1);
        if (success) {
            successCount++;
        }
    }

    if (successCount === state.selectedItems.length) {
        alert(`✅ 시리즈 "${title}"가 생성되었습니다!\n${successCount}개 파일이 추가되었습니다.`);
        clearSelection(); // Clear selection
        location.reload();
    } else {
        alert(`⚠️ 일부 파일 추가에 실패했습니다.\n성공: ${successCount}/${state.selectedItems.length}`);
    }
}

// Bulk add to existing series
async function bulkAddToExistingSeries() {
    const state = window.bulkSelectionState;

    if (state.selectedItems.length === 0) {
        alert('선택된 파일이 없습니다.');
        return;
    }

    // Validation: Check if all items have same content type
    const contentTypes = new Set(state.selectedItems.map(item => item.contentType));
    if (contentTypes.size > 1) {
        alert('⚠️ 만화책과 EPUB를 같은 시리즈에 넣을 수 없습니다.\n같은 타입의 파일만 선택해주세요.');
        return;
    }

    const contentType = state.selectedItems[0].contentType;

    // Get user series
    const seriesList = await getUserSeries(contentType);
    if (seriesList.length === 0) {
        alert('아직 시리즈가 없습니다. 먼저 시리즈를 생성해주세요.');
        return;
    }

    // Show series selection modal
    showBulkSeriesSelectionModal(seriesList, contentType);
}
