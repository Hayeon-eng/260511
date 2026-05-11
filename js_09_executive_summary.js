// =========================================
// Executive Summary
// =========================================
async function openExecutiveSummary() {
  const s = State.currentSession;
  if (!s) return;
  if (!s.turns || s.turns.length < 2) {
    toast('토론 발언이 더 쌓여야 합니다 (최소 2개)', 'error');
    return;
  }

  document.getElementById('modal_root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this) closeModal()">
      <div class="modal modal-wide">
        <div class="modal-head">
          <div class="modal-title">📊 임원진 보고용 요약</div>
          <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        <div class="modal-body" id="exec_body">
          <div class="exec-loading">
            <div class="thinking-dots"><span></span><span></span><span></span></div>
            <div style="margin-top:10px; color:var(--text-secondary)">토론 결과를 한 페이지 결론으로 정리 중...</div>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn-secondary" onclick="closeModal()">닫기</button>
        </div>
      </div>
    </div>
  `;

  try {
    const r = await fetch(`/api/sessions/${s.id}/executive_summary`, { method: 'POST' });
    const d = await r.json();
    if (!r.ok) {
      const detail = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail || {});
      throw new Error(detail || '생성 실패');
    }
    renderExecutiveSummary(d.summary || {});
  } catch (e) {
    document.getElementById('exec_body').innerHTML = `
      <div style="text-align:center; padding:24px; color:var(--red)">
        생성 실패: ${escapeHTML(e.message)}
      </div>
    `;
  }
}

function renderExecutiveSummary(summary) {
  const verdict = summary.verdict || '결론 없음';
  const keyGaps = summary.key_gaps || [];
  const actions = summary.actions || [];
  const expected = summary.expected_impact || '';
  const risks = summary.risks || [];

  // Quick Win은 ⭐, 일반은 임팩트별 색상
  const quickWins = actions.filter(a => a.quick_win);
  const otherActions = actions.filter(a => !a.quick_win);
  const quickWinSummaryHtml = quickWins.length ? `
    <div class="exec-quick-summary">
      <div class="exec-quick-summary-title">⭐ 지금 바로 할 일</div>
      <ul class="exec-quick-summary-list">
        ${quickWins.slice(0, 3).map(a => `
          <li>
            <strong>${escapeHTML(a.title || '')}</strong>
            <span>${escapeHTML(a.timeline || '-')} · ${escapeHTML(a.owner || '-')}</span>
          </li>
        `).join('')}
      </ul>
    </div>
  ` : '';

  const renderAction = (a, idx) => {
    const impactStars = '★'.repeat(a.impact) + '☆'.repeat(5 - a.impact);
    const effortDots = '●'.repeat(a.effort) + '○'.repeat(5 - a.effort);
    const axClass = cssAxis(a.axis || '');
    return `
      <div class="exec-action ${a.quick_win ? 'quick-win' : ''}">
        ${a.quick_win ? '<div class="exec-action-badge">⭐ Quick Win</div>' : ''}
        <div class="exec-action-num">${idx + 1}</div>
        <div class="exec-action-body">
          <div class="exec-action-title">${escapeHTML(a.title || '')}</div>
          <div class="exec-action-meta">
            <span class="exec-axis-tag axis-${axClass}">${AXIS_EMOJI[a.axis] || '·'} ${escapeHTML(a.axis || '')}</span>
            <span class="exec-meta-item">⏱ ${escapeHTML(a.timeline || '-')}</span>
            <span class="exec-meta-item">👤 ${escapeHTML(a.owner || '-')}</span>
          </div>
          <div class="exec-action-metrics">
            <div class="exec-metric">
              <span class="exec-metric-label">Impact</span>
              <span class="exec-metric-stars" title="${a.impact}/5">${impactStars}</span>
            </div>
            <div class="exec-metric">
              <span class="exec-metric-label">Effort</span>
              <span class="exec-metric-dots" title="${a.effort}/5">${effortDots}</span>
            </div>
          </div>
          ${a.expected_outcome ? `<div class="exec-action-outcome">📈 ${escapeHTML(a.expected_outcome)}</div>` : ''}
        </div>
      </div>
    `;
  };

  document.getElementById('exec_body').innerHTML = `
    <!-- 결론 -->
    <div class="exec-verdict">
      <div class="exec-verdict-label">🎯 결론</div>
      <div class="exec-verdict-text">"${escapeHTML(verdict)}"</div>
    </div>

    ${renderAnalysisReliability(State.currentSession, 'exec')}

    ${renderBrandFitSummary(State.currentSession, 'exec')}

    ${quickWinSummaryHtml}

    <!-- 핵심 격차 -->
    ${keyGaps.length ? `
      <div class="exec-section">
        <div class="exec-section-title">📊 핵심 격차 / 이슈</div>
        <div class="exec-gaps">
          ${keyGaps.map((g, i) => `
            <div class="exec-gap">
              <div class="exec-gap-num">${i+1}</div>
              <div class="exec-gap-body">
                <div class="exec-gap-title">${escapeHTML(g.title || '')}</div>
                <div class="exec-gap-meta">
                  ${g.axis ? `<span class="exec-axis-tag axis-${cssAxis(g.axis)}">${AXIS_EMOJI[g.axis] || '·'} ${escapeHTML(g.axis)}</span>` : ''}
                  ${g.evidence ? `<span class="exec-gap-evidence">${escapeHTML(g.evidence)}</span>` : ''}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Quick Wins (강조) -->
    ${quickWins.length ? `
      <div class="exec-section">
        <div class="exec-section-title quick-win-title">
          ⭐ Quick Wins — 지금 당장 실행
          <span class="exec-section-subtitle">높은 임팩트 × 낮은 노력</span>
        </div>
        <div class="exec-actions">
          ${quickWins.map((a, i) => renderAction(a, i)).join('')}
        </div>
      </div>
    ` : ''}

    <!-- 나머지 액션 -->
    ${otherActions.length ? `
      <div class="exec-section">
        <div class="exec-section-title">🎯 추가 액션 아이템</div>
        <div class="exec-actions">
          ${otherActions.map((a, i) => renderAction(a, quickWins.length + i)).join('')}
        </div>
      </div>
    ` : ''}

    <!-- 예상 임팩트 -->
    ${expected ? `
      <div class="exec-section">
        <div class="exec-section-title">💰 예상 임팩트</div>
        <div class="exec-impact">${escapeHTML(expected)}</div>
      </div>
    ` : ''}

    <!-- 리스크 / 가정 -->
    ${risks.length ? `
      <div class="exec-section">
        <div class="exec-section-title">⚠️ 리스크 / 가정</div>
        <ul class="exec-risks">
          ${risks.map(r => `<li>${escapeHTML(r)}</li>`).join('')}
        </ul>
      </div>
    ` : ''}
  `;
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

