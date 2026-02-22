/**
 * 키워드 추출 서비스 - 프론트엔드
 * SSE 연결, 작업 관리, 결과 표시, 선택 복사, 어드민 관리
 */

// ==================== State ====================
const state = {
    loggedIn: false,
    username: '',
    isAdmin: false,
    jobs: {},           // job_id -> job data
    activeJobId: null,  // 현재 결과 표시 중인 job
    eventSource: null,
    results: {},        // job_id -> results[]
    progress: {},       // job_id -> {found_count, message}
    selectedKeywords: new Set(), // 선택된 키워드 인덱스
};

// ==================== DOM Helpers ====================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', () => {
    // 로그인 폼
    $('#login-form').addEventListener('submit', handleLogin);

    // 작업 추가
    $('#add-job-btn').addEventListener('click', handleAddJob);
    $('#url-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleAddJob();
    });

    // 로그아웃
    $('#logout-btn').addEventListener('click', handleLogout);

    // CSV 다운로드
    $('#csv-download-btn').addEventListener('click', handleCsvDownload);

    // 복사 버튼들
    $('#copy-all-comma-btn').addEventListener('click', () => handleCopy('all', ','));
    $('#copy-all-line-btn').addEventListener('click', () => handleCopy('all', '\n'));
    $('#copy-sel-comma-btn').addEventListener('click', () => handleCopy('selected', ','));
    $('#copy-sel-line-btn').addEventListener('click', () => handleCopy('selected', '\n'));

    // 전체 선택 체크박스
    $('#select-all-cb').addEventListener('change', handleSelectAll);

    // 어드민: 사용자 생성
    $('#admin-create-btn').addEventListener('click', handleAdminCreateUser);

    // 페이지 로드 시 기존 세션 체크
    checkExistingSession();
});

// ==================== Auth ====================
async function handleLogin(e) {
    e.preventDefault();
    const username = $('#login-username').value.trim();
    const password = $('#login-password').value;

    if (!username || !password) return;

    try {
        const resp = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (resp.ok) {
            const data = await resp.json();
            state.loggedIn = true;
            state.username = data.username;
            state.isAdmin = !!data.is_admin;
            showMainScreen();
            connectSSE();
            refreshJobs();
            if (state.isAdmin) {
                loadAdminUsers();
            }
        } else {
            const err = await resp.json();
            showLoginError(err.detail || '로그인 실패');
        }
    } catch (e) {
        showLoginError('서버 연결 실패');
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (e) { /* ignore */ }

    if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
    }

    state.loggedIn = false;
    state.username = '';
    state.isAdmin = false;
    state.jobs = {};
    state.results = {};
    state.progress = {};
    state.activeJobId = null;
    state.selectedKeywords = new Set();
    showLoginScreen();
}

async function checkExistingSession() {
    try {
        const resp = await fetch('/api/jobs');
        if (resp.ok) {
            const data = await resp.json();
            state.loggedIn = true;
            // 기존 세션에서는 username을 jobs 응답에서 가져올 수 없으므로
            // user-info가 비어있을 수 있음 - SSE connected 이벤트에서 보완
            showMainScreen();
            connectSSE();
            for (const job of data.jobs) {
                state.jobs[job.job_id] = job;
            }
            renderJobs();
        }
    } catch (e) { /* not logged in */ }
}

// ==================== Screen Toggle ====================
function showLoginScreen() {
    $('#login-screen').style.display = 'flex';
    $('#main-screen').style.display = 'none';
    $('#login-username').value = '';
    $('#login-password').value = '';
}

function showMainScreen() {
    $('#login-screen').style.display = 'none';
    $('#main-screen').style.display = 'block';
    $('#user-info').textContent = state.username || '';
    // 어드민 섹션 표시/숨김
    $('#admin-section').style.display = state.isAdmin ? 'block' : 'none';
}

