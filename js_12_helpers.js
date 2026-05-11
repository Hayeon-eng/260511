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


function clampNumber(n, min, max) {
  return Math.max(min, Math.min(max, Number.isFinite(n) ? n : min));
}

function sessionSidesForReliability(session) {
  if (!session) return [];
  if (session.mode === 'compare') {
    const a = session.side_a || {};
    const b = session.side_b || {};
    return [
      { label: a.label || session.label_a || 'A', crawl: a.crawl || {}, analysis: a.analysis || {} },
      { label: b.label || session.label_b || 'B', crawl: b.crawl || {}, analysis: b.analysis || {} },
    ];
  }
  return [{ label: '분석 대상', crawl: session.crawl || {}, analysis: session.analysis || {} }];
}

function scoreOneCrawl(crawl, analysis) {
  const checks = (analysis && analysis.technical_checks) || (crawl && crawl.aeo_checks) || {};
  const headings = (crawl && crawl.headings) || {};
  const text = String((crawl && crawl.text) || '');
  const bodyLength = Number(checks.body_length || text.length || 0);
  const schemas = Array.isArray(crawl && crawl.schemas) ? crawl.schemas : [];
  const altCoverage = Number(checks.image_alt_coverage || 0);

  let score = 0;
  if (!crawl || crawl.ok === false) return 0;
  score += 6; // 크롤링/첨부 분석 파이프라인이 정상 응답
  if (bodyLength >= 1500) score += 6;
  else if (bodyLength >= 500) score += 4;
  else if (bodyLength >= 120) score += 2;
  if ((crawl && crawl.title) || checks.has_title) score += 3;
  if ((crawl && crawl.meta_description) || checks.has_meta_desc) score += 3;
  if ((headings.h1 || []).length || checks.has_h1) score += 3;
  if ((headings.h2 || []).length) score += 2;
  if (schemas.length || checks.has_schema) score += 5;
  if (altCoverage >= 70) score += 2;
  else if (altCoverage >= 30) score += 1;
  return clampNumber(score, 0, 30);
}

