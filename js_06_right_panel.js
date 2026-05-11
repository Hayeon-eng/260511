// =========================================
// Right Panel — Digest + Score
// =========================================

function renderRightPanelSummary(session, digest) {
  const isCompare = session.mode === 'compare';
  const analysis = session.analysis || {};

  if (digest && (digest.headline || (digest.top_insights || []).length)) {
    return `
      <div class="rp-summary-card">
        <div class="rp-summary-kicker">요약</div>
        ${digest.headline ? `<div class="rp-summary-headline">${escapeHTML(digest.headline)}</div>` : ''}
        ${(digest.top_insights || []).length ? `
          <ul class="rp-summary-list">
            ${digest.top_insights.slice(0, 3).map(x => `<li>${escapeHTML(x)}</li>`).join('')}
          </ul>
        ` : ''}
      </div>
    `;
  }

  if (isCompare) {
    const a = session.side_a || {};
    const b = session.side_b || {};
    const aLabel = a.label || session.label_a || 'A';
    const bLabel = b.label || session.label_b || 'B';
    const aAn = a.analysis || {};
    const bAn = b.analysis || {};
    const aSummary = aAn.summary || aAn.aeo_reason || '';
    const bSummary = bAn.summary || bAn.aeo_reason || '';
    const hasSummary = Boolean(aSummary || bSummary);

    return `
      <div class="rp-summary-card">
        <div class="rp-summary-kicker">요약</div>
        ${hasSummary ? `
          <div class="rp-summary-compare">
            <div class="rp-summary-side">
              <strong>${escapeHTML(aLabel)}</strong>
              <span>${escapeHTML(aSummary || '요약 없음')}</span>
            </div>
            <div class="rp-summary-side">
              <strong>${escapeHTML(bLabel)}</strong>
              <span>${escapeHTML(bSummary || '요약 없음')}</span>
            </div>
          </div>
        ` : `
          <div class="rp-summary-empty">
            아직 AI 1차 진단 요약이 비어 있습니다.<br>
            양쪽 AEO 점수가 0으로 보이면 분석 응답이 비었거나 JSON 파싱/토큰/키/크롤링 문제일 수 있습니다.
          </div>
        `}
      </div>
    `;
  }

  const summary = analysis.summary || analysis.aeo_reason || '';
  return `
    <div class="rp-summary-card">
      <div class="rp-summary-kicker">요약</div>
      ${summary ? `
        <div class="rp-summary-headline">${escapeHTML(summary)}</div>
        ${analysis.consumer_perception ? `<div class="rp-summary-desc">${escapeHTML(analysis.consumer_perception)}</div>` : ''}
      ` : `
        <div class="rp-summary-empty">
          아직 AI 1차 진단 요약이 비어 있습니다.<br>
          AEO 점수가 0으로 보이면 분석 응답이 비었거나 JSON 파싱/토큰/키/크롤링 문제일 수 있습니다.
        </div>
      `}
    </div>
  `;
}