function showLoginError(msg) {
    const el = $('#login-error');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

// ==================== SSE ====================
function connectSSE() {
    if (state.eventSource) {
        state.eventSource.close();
    }

    const es = new EventSource('/api/events');
    state.eventSource = es;

    es.addEventListener('connected', () => {});

    es.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        if (data.job_id) {
            if (!state.progress[data.job_id]) {
                state.progress[data.job_id] = { found_count: 0, message: '' };
            }
            state.progress[data.job_id].message = typeof data.data === 'string' ? data.data : '';
            renderJobProgress(data.job_id);
        }
    });

    es.addEventListener('sub_progress', (e) => {
        const data = JSON.parse(e.data);
        const prog = data.data;
        const jobId = data.job_id;
        if (prog && jobId) {
            state.progress[jobId] = {
                found_count: prog.found_count || 0,
                message: prog.message || '',
            };
            renderJobProgress(jobId);
        }
    });

    es.addEventListener('error_event', () => {});
    es.addEventListener('preview', () => {});

    es.addEventListener('finished', (e) => {
        const data = JSON.parse(e.data);
        const jobId = data.job_id;
        state.results[jobId] = data.data;
        refreshJobs();
    });

    es.addEventListener('job_added', (e) => {
        const data = JSON.parse(e.data);
        state.jobs[data.job_id] = data.data;
        renderJobs();
    });

    es.addEventListener('job_started', (e) => {
        const data = JSON.parse(e.data);
        state.jobs[data.job_id] = data.data;
        state.progress[data.job_id] = { found_count: 0, message: '시작 중...' };
        renderJobs();
    });

    es.addEventListener('job_finished', (e) => {
        const data = JSON.parse(e.data);
        state.jobs[data.job_id] = data.data;
        delete state.progress[data.job_id];
        renderJobs();
    });

    es.addEventListener('job_cancelled', (e) => {
        const data = JSON.parse(e.data);
        state.jobs[data.job_id] = data.data;
        delete state.progress[data.job_id];
        renderJobs();
    });

    es.addEventListener('job_deleted', (e) => {
        const data = JSON.parse(e.data);
        const jobId = data.job_id;
        delete state.jobs[jobId];
        delete state.results[jobId];
        delete state.progress[jobId];
        if (state.activeJobId === jobId) {
            state.activeJobId = null;
            $('#result-section').style.display = 'none';
        }
        renderJobs();
    });

    es.addEventListener('heartbeat', () => {});

    es.onerror = () => {
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }
        setTimeout(async () => {
            if (!state.loggedIn) return;
            try {
                const resp = await fetch('/api/jobs');
                if (resp.status === 401) {
                    state.loggedIn = false;
                    state.jobs = {};
                    state.results = {};
                    showLoginScreen();
                    return;
                }
            } catch (e) { /* 네트워크 오류 -> 재시도 */ }
            connectSSE();
        }, 3000);
    };
}

// ==================== Jobs ====================
async function handleAddJob() {
    const rawText = $('#url-input').value.trim();
    const count = parseInt($('#count-input').value) || 100;
    const maxRank = parseInt($('#max-rank-input').value) || 50;
    const minRank = parseInt($('#min-rank-input').value) || 1;
    const nameRatio = (parseInt($('#name-ratio-input').value) || 30) / 100;

    if (!rawText) {
        showToast('URL을 입력하세요', 'error');
        return;
    }

    const urls = rawText.split(/[\n,]+/)
        .map(u => u.trim())
        .filter(u => u.length > 0);

    const validUrls = [];
    const invalidUrls = [];
    for (const url of urls) {
        if (url.includes('place.naver.com')) {
            validUrls.push(url);
        } else {
            invalidUrls.push(url);
        }
    }

    if (invalidUrls.length > 0) {
        showToast(`유효하지 않은 URL ${invalidUrls.length}개 제외됨`, 'error');
    }

    if (validUrls.length === 0) {
        showToast('유효한 네이버 플레이스 URL이 없습니다', 'error');
        return;
    }

    const btn = $('#add-job-btn');
    btn.disabled = true;
    btn.textContent = `등록 중... (${validUrls.length}개)`;

    try {
        if (validUrls.length === 1) {
            const resp = await fetch('/api/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: validUrls[0], target_count: count, max_rank: maxRank, min_rank: minRank, name_keyword_ratio: nameRatio }),
            });
            if (resp.ok) {
                showToast(`작업 추가됨: ${validUrls[0]}`, 'success');
            } else {
                const err = await resp.json();
                showToast(`작업 추가 실패: ${err.detail}`, 'error');
            }
        } else {
            const resp = await fetch('/api/jobs/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls: validUrls, target_count: count, max_rank: maxRank, min_rank: minRank, name_keyword_ratio: nameRatio }),
            });
            if (resp.ok) {
                const data = await resp.json();
                showToast(`${data.count}개 작업 일괄 등록 완료`, 'success');
            } else {
                const err = await resp.json();
                showToast(`대량 등록 실패: ${err.detail}`, 'error');
            }
        }
        $('#url-input').value = '';
    } catch (e) {
        showToast('서버 연결 실패', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '추가';
    }
}

