// =========================================
// State
// =========================================
const State = {
  config: null,
  personas: [],
  sessions: [],
  currentSessionId: null,
  currentSession: null,
  autoRun: false,
  turnIndex: 0,
  uploadedFiles: [],
  selectedPersonas: [],  // for new session modal
};

const AXES = ["데이터", "콘텐츠", "AI Commerce", "UX"];
const AXIS_EMOJI = { "데이터": "📊", "콘텐츠": "✍️", "AI Commerce": "🛍️", "UX": "🎨" };

// =========================================
// Init
// =========================================
window.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  await loadPersonas();
  await loadSessions();
  await seedDefaultsIfEmpty();
  renderSidebar();
  renderWelcome();
});

async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    State.config = await r.json();
  } catch (e) {
    toast('설정 로드 실패', 'error');
  }
}

async function loadPersonas() {
  try {
    const r = await fetch('/api/personas');
    const d = await r.json();
    State.personas = d.personas || [];
  } catch (e) { console.error(e); }
}

async function loadSessions() {
  try {
    const r = await fetch('/api/sessions');
    const d = await r.json();
    State.sessions = d.sessions || [];
  } catch (e) { console.error(e); }
}

async function seedDefaultsIfEmpty() {
  if (State.personas.length === 0) {
    try {
      const r = await fetch('/api/personas/seed_defaults', { method: 'POST' });
      const d = await r.json();
      if (d.personas) State.personas = d.personas;
    } catch (e) { console.error(e); }
  }
}

// =========================================
// Sidebar Render
// =========================================
function renderSidebar() {
  renderSessionList();
  renderPersonaListSide();
}

function renderSessionList() {
  const el = document.getElementById('session_list');
  if (!State.sessions.length) {
    el.innerHTML = '<div class="empty-mini">아직 토론이 없습니다</div>';
    return;
  }
  el.innerHTML = State.sessions.map(s => `
    <div class="session-item ${s.id === State.currentSessionId ? 'active' : ''}" onclick="loadSession('${s.id}')">
      <div class="session-title">${escapeHTML(s.title || s.query)}</div>
      <span class="session-del" onclick="event.stopPropagation(); deleteSession('${s.id}')">✕</span>
    </div>
  `).join('');
}

function renderPersonaListSide() {
  const el = document.getElementById('persona_list_side');
  if (!State.personas.length) {
    el.innerHTML = '<div class="empty-mini">페르소나를 추가하세요</div>';
    return;
  }
  el.innerHTML = State.personas.map(p => `
    <div class="persona-side-item" onclick='openPersonaModal(${JSON.stringify(p.id)})'>
      <div class="avatar" style="background:${p.color}22; color:${p.color}">${escapeHTML(p.emoji || '💬')}</div>
      <div class="info">
        <div class="nick">${escapeHTML(p.name)}</div>
        <div class="axis">${(p.focus_dimensions || []).join(' · ') || '전체'}</div>
      </div>
    </div>
  `).join('');
}

// =========================================
// Welcome Screen
// =========================================
function renderWelcome() {
  document.getElementById('main_inner').innerHTML = `
    <div class="welcome">
      <h1>AI 토론으로 콘텐츠를 진단하세요</h1>
      <p>여러 페르소나가 동시에 같은 콘텐츠를 보고 데이터·콘텐츠·AI Commerce·UX 4가지 축으로 분석합니다. ChatGPT, Perplexity, Google Shopping이 이 페이지를 인용·추천할지가 핵심 질문입니다.</p>
      <div class="welcome-cards">
        <div class="welcome-card" onclick="openNewSessionModal()">
          <div class="ico" style="background:var(--tint-soft); color:var(--tint)">▶</div>
          <h3>새 토론 시작</h3>
          <p>URL이나 파일을 분석하고 페르소나들의 의견을 들어보세요</p>
        </div>
        <div class="welcome-card" onclick="openPersonaModal()">
          <div class="ico" style="background:rgba(191,90,242,0.10); color:var(--purple)">👤</div>
          <h3>페르소나 만들기</h3>
          <p>나만의 분석 관점을 가진 새 페르소나를 추가하세요</p>
        </div>
        <div class="welcome-card" onclick="showPersonaLibrary()">
          <div class="ico" style="background:rgba(48,209,88,0.12); color:var(--green)">📚</div>
          <h3>페르소나 둘러보기</h3>
          <p>기본 제공되는 8명의 분석가를 살펴보세요</p>
        </div>
      </div>
    </div>
  `;
  document.getElementById('rp_content').innerHTML = `
    <div class="rp-empty">토론을 시작하면<br>여기에 분석과 라이브 요약이 표시됩니다.</div>
  `;
}