function renderRightPanel() {
  const s = State.currentSession;
  if (!s) return;
  const isCompare = s.mode === 'compare';
  const analysis = s.analysis || {};
  const digest = (s.digest && s.digest.digest) || null;

  // ============ Sharp Insights — 우측 패널 헤로 영역 ============
  // 우선순위: 토론 다이제스트의 top_insights → 단일 분석의 key_insights
  let sharpInsights = [];
  let sharpHeadline = '';
  if (digest && digest.top_insights && digest.top_insights.length) {
    sharpInsights = digest.top_insights.slice(0, 4);
    sharpHeadline = digest.headline || '';
  } else if (!isCompare && analysis.key_insights && analysis.key_insights.length) {
    sharpInsights = analysis.key_insights.slice(0, 4);
  } else if (isCompare) {
    // 비교 모드: 양쪽 인사이트에서 차이 강조
    const a = (s.side_a || {}).analysis || {};
    const b = (s.side_b || {}).analysis || {};
    sharpInsights = [
      ...((a.key_insights || []).slice(0, 2).map(x => `[${(s.side_a||{}).label || s.label_a || 'A'}] ${x}`)),
      ...((b.key_insights || []).slice(0, 2).map(x => `[${(s.side_b||{}).label || s.label_b || 'B'}] ${x}`)),
    ].slice(0, 4);
  }

  // 핵심 액션들 (토론에서 추출)
  let sharpActions = [];
  if (digest && digest.by_dimension) {
    for (const ax of AXES) {
      const d = digest.by_dimension[ax] || {};
      (d.actions || []).slice(0, 1).forEach(a => sharpActions.push({ax, action: a}));
    }
  }
  // 다이제스트가 없으면 1차 진단의 actions 활용
  if (!sharpActions.length && analysis.by_dimension) {
    for (const ax of AXES) {
      const d = analysis.by_dimension[ax] || {};
      (d.actions || []).slice(0, 1).forEach(a => sharpActions.push({ax, action: a}));
    }
  }

  const sharpHtml = (sharpInsights.length || sharpActions.length) ? `
    <div class="rp-sharp">
      <div class="rp-sharp-title">
        <span class="rp-sharp-bolt">⚡</span>
        <span>Sharp Insights</span>
        <span class="rp-sharp-tag">${digest ? '토론 기반' : '1차 진단 기반'}</span>
      </div>
      ${sharpHeadline ? `<div class="rp-sharp-headline">"${escapeHTML(sharpHeadline)}"</div>` : ''}
      ${sharpInsights.length ? `
        <div class="rp-sharp-section">
          <div class="rp-sharp-label">💡 핵심 인사이트</div>
          <ul class="rp-sharp-list">
            ${sharpInsights.map(x => `<li>${escapeHTML(x)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
      ${sharpActions.length ? `
        <div class="rp-sharp-section">
          <div class="rp-sharp-label">🎯 즉시 실행할 액션</div>
          <ul class="rp-sharp-action-list">
            ${sharpActions.slice(0, 5).map(a => `
              <li>
                <span class="rp-sharp-axis-tag axis-${cssAxis(a.ax)}">${AXIS_EMOJI[a.ax]} ${escapeHTML(a.ax)}</span>
                <span class="rp-sharp-action-text">${escapeHTML(a.action)}</span>
              </li>
            `).join('')}
          </ul>
        </div>
      ` : ''}
    </div>
  ` : '';

  // ============ 점수 ============
  let scoreHtml;
  if (isCompare) {
    const a = s.side_a || {};
    const b = s.side_b || {};
    const aAn = a.analysis || {};
    const bAn = b.analysis || {};
    const aLabel = a.label || s.label_a || 'A';
    const bLabel = b.label || s.label_b || 'B';
    scoreHtml = `
      <div class="rp-section">
        <div class="rp-title">축별 비교 점수</div>
        <div class="rp-compare-grid">
          <div class="rp-compare-head">${escapeHTML(aLabel)}</div>
          <div class="rp-compare-head" style="text-align:center; color:var(--text-tertiary)">vs</div>
          <div class="rp-compare-head">${escapeHTML(bLabel)}</div>
          ${AXES.map(ax => {
            const a_d = (aAn.by_dimension || {})[ax] || {};
            const b_d = (bAn.by_dimension || {})[ax] || {};
            const aS = a_d.score || 0, bS = b_d.score || 0;
            const aClr = scoreColorVar(aS);
            const bClr = scoreColorVar(bS);
            return `
              <div class="rp-compare-cell"><span class="rp-compare-num" style="color:${aClr}">${aS}</span></div>
              <div class="rp-compare-cell" style="font-size:12px; color:var(--text-secondary)">${AXIS_EMOJI[ax]} ${escapeHTML(ax)}</div>
              <div class="rp-compare-cell"><span class="rp-compare-num" style="color:${bClr}">${bS}</span></div>
            `;
          }).join('')}
        </div>
      </div>
    `;
  } else {
    const byDim = analysis.by_dimension || {};
    scoreHtml = `
      <div class="rp-section">
        <div class="rp-title">축별 진단 점수</div>
        <div class="rp-score-grid">
          ${AXES.map(ax => {
            const d = byDim[ax] || {};
            const sc = d.score || 0;
            return `<div class="rp-score-cell">
              <div class="rp-score-axis">${AXIS_EMOJI[ax]} ${escapeHTML(ax)}</div>
              <div class="rp-score-num" style="color:${scoreColorVar(sc)}">${sc}</div>
            </div>`;
          }).join('')}
        </div>
      </div>
    `;
  }

  // ============ 다이제스트 상세 ============
  const digestHtml = digest ? `
    ${AXES.map(ax => {
      const d = (digest.by_dimension || {})[ax] || {};
      const hasContent = (d.consensus||[]).length || (d.conflicts||[]).length || (d.actions||[]).length;
      if (!hasContent) return '';
      return `
        <div class="rp-dim">
          <div class="rp-dim-axis axis-${cssAxis(ax)}">${AXIS_EMOJI[ax]} ${escapeHTML(ax)}</div>
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
    ${(digest.next_questions||[]).length ? `
      <div class="rp-section">
        <div class="rp-title">다음 라운드 질문</div>
        <ul class="rp-dim-list">${digest.next_questions.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>
      </div>` : ''}
  ` : `<div class="rp-empty">토론이 시작되면 여기에<br>축별 합의·충돌·액션이 정리됩니다.</div>`;

  const summaryHtml = renderRightPanelSummary(s, digest);
  const reliabilityHtml = renderAnalysisReliability(s, 'compact');

  document.getElementById('rp_content').innerHTML = summaryHtml + sharpHtml + reliabilityHtml + scoreHtml +
    (digest ? `<div class="rp-section"><div class="rp-title">축별 디테일</div></div>` : '') +
    digestHtml;
}