async function handleCancelJob(jobId) {
    try {
        await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
        showToast('작업 취소 요청', 'info', jobId);
    } catch (e) {
        showToast('취소 실패', 'error');
    }
}

async function handleDeleteJob(jobId) {
    if (!confirm('이 작업을 삭제하시겠습니까?')) return;
    try {
        const resp = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
        if (resp.ok) {
            showToast('작업 삭제됨', 'info', jobId);
        } else {
            showToast('삭제 실패', 'error');
        }
    } catch (e) {
        showToast('삭제 실패', 'error');
    }
}

async function refreshJobs() {
    try {
        const resp = await fetch('/api/jobs');
        if (resp.ok) {
            const data = await resp.json();
            for (const job of data.jobs) {
                state.jobs[job.job_id] = job;
            }
            renderJobs();
        }
    } catch (e) { /* ignore */ }
}

// ==================== Render Jobs ====================
function renderJobs() {
    const tbody = $('#job-tbody');
    const emptyEl = $('#job-empty');
    tbody.innerHTML = '';

    const jobs = Object.values(state.jobs).sort((a, b) => b.created_at - a.created_at);

    if (jobs.length === 0) {
        emptyEl.style.display = 'block';
        return;
    }
    emptyEl.style.display = 'none';

    for (const job of jobs) {
        const tr = document.createElement('tr');

        const statusMap = {
            queued: { text: '대기', cls: 'badge-queued' },
            running: { text: '실행 중', cls: 'badge-running' },
            completed: { text: '완료', cls: 'badge-completed' },
            failed: { text: '오류', cls: 'badge-failed' },
            cancelled: { text: '취소됨', cls: 'badge-cancelled' },
        };
        const st = statusMap[job.status] || { text: job.status, cls: 'badge-queued' };

        const shortUrl = job.url.length > 40 ? job.url.substring(0, 40) + '...' : job.url;

        // 발견 개수 (확정된 키워드만)
        const prog = state.progress[job.job_id];
        let foundHtml = '-';
        if (job.status === 'running' && prog) {
            foundHtml = `<span class="progress-pill">${prog.found_count}</span>`;
        } else if (job.status === 'running') {
            foundHtml = '<span class="progress-pill">0</span>';
        } else if (job.status === 'completed' || job.status === 'cancelled') {
            foundHtml = `${job.result_count || 0}`;
        }

        // 최근 진행 메시지
        let msgHtml = '';
        if (job.status === 'running' && prog && prog.message) {
            msgHtml = truncateMsg(prog.message);
        } else if (job.status === 'completed') {
            msgHtml = '완료';
        } else if (job.status === 'failed') {
            msgHtml = job.error_message || '오류';
        } else if (job.status === 'cancelled') {
            msgHtml = '취소됨';
        } else if (job.status === 'queued') {
            msgHtml = '대기 중';
        }

        // 액션 버튼
        let actionHtml = '<div class="action-btns">';
        if (job.status === 'queued' || job.status === 'running') {
            actionHtml += `<button class="btn-sm btn-danger-sm" onclick="handleCancelJob('${job.job_id}')">취소</button>`;
        }
        if (job.status === 'completed' || (job.status === 'cancelled' && job.result_count > 0)) {
            actionHtml += `<button class="btn-sm btn-success-sm" onclick="showResults('${job.job_id}')">결과</button>`;
        }
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
            actionHtml += `<button class="btn-sm btn-danger-sm" onclick="handleDeleteJob('${job.job_id}')">삭제</button>`;
        }
        actionHtml += '</div>';

        tr.innerHTML = `
            <td>${escapeHtml(job.place_name || '-')}</td>
            <td class="url-cell" title="${escapeHtml(job.url)}">${escapeHtml(shortUrl)}</td>
            <td>${job.target_count}</td>
            <td><span class="badge ${st.cls}">${st.text}</span></td>
            <td id="found-${job.job_id}">${foundHtml}</td>
            <td id="msg-${job.job_id}" class="msg-cell" title="${escapeHtml(msgHtml)}">${escapeHtml(msgHtml)}</td>
            <td>${actionHtml}</td>
        `;
        tbody.appendChild(tr);
    }
}

function truncateMsg(msg) {
    if (typeof msg !== 'string') return '';
    return msg.length > 40 ? msg.substring(0, 40) + '...' : msg;
}

function renderJobProgress(jobId) {
    const prog = state.progress[jobId];
    if (!prog) return;

    const foundCell = document.getElementById(`found-${jobId}`);
    if (foundCell) {
        foundCell.innerHTML = `<span class="progress-pill">${prog.found_count}</span>`;
    }

    const msgCell = document.getElementById(`msg-${jobId}`);
    if (msgCell && prog.message) {
        const msg = truncateMsg(prog.message);
        msgCell.textContent = msg;
        msgCell.title = prog.message;
    }
}