function showPersonaLibrary() {
  const html = `
    <div class="main-inner">
      <div class="session-header">
        <div class="topic">페르소나 라이브러리</div>
        <div style="color:var(--text-secondary); font-size:14px; margin-top:6px">기본 제공 + 사용자 추가 페르소나. 클릭하면 편집할 수 있습니다.</div>
      </div>
      ${State.personas.map(p => `
        <div class="turn-card" style="border-left-color:${p.color}; cursor:pointer" onclick='openPersonaModal(${JSON.stringify(p.id)})'>
          <div class="turn-head">
            <div class="turn-avatar" style="background:${p.color}22">${escapeHTML(p.emoji || '💬')}</div>
            <div>
              <div class="turn-name">${escapeHTML(p.name)}</div>
              <div style="font-size:12px;color:var(--text-tertiary)">${(p.focus_dimensions||[]).join(' · ') || '전체 축 가능'}</div>
            </div>
          </div>
          <div class="persona-card-detail">
            <div class="detail-row"><span class="detail-label">설명</span><span class="detail-value">${escapeHTML(p.description || '-')}</span></div>
            <div class="detail-row"><span class="detail-label">성격</span><span class="detail-value">${escapeHTML(p.personality || '-')}</span></div>
            <div class="detail-row"><span class="detail-label">전문</span><span class="detail-value">${escapeHTML(p.expertise || '-')}</span></div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
  document.getElementById('main_inner').outerHTML = html;
}

// =========================================
// Session Loading & Rendering
// =========================================
async function loadSession(sid) {
  State.currentSessionId = sid;
  State.autoRun = false;
  try {
    const r = await fetch(`/api/sessions/${sid}`);
    const data = await r.json();
    State.currentSession = data;
    renderSidebar();
    renderSession();
  } catch (e) {
    toast('세션 로드 실패', 'error');
  }
}

function renderSession() {
  const s = State.currentSession;
  if (!s) return;
  const analysis = s.analysis || {};
  const score = analysis.aeo_score || 0;
  const scoreClass = score < 40 ? 'score-low' : (score < 70 ? 'score-mid' : 'score-high');

  const personas = s.personas || [];
  const maxRounds = s.max_rounds || 3;
  const currentRound = personas.length > 0
    ? Math.floor((s.turns || []).length / personas.length) + 1
    : 1;

  const turnsHtml = (s.turns || []).map(renderTurnCard).join('');

  document.getElementById('main_inner').innerHTML = `
    <div class="session-header">
      <div class="topic">${escapeHTML(s.query)}</div>
      ${s.url ? `<div class="url">🔗 <a href="${escapeHTML(s.url)}" target="_blank" rel="noopener">${escapeHTML(s.url)}</a></div>` : ''}
      ${analysis.summary ? `<div style="color:var(--text-secondary); font-size:14px; margin-top:8px">${escapeHTML(analysis.summary)}</div>` : ''}
      <div class="persona-chips">
        ${personas.map(p => `
          <div class="persona-chip">
            <div class="dot" style="background:${p.color}22; color:${p.color}">${escapeHTML(p.emoji || '💬')}</div>
            ${escapeHTML(p.name)}
          </div>
        `).join('')}
      </div>
      <div class="session-meta-row">
        <div class="aeo-pill ${scoreClass}">AEO <span class="score">${score}</span><span>/100</span></div>
        <div class="aeo-pill" style="background:rgba(88,86,214,0.10); color:var(--indigo)">
          라운드 <span class="score" id="round_num">${Math.min(currentRound, maxRounds)}</span><span>/${maxRounds === 999 ? '∞' : maxRounds}</span>
        </div>
        <div class="session-controls">
          <button class="ctrl-btn primary" id="btn_play" onclick="toggleAutoRun()">▶ 자동 진행</button>
          <button class="ctrl-btn" onclick="manualNextTurn()">+1 발언</button>
          <button class="ctrl-btn" onclick="refreshDigest()">요약 갱신</button>
          <button class="ctrl-btn" onclick="exportSession()">⬇ MD</button>
          <button class="ctrl-btn danger" onclick="deleteSession('${s.id}', true)">삭제</button>
        </div>
      </div>
    </div>

    <div class="discussion-feed" id="discussion_feed">
      ${turnsHtml || '<div class="thinking-card" style="color:var(--text-secondary)">▶ 자동 진행 또는 +1 발언을 눌러 토론을 시작하세요.</div>'}
    </div>
  `;
  renderRightPanel();
}

