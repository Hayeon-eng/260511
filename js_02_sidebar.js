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