// ==================== Results ====================
async function showResults(jobId) {
    state.activeJobId = jobId;
    state.selectedKeywords = new Set();

    if (!state.results[jobId]) {
        try {
            const resp = await fetch(`/api/jobs/${jobId}/results`);
            if (resp.ok) {
                const data = await resp.json();
                state.results[jobId] = data.results;
            }
        } catch (e) { /* ignore */ }
    }

    const results = state.results[jobId] || [];
    renderResults(results, jobId);
}

function renderResults(results, jobId) {
    const section = $('#result-section');
    section.style.display = 'block';

    const valid = results.filter(r => r.rank !== null && r.rank !== undefined);
    const pllCount = valid.filter(r => r.keyword_type === 'PLL').length;
    const pltCount = valid.filter(r => r.keyword_type === 'PLT').length;

    const job = state.jobs[jobId];
    const statusInfo = job && job.status === 'cancelled' ? ' (취소됨 - 부분 결과)' : '';

    $('#result-summary').textContent =
        `총 ${valid.length}개 (PLL: ${pllCount}, PLT: ${pltCount})${statusInfo}`;

    // 결과 탭 렌더링
    const tabs = $('#result-tabs');
    tabs.innerHTML = '';
    const showableJobs = Object.values(state.jobs).filter(
        j => j.status === 'completed' || (j.status === 'cancelled' && j.result_count > 0)
    );
    for (const j of showableJobs) {
        const tab = document.createElement('button');
        tab.className = 'tab-btn' + (j.job_id === jobId ? ' active' : '');
        tab.textContent = j.place_name || j.job_id.substring(0, 8);
        tab.onclick = () => showResults(j.job_id);
        tabs.appendChild(tab);
    }

    // 전체 선택 체크박스 초기화
    $('#select-all-cb').checked = false;

    // 테이블 렌더링
    const tbody = $('#result-tbody');
    tbody.innerHTML = '';

    const sorted = valid.sort((a, b) => (a.rank || 999) - (b.rank || 999));

    sorted.forEach((r, i) => {
        const tr = document.createElement('tr');
        const typeClass = r.keyword_type === 'PLL' ? 'type-pll' : 'type-plt';
        const checked = state.selectedKeywords.has(i) ? 'checked' : '';

        tr.innerHTML = `
            <td><input type="checkbox" data-idx="${i}" ${checked} onchange="handleRowCheck(this)"></td>
            <td>${i + 1}</td>
            <td>${escapeHtml(r.keyword)}</td>
            <td>${r.rank || '-'}</td>
            <td class="${typeClass}">${r.keyword_type || '-'}</td>
            <td>${escapeHtml(r.status)}</td>
        `;

        if (state.selectedKeywords.has(i)) {
            tr.classList.add('selected');
        }

        tbody.appendChild(tr);
    });

    section.scrollIntoView({ behavior: 'smooth' });
}

// ==================== Checkbox Selection ====================
function handleSelectAll(e) {
    const checked = e.target.checked;
    state.selectedKeywords.clear();

    const checkboxes = $$('#result-tbody input[type="checkbox"]');
    checkboxes.forEach((cb) => {
        cb.checked = checked;
        const idx = parseInt(cb.dataset.idx);
        if (checked) {
            state.selectedKeywords.add(idx);
        }
        const tr = cb.closest('tr');
        if (tr) {
            tr.classList.toggle('selected', checked);
        }
    });
}

function handleRowCheck(cb) {
    const idx = parseInt(cb.dataset.idx);
    if (cb.checked) {
        state.selectedKeywords.add(idx);
    } else {
        state.selectedKeywords.delete(idx);
    }

    const tr = cb.closest('tr');
    if (tr) {
        tr.classList.toggle('selected', cb.checked);
    }

    // 전체 선택 체크박스 상태 동기화
    const total = $$('#result-tbody input[type="checkbox"]').length;
    $('#select-all-cb').checked = state.selectedKeywords.size === total && total > 0;
}