function renderTurnCard(t) {
  const dims = (t.dimensions || []).map(d => `
    <div class="dim-card">
      <div class="dim-axis axis-${cssAxis(d.axis)}">${AXIS_EMOJI[d.axis] || '·'} ${escapeHTML(d.axis)}</div>
      ${(d.evidence && d.evidence.length) ? `
        <div class="dim-block">
          <div class="dim-label">근거</div>
          <div class="evidence-list">
            ${d.evidence.map(ev => `
              <div class="evidence-item">
                <div class="evidence-source">${escapeHTML(ev.source || '')}</div>
                <div class="evidence-quote">${escapeHTML(ev.quote || '')}</div>
              </div>
            `).join('')}
          </div>
        </div>` : ''}
      ${d.argument ? `
        <div class="dim-block">
          <div class="dim-label">주장</div>
          <div class="dim-arg">${escapeHTML(d.argument)}</div>
        </div>` : ''}
      ${d.action ? `
        <div class="dim-block">
          <div class="dim-label">제안 액션</div>
          <div class="dim-action">${escapeHTML(d.action)}</div>
        </div>` : ''}
    </div>
  `).join('');

  return `
    <div class="turn-card" style="border-left-color:${t.color || 'var(--tint)'}">
      <div class="turn-head">
        <div class="turn-avatar" style="background:${(t.color||'#007AFF')}22">${escapeHTML(t.emoji || '💬')}</div>
        <div class="turn-name">${escapeHTML(t.persona)}</div>
        <span class="turn-stance stance-${t.stance || '신규관점'}">${escapeHTML(t.stance || '신규관점')}</span>
        ${t.target ? `<span class="turn-target">→ ${escapeHTML(t.target)}</span>` : ''}
        <span class="turn-round-tag">R${t.round || 1}</span>
      </div>
      ${t.synthesis ? `<div class="turn-synthesis">"${escapeHTML(t.synthesis)}"</div>` : ''}
      <div class="dim-cards">${dims}</div>
    </div>
  `;
}

function cssAxis(ax) { return ax.replace(/ /g, '-'); }