function calculateAnalysisReliability(session) {
  const sides = sessionSidesForReliability(session);
  const turns = Array.isArray(session && session.turns) ? session.turns : [];
  const digest = session && session.digest && session.digest.digest;
  const attachments = Array.isArray(session && session.attachments) ? session.attachments : [];

  const crawlScores = sides.map(side => scoreOneCrawl(side.crawl, side.analysis));
  const dataScore = crawlScores.length
    ? Math.round(crawlScores.reduce((a, b) => a + b, 0) / crawlScores.length)
    : 0;

  const allAnalyses = sides.map(s => s.analysis || {}).filter(Boolean);
  const hasAnySchema = sides.some(side => {
    const crawlSchemas = Array.isArray(side.crawl && side.crawl.schemas) ? side.crawl.schemas : [];
    const checks = (side.analysis && side.analysis.technical_checks) || (side.crawl && side.crawl.aeo_checks) || {};
    return crawlSchemas.length > 0 || Boolean(checks.has_schema);
  });
  const hasProductSignals = sides.some(side => {
    const blob = JSON.stringify({
      schemas: side.crawl && side.crawl.schemas,
      text: side.crawl && side.crawl.text,
      analysis: side.analysis,
    }).toLowerCase();
    return /product|offer|review|aggregaterating|price|stock|availability|faq|breadcrumb/.test(blob);
  });

  const dimensions = [];
  turns.forEach(t => (t.dimensions || []).forEach(d => dimensions.push(d)));
  const evidence = [];
  dimensions.forEach(d => (d.evidence || []).forEach(ev => evidence.push(ev)));
  const sourceText = evidence.map(ev => String((ev && ev.source) || '')).join(' ').toLowerCase();
  const quoteCount = evidence.filter(ev => String((ev && ev.quote) || '').trim().length >= 12).length;

  let groundingScore = 0;
  if (evidence.length >= 8) groundingScore += 8;
  else if (evidence.length >= 4) groundingScore += 6;
  else if (evidence.length >= 1) groundingScore += 3;
  if (quoteCount >= 5) groundingScore += 6;
  else if (quoteCount >= 2) groundingScore += 4;
  else if (quoteCount >= 1) groundingScore += 2;
  if (/json-ld|schema|product|offer|review|aggregate|faq|breadcrumb/.test(sourceText) || hasAnySchema) {
    groundingScore += 6;
  }
  if (/aeo|score|점수|technical|meta|og|h1|h2|alt|title/.test(sourceText)) {
    groundingScore += 3;
  }
  if (allAnalyses.some(a => (a.key_insights || []).length || a.by_dimension)) {
    groundingScore += 2;
  }
  groundingScore = clampNumber(groundingScore, 0, 25);

  let stabilityScore = 0;
  const allHaveSummary = allAnalyses.length > 0 && allAnalyses.every(a => a.summary || a.aeo_reason || a.by_dimension);
  if (allHaveSummary) stabilityScore += 7;
  if (turns.length >= 2) stabilityScore += 5;
  if (digest) stabilityScore += 4;
  const failureText = JSON.stringify(turns).toLowerCase();
  if (!/응답 생성 실패|api 키|빈 응답|파싱 실패|error|failed/.test(failureText)) stabilityScore += 4;
  stabilityScore = clampNumber(stabilityScore, 0, 20);

  let inferenceScore = 15;
  const analysisText = JSON.stringify({ analyses: allAnalyses, turns }).toLowerCase();
  const inferenceWords = (analysisText.match(/가능성|추정|예상|보인다|것 같다|추천|인식|perception|likely|could|may/g) || []).length;
  if (inferenceWords >= 16) inferenceScore -= 5;
  else if (inferenceWords >= 8) inferenceScore -= 3;
  // 실제 노출/전환/검색 로그는 현재 앱에 직접 연동되지 않으므로 기본 리스크로 반영.
  inferenceScore -= 4;
  if (!hasProductSignals) inferenceScore -= 2;
  inferenceScore = clampNumber(inferenceScore, 0, 15);

  let verificationScore = 0;
  if (hasAnySchema) verificationScore += 3;
  if (hasProductSignals) verificationScore += 3;
  if (attachments.length) verificationScore += 1;
  if (sides.some(side => Boolean(side.crawl && side.crawl.url))) verificationScore += 2;
  if (quoteCount >= 3) verificationScore += 1;
  verificationScore = clampNumber(verificationScore, 0, 10);

  let score = Math.round(dataScore + groundingScore + stabilityScore + inferenceScore + verificationScore);
  score = clampNumber(score, 30, 95);

  const basis = [];
  const cautions = [];
  basis.push(`데이터 수집 ${dataScore}/30`);
  basis.push(`근거 충실도 ${groundingScore}/25`);
  basis.push(`AI 응답 안정성 ${stabilityScore}/20`);
  if (hasAnySchema) basis.push('스키마/구조화 데이터 확인');
  if (quoteCount) basis.push(`직접 인용 ${quoteCount}개`);
  if (digest) basis.push('라이브 다이제스트 생성됨');

  cautions.push('실제 ChatGPT/Google Shopping 노출 여부는 직접 연동되지 않음');
  cautions.push('전환율·클릭률·Merchant Center 상태는 추가 검증 필요');
  if (!hasAnySchema) cautions.push('구조화 데이터 확인 신호가 약함');
  if (evidence.length < 4) cautions.push('페르소나 발언의 직접 근거 수가 적음');
  if (attachments.some(a => a.kind === 'pdf' || a.kind === 'image')) {
    cautions.push('첨부 PDF/이미지는 텍스트/비전 추출 오류 가능성 있음');
  }

  return {
    score,
    basis: basis.slice(0, 6),
    cautions: cautions.slice(0, 5),
    components: { dataScore, groundingScore, stabilityScore, inferenceScore, verificationScore },
  };
}

function reliabilityTone(score) {
  if (score >= 90) return 'very-high';
  if (score >= 70) return 'good';
  if (score >= 50) return 'mid';
  return 'low';
}

function renderAnalysisReliability(session, variant) {
  const meta = calculateAnalysisReliability(session);
  const compact = variant === 'compact';
  return `
    <div class="reliability-card reliability-${reliabilityTone(meta.score)} ${compact ? 'compact' : ''}">
      <div class="reliability-head">
        <div>
          <div class="reliability-label">검증 메모</div>
          <div class="reliability-title">분석 신뢰도 <strong>${meta.score}%</strong></div>
        </div>
        <div class="reliability-score">${meta.score}</div>
      </div>
      <div class="reliability-body">
        <div class="reliability-col">
          <div class="reliability-subtitle">근거</div>
          <ul>${meta.basis.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>
        </div>
        <div class="reliability-col">
          <div class="reliability-subtitle">주의</div>
          <ul>${meta.cautions.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>
        </div>
      </div>
      <details class="reliability-rubric">
        <summary>신뢰도 기준 보기</summary>
        <div>90~95%: 원문/스키마/정량 데이터가 충분하고 오류 없음</div>
        <div>70~89%: 일반적으로 신뢰 가능하지만 일부 추론 포함</div>
        <div>50~69%: 데이터 부족 또는 추론 비중 높음</div>
        <div>30~49%: 크롤링/추출/LLM 응답 문제가 있어 참고용</div>
      </details>
    </div>
  `;
}