// ==================== Copy / Clipboard ====================
function handleCopy(scope, separator) {
    if (!state.activeJobId) return;

    const results = state.results[state.activeJobId] || [];
    const valid = results.filter(r => r.rank !== null && r.rank !== undefined);
    const sorted = valid.sort((a, b) => (a.rank || 999) - (b.rank || 999));

    let keywords;
    if (scope === 'selected') {
        if (state.selectedKeywords.size === 0) {
            showToast('선택된 키워드가 없습니다', 'error');
            return;
        }
        keywords = sorted.filter((_, i) => state.selectedKeywords.has(i)).map(r => r.keyword);
    } else {
        keywords = sorted.map(r => r.keyword);
    }

    const sepLabel = separator === ',' ? '쉼표' : '줄바꿈';
    const scopeLabel = scope === 'selected' ? '선택' : '전체';
    const text = keywords.join(separator);
    copyToClipboard(text, `${scopeLabel} ${keywords.length}개, ${sepLabel}`);
}

function copyToClipboard(text, label) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(`클립보드에 복사됨 (${label})`, 'success');
            showToast(`클립보드에 복사됨 (${label})`, 'success');
        }).catch(() => {
            fallbackCopy(text, label);
        });
    } else {
        fallbackCopy(text, label);
    }
}

function fallbackCopy(text, label) {
    const ta = $('#clipboard-fallback');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '0';
    ta.style.top = '0';
    ta.style.opacity = '0.01';
    ta.focus();
    ta.select();
    try {
        const ok = document.execCommand('copy');
        if (ok) {
            showToast(`클립보드에 복사됨 (${label})`, 'success');
            showToast(`클립보드에 복사됨 (${label})`, 'success');
        } else {
            showToast('클립보드 복사 실패 - 수동으로 복사하세요', 'error');
            showToast('클립보드 복사 실패', 'error');
        }
    } catch (e) {
        showToast('클립보드 복사 실패', 'error');
        showToast('클립보드 복사 실패', 'error');
    }
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '-9999px';
    ta.style.opacity = '1';
}

// ==================== CSV ====================
async function handleCsvDownload() {
    if (!state.activeJobId) return;
    window.location.href = `/api/jobs/${state.activeJobId}/results/csv`;
}

// ==================== Admin ====================
async function loadAdminUsers() {
    if (!state.isAdmin) return;
    try {
        const resp = await fetch('/api/admin/users');
        if (resp.ok) {
            const data = await resp.json();
            renderAdminUsers(data.users);
        }
    } catch (e) { /* ignore */ }
}

function renderAdminUsers(users) {
    const tbody = $('#admin-user-tbody');
    tbody.innerHTML = '';

    for (const user of users) {
        const tr = document.createElement('tr');
        const roleBadge = user.is_admin
            ? '<span class="badge-admin">관리자</span>'
            : '<span class="badge-user">일반</span>';

        const deleteBtn = user.is_admin
            ? '<button class="btn-sm" disabled title="관리자는 삭제할 수 없습니다">삭제</button>'
            : `<button class="btn-sm btn-danger-sm" onclick="handleAdminDeleteUser('${escapeHtml(user.username)}')">삭제</button>`;

        tr.innerHTML = `
            <td>${escapeHtml(user.username)}</td>
            <td>${roleBadge}</td>
            <td>${deleteBtn}</td>
        `;
        tbody.appendChild(tr);
    }
}

async function handleAdminCreateUser() {
    const username = $('#admin-new-username').value.trim();
    const password = $('#admin-new-password').value;

    if (!username || !password) {
        showToast('사용자명과 비밀번호를 입력하세요', 'error');
        return;
    }

    try {
        const resp = await fetch('/api/admin/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (resp.ok) {
            showToast(`사용자 "${username}" 생성 완료`, 'success');
            $('#admin-new-username').value = '';
            $('#admin-new-password').value = '';
            loadAdminUsers();
        } else {
            const err = await resp.json();
            showToast(`사용자 생성 실패: ${err.detail || '알 수 없는 오류'}`, 'error');
        }
    } catch (e) {
        showToast('서버 연결 실패', 'error');
    }
}

async function handleAdminDeleteUser(username) {
    if (!confirm(`"${username}" 사용자를 삭제하시겠습니까?`)) return;

    try {
        const resp = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, {
            method: 'DELETE',
        });

        if (resp.ok) {
            showToast(`사용자 "${username}" 삭제 완료`, 'success');
            loadAdminUsers();
        } else {
            const err = await resp.json();
            showToast(`삭제 실패: ${err.detail || '알 수 없는 오류'}`, 'error');
        }
    } catch (e) {
        showToast('서버 연결 실패', 'error');
    }
}

// ==================== Toast ====================
function showToast(message, type = 'info') {
    const container = $('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

// ==================== Util ====================
function escapeHtml(str) {
    if (typeof str !== 'string') str = String(str);
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