// =========================================
// Right Panel — Digest + Score
// =========================================
function renderRightPanel() {
  const s = State.currentSession;
  if (!s) return;
  const analysis = s.analysis || {};
  const digest = (s.digest && s.digest.digest) || null;
  const byDim = analysis.by_dimension || {};

  const scoreHtml = `
    <div class="rp-section">
      <div class="rp-title">축별 진단 점수</div>
      <div class="rp-score-grid">
        ${AXES.map(ax => {
          const d = byDim[ax] || {};
          const sc = d.score || 0;
          const color = sc < 40 ? 'var(--red)' : (sc < 70 ? 'var(--orange)' : 'var(--green)');
          return `<div class="rp-score-cell">
            <div class="rp-score-axis">${AXIS_EMOJI[ax]} ${escapeHTML(ax)}</div>
            <div class="rp-score-num" style="color:${color}">${sc}</div>
          </div>`;
        }).join('')}
      </div>
    </div>
  `;

  const digestHtml = digest ? `
    <div class="rp-section">
      <div class="rp-title">라이브 다이제스트</div>
      ${digest.headline ? `<div class="rp-headline">"${escapeHTML(digest.headline)}"</div>` : ''}
    </div>
    ${AXES.map(ax => {
      const d = (digest.by_dimension || {})[ax] || {};
      const hasContent = (d.consensus||[]).length || (d.conflicts||[]).length || (d.actions||[]).length;
      if (!hasContent) return '';
      return `
        <div class="rp-dim">
          <div class="rp-dim-axis">${AXIS_EMOJI[ax]} ${escapeHTML(ax)}</div>
          ${(d.consensus||[]).length ? `
            <div class="rp-dim-subhead">합의</div>
            <ul class="rp-dim-list">${d.consensus.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>` : ''}
          ${(d.conflicts||[]).length ? `
            <div class="rp-dim-subhead">충돌</div>
            <ul class="rp-dim-list">${d.conflicts.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>` : ''}
          ${(d.actions||[]).length ? `
            <div class="rp-dim-subhead">액션</div>
            <ul class="rp-dim-list">${d.actions.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>` : ''}
        </div>
      `;
    }).join('')}
    ${(digest.top_insights||[]).length ? `
      <div class="rp-section">
        <div class="rp-title">통합 인사이트</div>
        <ul class="rp-dim-list">${digest.top_insights.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>
      </div>` : ''}
    ${(digest.next_questions||[]).length ? `
      <div class="rp-section">
        <div class="rp-title">다음 라운드 질문</div>
        <ul class="rp-dim-list">${digest.next_questions.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>
      </div>` : ''}
  ` : `<div class="rp-empty">발언이 쌓이면 "요약 갱신" 버튼으로<br>다이제스트를 만들 수 있어요.</div>`;

  document.getElementById('rp_content').innerHTML = scoreHtml + digestHtml;
}

// =========================================
// Turn execution
// =========================================
async function manualNextTurn() {
  await nextTurnStep();
}

async function toggleAutoRun() {
  State.autoRun = !State.autoRun;
  const btn = document.getElementById('btn_play');
  if (State.autoRun) {
    btn.textContent = '⏸ 일시정지';
    runLoop();
  } else {
    btn.textContent = '▶ 자동 진행';
  }
}

async function runLoop() {
  while (State.autoRun) {
    const s = State.currentSession;
    if (!s) break;
    const personas = s.personas || [];
    const maxRounds = s.max_rounds || 3;
    const completedRounds = personas.length > 0
      ? Math.floor((s.turns || []).length / personas.length)
      : 0;

    // 최대 라운드 도달 — 자동 진행만 멈추고 +1 발언으로는 계속 가능
    if (maxRounds !== 999 && completedRounds >= maxRounds) {
      State.autoRun = false;
      const btn = document.getElementById('btn_play');
      if (btn) btn.textContent = '▶ 자동 진행';
      await refreshDigest(true);
      toast(`${maxRounds}라운드 완료 · 최종 요약 갱신됨`);
      break;
    }

    try {
      const r = await nextTurnStep();
      if (!r) break;
      // 라운드 인디케이터 업데이트
      const rn = document.getElementById('round_num');
      if (rn) rn.textContent = Math.min(completedRounds + 1, maxRounds);
      await sleep(1500);
    } catch (e) {
      console.error(e);
      toast('진행 중 오류: ' + e.message, 'error');
      State.autoRun = false;
      const btn = document.getElementById('btn_play');
      if (btn) btn.textContent = '▶ 자동 진행';
      break;
    }
  }
}

async function nextTurnStep() {
  const s = State.currentSession;
  if (!s) return false;
  const personas = s.personas || [];
  if (!personas.length) {
    toast('이 세션에 페르소나가 없습니다', 'error');
    return false;
  }

  // 현재까지 turn 수 → 다음 발언자 결정 (라운드 로빈)
  const turns = s.turns || [];
  const nextSpeaker = personas[turns.length % personas.length];

  // 진행 중 인디케이터
  appendThinking(nextSpeaker);

  let res;
  try {
    const r = await fetch(`/api/sessions/${s.id}/turn`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ persona_name: nextSpeaker.name }),
    });
    res = await r.json();
    if (!r.ok) throw new Error(res.detail || 'turn 실패');
  } catch (e) {
    removeThinking();
    toast('발언 생성 실패: ' + e.message, 'error');
    return false;
  }
  removeThinking();

  // 로컬 상태 업데이트
  s.turns = [...(s.turns || []), res.turn];
  appendTurnCard(res.turn);

  // 라운드 끝마다 다이제스트 갱신
  if (s.turns.length % personas.length === 0) {
    await refreshDigest(true);
  }
  return true;
}

