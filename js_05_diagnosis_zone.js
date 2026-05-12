// =========================================
// 크롤링·입력 데이터 기반 사전 진단 영역
// =========================================
function renderDiagnosisZone(s) {
  const isCompare = s.mode === 'compare';

  if (isCompare) {
    const a = s.side_a || {};
    const b = s.side_b || {};
    const aAn = a.analysis || {};
    const bAn = b.analysis || {};
    const aLabel = a.label || s.label_a || 'A';
    const bLabel = b.label || s.label_b || 'B';
    const aScore = aAn.aeo_score || 0;
    const bScore = bAn.aeo_score || 0;
    const diff = bScore - aScore;
    const winner = diff > 0 ? 'B' : (diff < 0 ? 'A' : 'tie');

    return `
      <div class="zone zone-diagnosis">
        <div class="zone-banner zone-banner-diagnosis">
          <div class="zone-banner-icon">📋</div>
          <div class="zone-banner-text">
            <div class="zone-banner-title">크롤링·입력 데이터 기반 사전 진단 <span class="zone-tag">자동 분석</span></div>
            <div class="zone-banner-subtitle">입력한 두 콘텐츠에서 수집한 원문·메타데이터·첨부 내용을 먼저 자동 분석한 결과입니다. 페르소나들은 이 근거를 참고해 심화 토론합니다.</div>
          </div>
        </div>

        <div class="diag-compare-hero">
          <div class="diag-side ${winner==='A'?'winner':''}">
            <div class="diag-side-label">${escapeHTML(aLabel)}</div>
            ${a.url ? `<div class="diag-side-url">${escapeHTML(a.url)}</div>` : ''}
            <div class="diag-score-big" style="color:${scoreColorVar(aScore)}">${aScore}</div>
            <div class="diag-score-cap">AEO 점수 / 100</div>
            ${aAn.summary ? `<div class="diag-side-summary">${escapeHTML(aAn.summary)}</div>` : ''}
          </div>
          <div class="diag-vs">
            <div class="diag-vs-label">VS</div>
            ${diff !== 0 ? `
              <div class="diag-diff">
                <span class="diag-diff-arrow">${diff > 0 ? '→' : '←'}</span>
                <span class="diag-diff-num">${Math.abs(diff)}점</span>
                <span class="diag-diff-label">차이</span>
              </div>
            ` : '<div class="diag-diff" style="color:var(--text-tertiary)">동점</div>'}
          </div>
          <div class="diag-side ${winner==='B'?'winner':''}">
            <div class="diag-side-label">${escapeHTML(bLabel)}</div>
            ${b.url ? `<div class="diag-side-url">${escapeHTML(b.url)}</div>` : ''}
            <div class="diag-score-big" style="color:${scoreColorVar(bScore)}">${bScore}</div>
            <div class="diag-score-cap">AEO 점수 / 100</div>
            ${bAn.summary ? `<div class="diag-side-summary">${escapeHTML(bAn.summary)}</div>` : ''}
          </div>
        </div>

        <!-- 5개 축 비교 막대 -->
        <div class="diag-axis-bars">
          ${AXES.map(ax => {
            const a_d = getDimensionData(aAn, ax);
            const b_d = getDimensionData(bAn, ax);
            const aS = a_d.score || 0, bS = b_d.score || 0;
            const axClass = cssAxis(ax);
            return `
              <div class="axis-bar-row">
                <div class="axis-bar-label">${AXIS_EMOJI[ax]} ${escapeHTML(ax)}</div>
                <div class="axis-bar-track">
                  <div class="axis-bar-side axis-bar-left">
                    <div class="axis-bar-num" style="color:${scoreColorVar(aS)}">${aS}</div>
                    <div class="axis-bar-fill axis-bar-fill-left axis-fill-${axClass}" style="width:${aS}%"></div>
                  </div>
                  <div class="axis-bar-divider"></div>
                  <div class="axis-bar-side axis-bar-right">
                    <div class="axis-bar-fill axis-bar-fill-right axis-fill-${axClass}" style="width:${bS}%"></div>
                    <div class="axis-bar-num" style="color:${scoreColorVar(bS)}">${bS}</div>
                  </div>
                </div>
              </div>
            `;
          }).join('')}
        </div>

        <div class="diag-brand-criteria-note">${brandFitCriteriaHtml('')}</div>

        ${renderDiagInsights(aAn, bAn, aLabel, bLabel)}
      </div>
    `;
  }

  // 단일 모드
  const analysis = s.analysis || {};
  const score = analysis.aeo_score || 0;
  const byDim = analysis.by_dimension || {};

  return `
    <div class="zone zone-diagnosis">
      <div class="zone-banner zone-banner-diagnosis">
        <div class="zone-banner-icon">📋</div>
        <div class="zone-banner-text">
          <div class="zone-banner-title">크롤링·입력 데이터 기반 사전 진단 <span class="zone-tag">자동 분석</span></div>
          <div class="zone-banner-subtitle">입력한 URL·이미지·카피에서 수집한 원문·메타데이터·첨부 내용을 먼저 자동 분석한 결과입니다. 페르소나들은 이 근거를 참고해 심화 토론합니다.</div>
        </div>
      </div>

      <div class="diag-single-hero">
        <div class="diag-score-block">
          <div class="diag-score-big" style="color:${scoreColorVar(score)}">${score}</div>
          <div class="diag-score-cap">AEO 점수 / 100</div>
          ${analysis.aeo_reason ? `<div class="diag-reason">${escapeHTML(analysis.aeo_reason)}</div>` : ''}
        </div>
        <div class="diag-summary-block">
          ${analysis.summary ? `<div class="diag-summary-title">콘텐츠 요약</div><div class="diag-summary-text">${escapeHTML(analysis.summary)}</div>` : ''}
          ${analysis.consumer_perception ? `<div class="diag-summary-title" style="margin-top:14px">소비자 인식</div><div class="diag-summary-text">${escapeHTML(analysis.consumer_perception)}</div>` : ''}
        </div>
      </div>

      <div class="diag-axis-grid">
        ${AXES.map(ax => {
          const d = getDimensionData(analysis, ax);
          const sc = d.score || 0;
          const axClass = cssAxis(ax);
          return `
            <div class="diag-axis-cell axis-bg-${axClass}">
              <div class="diag-axis-head">
                <span class="diag-axis-icon">${AXIS_EMOJI[ax]}</span>
                <span class="diag-axis-name">${escapeHTML(ax)}</span>
              </div>
              <div class="diag-axis-score" style="color:${scoreColorVar(sc)}">${sc}</div>
              <div class="diag-axis-bar"><div class="diag-axis-bar-fill axis-fill-${axClass}" style="width:${sc}%"></div></div>
              ${(d.findings||[]).length ? `<div class="diag-axis-list"><strong>발견</strong>${d.findings.slice(0,2).map(x=>`<div>· ${escapeHTML(x)}</div>`).join('')}</div>` : ''}
              ${(d.gaps||[]).length ? `<div class="diag-axis-list"><strong>결손</strong>${d.gaps.slice(0,2).map(x=>`<div>· ${escapeHTML(x)}</div>`).join('')}</div>` : ''}
              ${ax === BRAND_AXIS ? brandFitCriteriaHtml((analysis.brand_fit || {}).target_brand) : ''}
            </div>
          `;
        }).join('')}
      </div>

      ${renderDiagInsights(analysis, null)}
    </div>
  `;
}

