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
  const isCompare = s.mode === 'compare';
  const score = analysis.aeo_score || 0;
  const scoreClass = score < 40 ? 'score-low' : (score < 70 ? 'score-mid' : 'score-high');

  const personas = s.personas || [];
  const maxRounds = s.max_rounds || 3;
  const currentRound = personas.length > 0
    ? Math.floor((s.turns || []).length / personas.length) + 1
    : 1;

  // 라운드 구분선이 적절한 곳에 들어가게 — 각 라운드 첫 발언에 표시
  const turnsList = s.turns || [];
  const turnsHtml = turnsList.map((t, i) => {
    const prevRound = i > 0 ? turnsList[i-1].round : 0;
    const showRoundDivider = (t.round || 1) !== prevRound;
    return renderTurnCard(t, { showRoundDivider });
  }).join('');

  // A/B 비교 모드 헤더
  let scoresHTML;
  if (isCompare) {
    const a = s.side_a || {};
    const b = s.side_b || {};
    const aLabel = a.label || s.label_a || 'A';
    const bLabel = b.label || s.label_b || 'B';
    const aAn = a.analysis || {};
    const bAn = b.analysis || {};
    const aScore = aAn.aeo_score || 0;
    const bScore = bAn.aeo_score || 0;
    const aCls = aScore < 40 ? 'score-low' : (aScore < 70 ? 'score-mid' : 'score-high');
    const bCls = bScore < 40 ? 'score-low' : (bScore < 70 ? 'score-mid' : 'score-high');
    scoresHTML = `
      <div class="vs-row">
        <div class="vs-card">
          <div class="vs-label">${escapeHTML(aLabel)}</div>
          ${a.url ? `<div class="vs-url">${escapeHTML(a.url)}</div>` : ''}
          <div class="aeo-pill ${aCls}">AEO <span class="score">${aScore}</span><span>/100</span></div>
          <div class="vs-mini-summary">${escapeHTML(aAn.summary || '')}</div>
        </div>
        <div class="vs-mid">VS</div>
        <div class="vs-card">
          <div class="vs-label">${escapeHTML(bLabel)}</div>
          ${b.url ? `<div class="vs-url">${escapeHTML(b.url)}</div>` : ''}
          <div class="aeo-pill ${bCls}">AEO <span class="score">${bScore}</span><span>/100</span></div>
          <div class="vs-mini-summary">${escapeHTML(bAn.summary || '')}</div>
        </div>
      </div>
    `;
  } else {
    scoresHTML = `
      <div class="aeo-pill ${scoreClass}">AEO <span class="score">${score}</span><span>/100</span></div>
    `;
  }

  document.getElementById('main_inner').innerHTML = `
    <div class="session-header">
      <div class="topic">${escapeHTML(s.query)}</div>
      ${s.url && !isCompare ? `<div class="url">🔗 <a href="${escapeHTML(s.url)}" target="_blank" rel="noopener">${escapeHTML(s.url)}</a></div>` : ''}
      <div class="persona-chips">
        ${personas.map(p => `
          <div class="persona-chip">
            <div class="dot" style="background:${p.color}22; color:${p.color}">${escapeHTML(p.emoji || '💬')}</div>
            ${escapeHTML(p.name)}
          </div>
        `).join('')}
      </div>
      <div class="session-meta-row">
        <div class="aeo-pill" style="background:rgba(88,86,214,0.10); color:var(--indigo)">
          라운드 <span class="score" id="round_num">${Math.min(currentRound, maxRounds)}</span><span>/${maxRounds === 999 ? '∞' : maxRounds}</span>
        </div>
        <div class="session-controls">
          <button class="ctrl-btn primary" id="btn_play" onclick="toggleAutoRun()">▶ 자동 진행</button>
          <button class="ctrl-btn" onclick="manualNextTurn()">+1 발언</button>
          <button class="ctrl-btn" onclick="refreshDigest()">요약 갱신</button>
          <div class="ctrl-menu">
            <button class="ctrl-btn" onclick="toggleExportMenu(event)">⬇ 내보내기 ▾</button>
            <div class="ctrl-menu-dropdown" id="export_menu">
              <div class="dd-item" onclick="exportSession('md')">📝 마크다운 (.md)</div>
              <div class="dd-item" onclick="exportSession('xlsx')">📊 엑셀 (.xlsx)</div>
              <div class="dd-item" onclick="exportSession('pptx')">🎯 파워포인트 (.pptx)</div>
            </div>
          </div>
          <button class="ctrl-btn danger" onclick="deleteSession('${s.id}', true)">삭제</button>
        </div>
      </div>
    </div>

    <!-- ============ ZONE 1: 크롤링·입력 데이터 기반 사전 진단 ============ -->
    ${renderDiagnosisZone(s)}

    <!-- ============ ZONE 2: 실시간 토론 ============ -->
    <div class="zone zone-discussion">
      <div class="zone-banner zone-banner-discussion">
        <div class="zone-banner-icon">💬</div>
        <div class="zone-banner-text">
          <div class="zone-banner-title">실시간 토론</div>
          <div class="zone-banner-subtitle">${personas.length}명의 페르소나가 5개 축 관점으로 깊이 있는 의견을 만들어갑니다</div>
        </div>
        <div class="zone-banner-stats">
          <strong id="turns_count">${(s.turns||[]).length}</strong> 발언
        </div>
      </div>
      <div class="discussion-feed" id="discussion_feed">
        ${turnsHtml || '<div class="thinking-card" style="color:var(--text-secondary)"><div class="thinking-dots"><span></span><span></span><span></span></div><div>▶ 자동 진행 또는 +1 발언을 눌러 토론을 시작하세요.</div></div>'}
      </div>

      <!-- 꼬리질문 입력창 -->
      <div class="ask-bar">
        <div class="ask-bar-row">
          <input class="ask-input" id="ask_input" placeholder="페르소나들에게 추가 질문하기..." onkeydown="if(event.key==='Enter') sendFollowup()">
          <select class="ask-target" id="ask_target">
            <option value="">전체 페르소나</option>
            ${personas.map(p => `<option value="${escapeAttr(p.name)}">${escapeHTML(p.emoji||'💬')} ${escapeHTML(p.name)}만</option>`).join('')}
          </select>
          <button class="ask-send" onclick="sendFollowup()">↗ 보내기</button>
        </div>
        <div class="ask-presets">
          <span class="ask-preset-label">자주 쓰는 질문:</span>
          <button class="ask-preset" onclick="setAskInput('이 액션들을 우선순위 5개로 정리해줘')">우선순위 5개</button>
          <button class="ask-preset" onclick="setAskInput('1개월 안에 실행 가능한 것만 추려줘')">1개월 가능</button>
          <button class="ask-preset" onclick="setAskInput('구현 난이도와 예상 효과를 점수로 매겨줘')">난이도/효과 점수</button>
          <button class="ask-preset" onclick="setAskInput('경쟁사 사례를 더 구체적으로 들어줘')">경쟁사 사례</button>
        </div>
      </div>

      <!-- 임원진 보고 만들기 -->
      <div class="exec-cta">
        <button class="exec-cta-btn" onclick="openExecutiveSummary()">
          <span class="exec-cta-icon">📊</span>
          <span class="exec-cta-text">
            <strong>임원진 보고용 한 페이지 요약 만들기</strong>
            <small>토론 결과를 결론·핵심 격차·우선순위 액션으로 정리합니다</small>
          </span>
          <span class="exec-cta-arrow">→</span>
        </button>
      </div>
    </div>
  `;
  renderRightPanel();
}