function appendTurnCard(t) {
  const feed = document.getElementById('discussion_feed');
  if (!feed) return;
  // 첫 메시지면 안내 카드 제거
  const onlyThinking = feed.children.length === 1 && feed.children[0].classList.contains('thinking-card');
  if (onlyThinking) feed.innerHTML = '';
  feed.insertAdjacentHTML('beforeend', renderTurnCard(t));
  feed.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function appendThinking(persona) {
  const feed = document.getElementById('discussion_feed');
  if (!feed) return;
  const id = 'thinking_now';
  removeThinking();
  feed.insertAdjacentHTML('beforeend', `
    <div class="thinking-card" id="${id}">
      <div class="turn-avatar" style="background:${persona.color}22; width:32px; height:32px; font-size:15px">${escapeHTML(persona.emoji || '💬')}</div>
      <div style="font-size:14px; color:var(--text-secondary)"><strong>${escapeHTML(persona.name)}</strong>가 분석 중</div>
      <div class="thinking-dots" style="margin-left:auto"><span></span><span></span><span></span></div>
    </div>
  `);
  feed.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
}
function removeThinking() {
  const e = document.getElementById('thinking_now');
  if (e) e.remove();
}

async function refreshDigest(silent=false) {
  const s = State.currentSession;
  if (!s) return;
  try {
    const r = await fetch(`/api/sessions/${s.id}/digest`, { method: 'POST' });
    const d = await r.json();
    s.digest = { digest: d.digest };  // mimic GET shape
    renderRightPanel();
    if (!silent) toast('다이제스트 갱신');
  } catch (e) {
    if (!silent) toast('다이제스트 실패', 'error');
  }
}

async function exportSession() {
  const s = State.currentSession;
  if (!s) return;
  window.open(`/api/sessions/${s.id}/export`, '_blank');
}

async function deleteSession(sid, confirmFirst=false) {
  if (confirmFirst && !confirm('이 토론을 삭제할까요?')) return;
  await fetch(`/api/sessions/${sid}`, { method: 'DELETE' });
  await loadSessions();
  if (State.currentSessionId === sid) {
    State.currentSessionId = null;
    State.currentSession = null;
    renderWelcome();
  }
  renderSidebar();
}

// =========================================
// New Session Modal
// =========================================
function openNewSessionModal() {
  State.uploadedFiles = [];
  State.maxRounds = 3;
  // 기본은 4명만 (각 축 1명씩) 선택
  const byAxis = {};
  for (const p of State.personas) {
    const ax = (p.focus_dimensions || [])[0] || '기타';
    if (!byAxis[ax]) byAxis[ax] = p;
  }
  State.selectedPersonas = Object.values(byAxis).slice(0, 4).map(p => p.name);
  renderNewSessionModal();
}

function renderNewSessionModal() {
  const html = `
    <div class="modal-overlay" onclick="if(event.target===this) closeModal()">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">새 토론 시작</div>
          <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>토론 주제 *</label>
            <input class="input" id="ns_query" placeholder="예: 우리 신제품 페이지가 ChatGPT 추천에 잘 들어갈까?">
          </div>
          <div class="field">
            <label>분석할 URL</label>
            <input class="input" id="ns_url" placeholder="https://example.com/product/...">
            <div class="hint">URL이 없으면 첨부파일만 분석할 수도 있습니다.</div>
          </div>
          <div class="field">
            <label>첨부파일 (PDF · 이미지)</label>
            <div class="upload-zone" onclick="document.getElementById('ns_file').click()">
              <div style="font-size:22px; margin-bottom:4px">📎</div>
              클릭해서 파일을 선택하세요
              <div class="hint" style="margin-top:4px">PDF / PNG / JPG / WEBP · 여러 개 가능</div>
            </div>
            <input type="file" id="ns_file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif" style="display:none" onchange="handleUpload(event)">
            <div class="uploaded-list" id="uploaded_list">
              ${State.uploadedFiles.map(f => `
                <div class="uploaded-item">
                  ${f.kind === 'pdf' ? '📄' : '🖼️'} ${escapeHTML(f.filename)}
                  <span class="x" onclick="removeUpload('${f.id}')">✕</span>
                </div>
              `).join('')}
            </div>
          </div>
          <div class="field">
            <label>최대 라운드 (자동 진행 시)</label>
            <div class="dim-toggle-row">
              ${[1,2,3,5,999].map(n => `
                <div class="dim-toggle ${State.maxRounds===n?'active':''}" onclick="pickRounds(${n})">
                  ${n===999 ? '무제한' : n+'라운드'}
                </div>
              `).join('')}
            </div>
            <div class="hint">한 라운드 = 모든 페르소나가 한 번씩 발언. 페르소나 4명 × 3라운드 = 12개 발언.</div>
          </div>
          <div class="field">
            <label>참여 페르소나 (${State.selectedPersonas.length}명)</label>
            <div class="persona-pick-grid">
              ${State.personas.map(p => `
                <div class="persona-pick ${State.selectedPersonas.includes(p.name) ? 'selected' : ''}" onclick="togglePersonaPick('${escapeHTML(p.name)}')">
                  <div class="pavt" style="background:${p.color}22">${escapeHTML(p.emoji || '💬')}</div>
                  <div class="pinfo">
                    <div class="pnick">${escapeHTML(p.name)}</div>
                    <div class="ptag">${(p.focus_dimensions||[]).join(' · ') || '전체'}</div>
                  </div>
                </div>
              `).join('')}
            </div>
            <div class="hint">3~5명 권장. 더 많으면 다이제스트가 풍부해지지만 한 라운드가 오래 걸립니다.</div>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn-secondary" onclick="closeModal()">취소</button>
          <button class="btn-primary" id="btn_start_session" onclick="startSession()">분석 시작</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById('modal_root').innerHTML = html;
}

function togglePersonaPick(name) {
  const i = State.selectedPersonas.indexOf(name);
  if (i >= 0) State.selectedPersonas.splice(i, 1);
  else State.selectedPersonas.push(name);
  renderNewSessionModal();
}

function pickRounds(n) {
  State.maxRounds = n;
  renderNewSessionModal();
}

async function handleUpload(ev) {
  const files = Array.from(ev.target.files || []);
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    try {
      toast(`업로드 중: ${f.name}`);
      const r = await fetch('/api/upload', { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || '업로드 실패');
      State.uploadedFiles.push(d);
    } catch (e) {
      toast(`업로드 실패: ${f.name}`, 'error');
    }
  }
  renderNewSessionModal();
}

function removeUpload(id) {
  State.uploadedFiles = State.uploadedFiles.filter(f => f.id !== id);
  renderNewSessionModal();
}

async function startSession() {
  const query = document.getElementById('ns_query').value.trim();
  const url = document.getElementById('ns_url').value.trim();
  if (!query) { toast('토론 주제를 입력하세요', 'error'); return; }
  if (!url && !State.uploadedFiles.length) { toast('URL 또는 파일 중 하나는 필요해요', 'error'); return; }
  if (!State.selectedPersonas.length) { toast('페르소나를 1명 이상 선택하세요', 'error'); return; }

  const chosenPersonas = State.personas.filter(p => State.selectedPersonas.includes(p.name));
  const btn = document.getElementById('btn_start_session');
  btn.disabled = true;
  btn.textContent = '분석 중...';

  try {
    const r = await fetch('/api/sessions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        query, url,
        personas: chosenPersonas,
        attachment_ids: State.uploadedFiles.map(f => f.id),
        max_rounds: State.maxRounds || 3,
      })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '세션 생성 실패');
    closeModal();
    await loadSessions();
    await loadSession(d.session_id);
    toast('분석 완료 · 자동 진행을 누르세요');
  } catch (e) {
    toast('실패: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = '분석 시작';
  }
}

// =========================================
// Persona Modal (Create / Edit / Delete)
// =========================================
const COLORS = ['#0A84FF', '#5856D6', '#BF5AF2', '#FF375F', '#FF3B30', '#FF9500', '#FFCC00', '#30D158', '#5AC8FA', '#00C7BE'];
const EMOJIS = ['💬','📊','✍️','🛍️','🎨','🩺','💫','🤨','🔎','🧠','🚀','💎','⚡','🎯','🔥','🌟'];

function openPersonaModal(pid) {
  const editing = pid ? State.personas.find(p => p.id === pid) : null;
  renderPersonaModal(editing);
}

function renderPersonaModal(editing) {
  const p = editing || { name:'', description:'', personality:'', expertise:'',
                        focus_dimensions:[], color:COLORS[0], emoji:EMOJIS[0] };
  const isEdit = !!editing;

  document.getElementById('modal_root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this) closeModal()">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">${isEdit ? '페르소나 편집' : '새 페르소나'}</div>
          <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>닉네임 *</label>
            <input class="input" id="pf_name" value="${escapeAttr(p.name)}" placeholder="예: 감성젠지, DataNerd, UXResearcher">
            <div class="hint">실명보다 캐릭터가 드러나는 닉네임을 추천합니다.</div>
          </div>
          <div class="field">
            <label>설명</label>
            <textarea class="textarea" id="pf_desc" placeholder="이 페르소나가 어떤 사람/관점인지">${escapeAttr(p.description)}</textarea>
          </div>
          <div class="field">
            <label>성격 · 말투</label>
            <textarea class="textarea" id="pf_pers" placeholder="어떤 톤과 태도로 말하는지">${escapeAttr(p.personality)}</textarea>
          </div>
          <div class="field">
            <label>전문 분야</label>
            <textarea class="textarea" id="pf_exp" placeholder="이 페르소나가 깊이 아는 영역">${escapeAttr(p.expertise)}</textarea>
          </div>
          <div class="field">
            <label>주력 분석 축 (여러 개 선택 가능)</label>
            <div class="dim-toggle-row" id="pf_dims">
              ${AXES.map(ax => `
                <div class="dim-toggle ${p.focus_dimensions.includes(ax) ? 'active' : ''}" data-axis="${escapeAttr(ax)}" onclick="toggleDim(this)">
                  ${AXIS_EMOJI[ax]} ${escapeHTML(ax)}
                </div>
              `).join('')}
            </div>
            <div class="hint">선택하지 않으면 모든 축에서 발언 가능합니다.</div>
          </div>
          <div class="field">
            <label>아바타 이모지</label>
            <div class="emoji-pick-row" id="pf_emojis">
              ${EMOJIS.map(e => `<div class="emoji-pick ${e===p.emoji?'active':''}" data-emoji="${e}" onclick="pickEmoji(this)">${e}</div>`).join('')}
            </div>
          </div>
          <div class="field">
            <label>컬러</label>
            <div class="color-row" id="pf_colors">
              ${COLORS.map(c => `<div class="color-pick ${c===p.color?'active':''}" data-color="${c}" style="background:${c}" onclick="pickColor(this)"></div>`).join('')}
            </div>
          </div>
        </div>
        <div class="modal-foot">
          ${isEdit ? `<button class="btn-danger" onclick="deletePersona('${p.id}')">삭제</button>` : ''}
          <button class="btn-secondary" onclick="closeModal()">취소</button>
          <button class="btn-primary" onclick="${isEdit ? `savePersona('${p.id}')` : 'savePersona()'}">${isEdit ? '저장' : '추가'}</button>
        </div>
      </div>
    </div>
  `;
}

function toggleDim(el) { el.classList.toggle('active'); }
function pickColor(el) {
  document.querySelectorAll('#pf_colors .color-pick').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}
function pickEmoji(el) {
  document.querySelectorAll('#pf_emojis .emoji-pick').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

async function savePersona(pid) {
  const name = document.getElementById('pf_name').value.trim();
  if (!name) { toast('닉네임은 필수예요', 'error'); return; }
  const data = {
    name,
    description: document.getElementById('pf_desc').value.trim(),
    personality: document.getElementById('pf_pers').value.trim(),
    expertise: document.getElementById('pf_exp').value.trim(),
    focus_dimensions: Array.from(document.querySelectorAll('#pf_dims .dim-toggle.active')).map(e => e.dataset.axis),
    color: document.querySelector('#pf_colors .color-pick.active')?.dataset.color || COLORS[0],
    emoji: document.querySelector('#pf_emojis .emoji-pick.active')?.dataset.emoji || EMOJIS[0],
  };
  try {
    if (pid) {
      await fetch(`/api/personas/${pid}`, { method: 'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data) });
      toast('수정 완료');
    } else {
      await fetch('/api/personas', { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data) });
      toast('추가 완료');
    }
    await loadPersonas();
    renderSidebar();
    closeModal();
  } catch (e) {
    toast('저장 실패', 'error');
  }
}

async function deletePersona(pid) {
  if (!confirm('이 페르소나를 삭제할까요?')) return;
  try {
    await fetch(`/api/personas/${pid}`, { method: 'DELETE' });
    await loadPersonas();
    renderSidebar();
    closeModal();
    toast('삭제됨');
  } catch (e) { toast('삭제 실패', 'error'); }
}

// =========================================
// Helpers
// =========================================
function closeModal() { document.getElementById('modal_root').innerHTML = ''; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function escapeHTML(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeAttr(s) { return escapeHTML(s); }
function toast(msg, kind) {
  const el = document.createElement('div');
  el.className = 'toast' + (kind==='error' ? ' error' : '');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2400);
}