function renderDiagInsights(an, an2, labelA, labelB) {
  // 핵심 인사이트 / 예상 질의 영역
  const insights = (an && an.key_insights) || [];
  const questions = (an && an.likely_questions) || [];
  if (!insights.length && !questions.length) return '';
  return `
    <div class="diag-insights">
      ${insights.length ? `
        <div class="diag-insight-block">
          <div class="diag-insight-title">💡 핵심 인사이트</div>
          <ul class="diag-insight-list">
            ${insights.slice(0,4).map(x => `<li>${escapeHTML(x)}</li>`).join('')}
          </ul>
        </div>` : ''}
      ${questions.length ? `
        <div class="diag-insight-block">
          <div class="diag-insight-title">🔍 AI에게 사용자가 물을 만한 질문</div>
          <ul class="diag-insight-list">
            ${questions.slice(0,4).map(x => `<li>"${escapeHTML(x)}"</li>`).join('')}
          </ul>
        </div>` : ''}
    </div>
  `;
}

function scoreColorVar(s) {
  if (s >= 70) return 'var(--green)';
  if (s >= 40) return 'var(--orange)';
  return 'var(--red)';
}

function renderTurnCard(t, opts) {
  opts = opts || {};
  const showRoundDivider = opts.showRoundDivider;
  const dims = (t.dimensions || []);
  const cardId = `turn_${t.id || Math.random().toString(36).slice(2)}`;
  const color = t.color || '#007AFF';

  // 사용자 질문 카드 (특별 디자인)
  if (t.is_user || t.persona === '👤 사용자') {
    const roundDivider = showRoundDivider ? `
      <div class="round-divider">
        <span class="round-divider-line"></span>
        <span class="round-divider-label">🔵 라운드 ${t.round || 1} 시작</span>
        <span class="round-divider-line"></span>
      </div>
    ` : '';
    return `
      ${roundDivider}
      <div class="user-turn-card">
        <div class="user-turn-icon">❓</div>
        <div class="user-turn-content">
          <div class="user-turn-label">사용자 추가 질문</div>
          <div class="user-turn-text">"${escapeHTML(t.synthesis || '')}"</div>
        </div>
      </div>
    `;
  }

  const dimsHtml = dims.map((d, di) => {
    const axClass = cssAxis(d.axis);
    const evHtml = (d.evidence || []).map(ev => {
      const src = ev.source || '';
      const quote = ev.quote || '';
      // 비교 모드 라벨 자동 인식
      const sideMatch = src.match(/^\[(.+?)\]/);
      const sideTag = sideMatch ? `<span class="ev-side-tag">${escapeHTML(sideMatch[1])}</span>` : '';
      const cleanSrc = src.replace(/^\[.+?\]\s*/, '');
      return `
        <div class="evidence-item-v2">
          <div class="evidence-header-v2">${sideTag}<span class="evidence-source-v2">${escapeHTML(cleanSrc)}</span></div>
          <div class="evidence-quote-v2">${escapeHTML(quote)}</div>
        </div>
      `;
    }).join('');


    return `
      <div class="dim-block-v2 axis-bg-${axClass}">
        <div class="dim-axis-v2 axis-${axClass}">
          <span>${AXIS_EMOJI[d.axis] || '·'}</span>
          <span>${escapeHTML(d.axis)}</span>
        </div>

        ${d.argument ? `
          <div class="dim-section-arg">
            <div class="dim-section-label">💭 주장</div>
            <div class="dim-arg-v2">${escapeHTML(d.argument)}</div>
          </div>
        ` : ''}

        ${d.action ? `
          <div class="dim-section-action">
            <div class="dim-section-label-action">✅ 실행 액션</div>
            <div class="dim-action-v2">${escapeHTML(d.action)}</div>
          </div>
        ` : ''}


        ${evHtml ? `
          <details class="evidence-collapse">
            <summary class="evidence-summary">
              <span>📎 근거 보기</span>
              <span class="evidence-count">${(d.evidence||[]).length}개</span>
            </summary>
            <div class="evidence-list-v2">${evHtml}</div>
          </details>
        ` : ''}
      </div>
    `;
  }).join('');

  const stance = t.stance || '신규관점';
  const roundDivider = showRoundDivider ? `
    <div class="round-divider">
      <span class="round-divider-line"></span>
      <span class="round-divider-label">🔵 라운드 ${t.round || 1} 시작</span>
      <span class="round-divider-line"></span>
    </div>
  ` : '';

  return `
    ${roundDivider}
    <div class="turn-card-v2" id="${cardId}" style="--persona-color:${color}">
      <div class="turn-card-side"></div>
      <div class="turn-card-main">
        <div class="turn-head-v2">
          <div class="turn-avatar-v2" style="background:${color}1A; color:${color}; border:2px solid ${color}33">
            ${escapeHTML(t.emoji || '💬')}
          </div>
          <div class="turn-head-info">
            <div class="turn-head-line1">
              <span class="turn-name-v2">${escapeHTML(t.persona)}</span>
              <span class="turn-stance-v2 stance-${stance}">${escapeHTML(stance)}</span>
              ${t.target ? `<span class="turn-target-v2">→ <strong>${escapeHTML(t.target)}</strong></span>` : ''}
            </div>
            <div class="turn-head-meta">
              <span>R${t.round || 1}</span>
              <span class="turn-axes">${dims.map(d => `${AXIS_EMOJI[d.axis]||'·'} ${escapeHTML(d.axis)}`).join(' · ')}</span>
            </div>
          </div>
        </div>

        ${t.synthesis ? `
          <div class="turn-synthesis-v2">
            <div class="turn-synthesis-mark">"</div>
            <div class="turn-synthesis-text">${escapeHTML(t.synthesis)}</div>
          </div>
        ` : ''}

        <div class="dim-cards-v2">${dimsHtml}</div>
      </div>
    </div>
  `;
}

function cssAxis(ax) { return ax.replace(/ /g, '-'); }

