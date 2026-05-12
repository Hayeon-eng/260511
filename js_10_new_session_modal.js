// =========================================
// New Session Modal
// =========================================

const TOPIC_PRESETS = [
  '이 제품 페이지가 AI Agent 추천 답변에 잘 들어갈 수 있을까?',
  '이 페이지의 브랜드 메시지는 공식 브랜드 아이덴티티와 잘 맞을까?',
  '이 카피 문구가 AI Agent가 이해하고 인용하기 좋은 구조일까?',
  '경쟁사 대비 AI Commerce 관점에서 어떤 페이지가 더 유리할까?',
];

const URL_PRESETS = [
  {
    key: 'apple',
    label: 'Apple iPhone 17 Pro',
    url: 'https://www.apple.com/uk/iphone-17-pro/',
  },
  {
    key: 'samsung',
    label: 'Samsung Galaxy S26 Ultra',
    url: 'https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/',
  },
];

const KV_IMAGE_PRESETS = [
  {
    key: 'apple',
    label: 'iPhone 17 Pro KV',
    url: 'https://www.apple.com/v/iphone-17-pro/d/images/overview/welcome/hero__bdntboqignj6_xlarge.jpg',
  },
  {
    key: 'samsung',
    label: 'Galaxy S26 Ultra KV',
    url: 'https://images.samsung.com/sg/smartphones/galaxy-s26-ultra/images/galaxy-s26-ultra-features-kv.jpg?imbypass=true',
  },
];

const COPY_BRAND_OPTIONS = [
  { value: 'Samsung Galaxy', label: 'Samsung Galaxy' },
  { value: 'Apple', label: 'Apple' },
];

function renderVisualList(side) {
  const arr = side === 'A' ? State.visualA : (side === 'B' ? State.visualB : State.visualUrls);
  if (!arr || !arr.length) {
    return '<div class="hint">선택한 KV 이미지 프리셋이 없습니다.</div>';
  }
  return arr.map(v => `
    <div class="uploaded-item">
      🖼️ ${escapeHTML(v.label || 'KV 이미지')}
      <span class="x" onclick="removeVisualPreset('${escapeAttr(v.url)}', '${side || ''}')">✕</span>
    </div>
  `).join('');
}

function openNewSessionModal() {
  State.uploadedFiles = [];
  State.uploadedA = [];
  State.uploadedB = [];
  State.visualUrls = [];
  State.visualA = [];
  State.visualB = [];
  State.maxRounds = 1;
  State.sessionMode = 'single';
  State.copyCompareResult = null;
  State.newSessionDraft = {
    query: '',
    url: '',
    copyText: '',
    labelA: '',
    urlA: '',
    labelB: '',
    urlB: '',
    copyBrand: 'Samsung Galaxy',
    copyProduct: '',
    copyA: '',
    copyB: '',
  };

  // 토큰 절약을 위해 기본은 1라운드 + AI Commerce 페르소나 1명만 선택
  const preferred = State.personas.find(p => p.name === 'AICommerceHacker')
    || State.personas.find(p => (p.focus_dimensions || []).includes('AI Commerce'))
    || State.personas[0];
  State.selectedPersonas = preferred ? [preferred.name] : [];
  renderNewSessionModal();
}

function captureNewSessionDraft() {
  const d = State.newSessionDraft || {};
  const get = (id, key) => {
    const el = document.getElementById(id);
    return el ? el.value : (d[key] || '');
  };
  d.query = get('ns_query', 'query');
  d.url = get('ns_url', 'url');
  d.copyText = get('ns_copy_text', 'copyText');
  d.labelA = get('ns_label_A', 'labelA');
  d.urlA = get('ns_url_A', 'urlA');
  d.labelB = get('ns_label_B', 'labelB');
  d.urlB = get('ns_url_B', 'urlB');
  d.copyBrand = get('ns_copy_brand', 'copyBrand') || 'Samsung Galaxy';
  d.copyProduct = get('ns_copy_product', 'copyProduct');
  d.copyA = get('ns_copy_A', 'copyA');
  d.copyB = get('ns_copy_B', 'copyB');
  State.newSessionDraft = d;
}

function draftVal(key) {
  const d = State.newSessionDraft || {};
  return escapeAttr(d[key] || '');
}

function draftText(key) {
  const d = State.newSessionDraft || {};
  return escapeHTML(d[key] || '');
}

function renderModeTabs(mode) {
  return `
    <div class="seg-row seg-row-3">
      <div class="seg ${mode === 'single' ? 'active' : ''}" onclick="pickMode('single')">📄 단일 분석</div>
      <div class="seg ${mode === 'compare' ? 'active' : ''}" onclick="pickMode('compare')">🆚 A/B 페이지 비교</div>
      <div class="seg ${mode === 'copy' ? 'active' : ''}" onclick="pickMode('copy')">✍️ 카피 비교</div>
    </div>
  `;
}

function renderTopicField(mode) {
  const placeholder = mode === 'copy'
    ? '예: Galaxy 신제품 런칭 카피 A/B 중 어떤 문구가 더 적합할까?'
    : (mode === 'compare'
      ? '예: 우리 페이지 vs 애플 페이지, AI 추천에 누가 더 잘 들어갈까?'
      : '예: 우리 신제품 페이지가 AI Agent 추천에 잘 들어갈까?');

  return `
    <div class="field">
      <label>토론 주제 ${mode === 'copy' ? '<span class="optional-label">선택</span>' : '*'}</label>
      <input class="input" id="ns_query" value="${draftVal('query')}" placeholder="${escapeAttr(placeholder)}">
      <div class="preset-group">
        <span class="preset-label">자주 쓰는 주제</span>
        <div class="preset-row">
          ${TOPIC_PRESETS.map(x => `
            <button type="button" class="preset-chip" onclick='applyTopicPreset(${JSON.stringify(x)})'>
              ${escapeHTML(x.replace('이 ', '').replace('가 ', ' · ')).slice(0, 24)}
            </button>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderSingleFields() {
  return `
    <div class="field">
      <label>분석할 URL (웹페이지 또는 YouTube)</label>
      <input class="input" id="ns_url" value="${draftVal('url')}" placeholder="https://example.com/product/... 또는 https://youtube.com/watch?v=...">
      <div class="preset-group compact">
        <span class="preset-label">URL 빠른 입력</span>
        <div class="preset-row">
          ${URL_PRESETS.map(p => `
            <button type="button" class="preset-chip" onclick='applyUrlPreset(${JSON.stringify(p)})'>${escapeHTML(p.label)}</button>
          `).join('')}
        </div>
      </div>
      <div class="hint">URL이 없으면 첨부파일 또는 카피 문구만 분석할 수도 있습니다. YouTube는 가능한 경우 자막/자동자막과 페이지 메타데이터를 분석합니다. 영상 화면 자체는 분석하지 않습니다.</div>
    </div>
    <div class="field">
      <label>카피 문구로 분석 (선택)</label>
      <textarea class="textarea copy-textarea" id="ns_copy_text" placeholder="URL 없이 카피 문구만 붙여넣어도 AI 적합도·브랜드 메시지 적합도 중심으로 간단 진단할 수 있습니다.">${draftText('copyText')}</textarea>
      <div class="hint">카피만 입력하면 페이지 구조·이미지·UX 정보는 제한적으로 평가됩니다. URL과 함께 입력하면 추가 카피 근거로 함께 반영됩니다.</div>
    </div>
    <div class="field">
      <label>KV 이미지 프리셋</label>
      <div class="preset-row">
        ${KV_IMAGE_PRESETS.map(p => `
          <button type="button" class="preset-chip" onclick='addVisualPreset(${JSON.stringify(p)})'>${escapeHTML(p.label)}</button>
        `).join('')}
      </div>
      <div class="uploaded-list visual-preset-list">${renderVisualList('')}</div>
      <div class="hint">공식 페이지의 KV 이미지를 시각 참고자료로 함께 분석합니다. 외부 이미지 다운로드 실패 시 해당 이미지만 건너뜁니다.</div>
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
  `;
}

function renderCompareFields() {
  return `
    <div class="compare-grid">
      ${['A','B'].map(side => {
        const label = side === 'A' ? '좌측 (A)' : '우측 (B)';
        const arr = side === 'A' ? State.uploadedA : State.uploadedB;
        const labelKey = side === 'A' ? 'labelA' : 'labelB';
        const urlKey = side === 'A' ? 'urlA' : 'urlB';
        return `
          <div class="compare-card">
            <div class="compare-card-head">${label}</div>
            <div class="field" style="margin-bottom:10px">
              <label>라벨</label>
              <input class="input" id="ns_label_${side}" value="${draftVal(labelKey)}" placeholder="${side === 'A' ? '우리 페이지' : '애플 페이지'}">
            </div>
            <div class="field" style="margin-bottom:10px">
              <label>URL (웹페이지 또는 YouTube)</label>
              <input class="input" id="ns_url_${side}" value="${draftVal(urlKey)}" placeholder="https://...">
              <div class="preset-group compact">
                <span class="preset-label">URL 빠른 입력</span>
                <div class="preset-row">
                  ${URL_PRESETS.map(p => `
                    <button type="button" class="preset-chip" onclick='applyUrlPreset(${JSON.stringify(p)}, "${side}")'>${escapeHTML(p.label)}</button>
                  `).join('')}
                </div>
              </div>
              <div class="hint">YouTube는 가능한 경우 자막/자동자막과 페이지 메타데이터를 분석합니다. 영상 화면 자체는 분석하지 않습니다.</div>
            </div>
            <div class="field" style="margin-bottom:10px">
              <label>KV 이미지 프리셋</label>
              <div class="preset-row">
                ${KV_IMAGE_PRESETS.map(p => `
                  <button type="button" class="preset-chip" onclick='addVisualPreset(${JSON.stringify(p)}, "${side}")'>${escapeHTML(p.label)}</button>
                `).join('')}
              </div>
              <div class="uploaded-list visual-preset-list">${renderVisualList(side)}</div>
              <div class="hint">공식 페이지의 KV 이미지를 시각 참고자료로 함께 분석합니다. 외부 이미지 다운로드 실패 시 해당 이미지만 건너뜁니다.</div>
            </div>
            <div class="field" style="margin-bottom:0">
              <label>첨부 (PDF · 이미지)</label>
              <div class="upload-zone-mini" onclick="document.getElementById('ns_file_${side}').click()">📎 클릭해서 추가</div>
              <input type="file" id="ns_file_${side}" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif" style="display:none" onchange="handleUpload(event, '${side}')">
              <div class="uploaded-list">
                ${arr.map(f => `
                  <div class="uploaded-item">
                    ${f.kind === 'pdf' ? '📄' : '🖼️'} ${escapeHTML(f.filename)}
                    <span class="x" onclick="removeUpload('${f.id}', '${side}')">✕</span>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderCopyCompareFields() {
  const selectedBrand = (State.newSessionDraft || {}).copyBrand || 'Samsung Galaxy';
  return `
    <div class="copy-compare-box">
      <div class="copy-compare-note">
        <strong>당사 카피 A/B 비교</strong>
        <span>URL/이미지 분석과 달리, 입력한 카피 문구 자체를 AI Agent 적합도·브랜드 페르소나 적합도·메시지 명확성 중심으로 빠르게 비교합니다.</span>
      </div>
      <div class="compare-grid copy-meta-grid">
        <div class="field">
          <label>브랜드 기준</label>
          <select class="select" id="ns_copy_brand">
            ${COPY_BRAND_OPTIONS.map(b => `
              <option value="${escapeAttr(b.value)}" ${selectedBrand === b.value ? 'selected' : ''}>${escapeHTML(b.label)}</option>
            `).join('')}
          </select>
          <div class="hint">공식 브랜드 아이덴티티와 브랜드 페르소나 기준으로 비교합니다.</div>
        </div>
        <div class="field">
          <label>제품/카테고리</label>
          <input class="input" id="ns_copy_product" value="${draftVal('copyProduct')}" placeholder="예: 스마트폰 / 워치 / 태블릿 / 이어버드">
          <div class="hint">제품 맥락을 넣으면 카피 판단이 더 정확해집니다.</div>
        </div>
      </div>
      <div class="compare-grid copy-ab-grid">
        <div class="compare-card">
          <div class="compare-card-head">카피 A</div>
          <textarea class="textarea copy-ab-textarea" id="ns_copy_A" placeholder="카피 A 후보를 입력하세요.">${draftText('copyA')}</textarea>
        </div>
        <div class="compare-card">
          <div class="compare-card-head">카피 B</div>
          <textarea class="textarea copy-ab-textarea" id="ns_copy_B" placeholder="카피 B 후보를 입력하세요.">${draftText('copyB')}</textarea>
        </div>
      </div>
      <div class="copy-quick-actions">
        <button type="button" class="btn-secondary" onclick="quickCompareCopy()">⚡ 빠른 비교</button>
        <div class="hint">빠른 비교는 요약 팝업만 띄웁니다. 하단의 토론 시작을 누르면 같은 카피를 기준으로 페르소나 심화토론을 진행합니다.</div>
      </div>
    </div>
  `;
}

function renderNewSessionModal() {
  const mode = State.sessionMode || 'single';
  const modeHint = mode === 'copy'
    ? '당사 내부 A/B 카피 후보를 빠르게 비교하고, 필요하면 페르소나 심화토론으로 이어갑니다.'
    : (mode === 'compare'
      ? '두 콘텐츠(우리 vs 경쟁사, 또는 A안 vs B안)를 같은 페르소나들이 비교 토론합니다.'
      : '하나의 URL, 파일 또는 카피 문구를 5개 축으로 진단합니다.');
  const modeFields = mode === 'copy'
    ? renderCopyCompareFields()
    : (mode === 'compare' ? renderCompareFields() : renderSingleFields());

  const html = `
    <div class="modal-overlay" onclick="if(event.target===this) closeModal()">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">새 토론 시작</div>
          <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>분석 방식</label>
            ${renderModeTabs(mode)}
            <div class="hint">${escapeHTML(modeHint)}</div>
          </div>
          ${renderTopicField(mode)}
          ${modeFields}
          <div class="field">
            <label>최대 라운드 (자동 진행 시)</label>
            <div class="dim-toggle-row">
              ${[1,2,3,5,999].map(n => `
                <div class="dim-toggle ${State.maxRounds===n?'active':''}" onclick="pickRounds(${n})">
                  ${n===999 ? '무제한' : n+'라운드'}
                </div>
              `).join('')}
            </div>
            <div class="hint">한 라운드 = 모든 페르소나가 한 번씩 발언.</div>
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
            <div class="hint">토큰 절약을 위해 기본은 1명입니다. 필요할 때만 페르소나를 추가하세요.</div>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn-secondary" onclick="closeModal()">취소</button>
          <button class="btn-primary" id="btn_start_session" onclick="startSession()">${mode === 'copy' ? '토론 시작' : '분석 시작'}</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById('modal_root').innerHTML = html;
}

function applyTopicPreset(text) {
  const input = document.getElementById('ns_query');
  if (input) {
    input.value = text;
    input.focus();
  }
  captureNewSessionDraft();
}

function applyUrlPreset(preset, side) {
  const id = side ? `ns_url_${side}` : 'ns_url';
  const input = document.getElementById(id);
  if (input) input.value = preset.url || '';
  if (side) {
    const label = document.getElementById(`ns_label_${side}`);
    if (label && !label.value.trim()) label.value = preset.label || '';
  }
  captureNewSessionDraft();
}

function addVisualPreset(preset, side) {
  captureNewSessionDraft();
  const target = side === 'A' ? State.visualA : (side === 'B' ? State.visualB : State.visualUrls);
  if (!target.some(v => v.url === preset.url)) {
    target.push({ label: preset.label, url: preset.url });
  }
  renderNewSessionModal();
}

function removeVisualPreset(url, side) {
  captureNewSessionDraft();
  if (side === 'A') State.visualA = State.visualA.filter(v => v.url !== url);
  else if (side === 'B') State.visualB = State.visualB.filter(v => v.url !== url);
  else State.visualUrls = State.visualUrls.filter(v => v.url !== url);
  renderNewSessionModal();
}

function pickMode(mode) {
  captureNewSessionDraft();
  State.sessionMode = mode;
  State.copyCompareResult = null;
  renderNewSessionModal();
}

function togglePersonaPick(name) {
  captureNewSessionDraft();
  const i = State.selectedPersonas.indexOf(name);
  if (i >= 0) State.selectedPersonas.splice(i, 1);
  else State.selectedPersonas.push(name);
  renderNewSessionModal();
}

function pickRounds(n) {
  captureNewSessionDraft();
  State.maxRounds = n;
  renderNewSessionModal();
}

async function handleUpload(ev, side) {
  captureNewSessionDraft();
  const files = Array.from(ev.target.files || []);
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    try {
      toast(`업로드 중: ${f.name}`);
      const r = await fetch('/api/upload', { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || '업로드 실패');
      if (side === 'A') State.uploadedA.push(d);
      else if (side === 'B') State.uploadedB.push(d);
      else State.uploadedFiles.push(d);
    } catch (e) {
      toast(`업로드 실패: ${f.name}`, 'error');
    }
  }
  captureNewSessionDraft();
  renderNewSessionModal();
}

function removeUpload(id, side) {
  captureNewSessionDraft();
  if (side === 'A') State.uploadedA = State.uploadedA.filter(f => f.id !== id);
  else if (side === 'B') State.uploadedB = State.uploadedB.filter(f => f.id !== id);
  else State.uploadedFiles = State.uploadedFiles.filter(f => f.id !== id);
  renderNewSessionModal();
}

function collectCopyCompareData() {
  captureNewSessionDraft();
  const d = State.newSessionDraft || {};
  return {
    brand: (d.copyBrand || 'Samsung Galaxy').trim(),
    product: (d.copyProduct || '').trim(),
    query: (d.query || '').trim(),
    copy_a: (d.copyA || '').trim(),
    copy_b: (d.copyB || '').trim(),
  };
}

function validateCopyCompareData(data) {
  if (!data.product) return '제품/카테고리를 입력하세요';
  if (!data.copy_a || !data.copy_b) return '카피 A와 카피 B를 모두 입력하세요';
  return '';
}

async function quickCompareCopy() {
  const data = collectCopyCompareData();
  const err = validateCopyCompareData(data);
  if (err) {
    toast(err, 'error');
    return;
  }

  const btn = document.querySelector('.copy-quick-actions .btn-secondary');
  const oldText = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = '비교 중...';
  }

  try {
    const r = await fetch('/api/copy/compare', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const result = await r.json();
    if (!r.ok) throw new Error(result.detail || '카피 비교 실패');
    showCopyComparePopup(result);
  } catch (e) {
    toast('카피 비교 실패: ' + e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = oldText || '⚡ 빠른 비교';
    }
  }
}

function showCopyComparePopup(result) {
  const old = document.getElementById('copy_compare_popup');
  if (old) old.remove();
  const winnerLabel = result.winner === 'A' ? '카피 A 우세'
    : (result.winner === 'B' ? '카피 B 우세' : '무승부');
  const reasons = result.reasons || [];
  const cautions = result.cautions || [];
  document.body.insertAdjacentHTML('beforeend', `
    <div class="modal-overlay copy-result-overlay" id="copy_compare_popup" onclick="if(event.target===this) closeCopyComparePopup()">
      <div class="modal copy-result-modal">
        <div class="modal-head">
          <div class="modal-title">✍️ 카피 빠른 비교 결과</div>
          <button class="modal-close" onclick="closeCopyComparePopup()">✕</button>
        </div>
        <div class="modal-body">
          <div class="copy-winner-card">
            <div class="copy-winner-label">추천</div>
            <div class="copy-winner-title">${escapeHTML(winnerLabel)}</div>
            <div class="copy-winner-summary">${escapeHTML(result.summary || '')}</div>
          </div>
          <div class="copy-score-row">
            <div class="copy-score-card">
              <div class="copy-score-label">카피 A</div>
              <div class="copy-score-num">${Number(result.a_score || 0)}</div>
            </div>
            <div class="copy-score-card">
              <div class="copy-score-label">카피 B</div>
              <div class="copy-score-num">${Number(result.b_score || 0)}</div>
            </div>
          </div>
          ${reasons.length ? `
            <div class="copy-result-section">
              <div class="copy-result-section-title">이유</div>
              <ul>${reasons.map(x => `<li>${escapeHTML(x)}</li>`).join('')}</ul>
            </div>` : ''}
          ${result.recommended_revision ? `
            <div class="copy-result-section">
              <div class="copy-result-section-title">추천 수정 방향</div>
              <div class="copy-revision-box">${escapeHTML(result.recommended_revision)}</div>
            </div>` : ''}
          ${cautions.length ? `
            <div class="copy-result-note">
              ${cautions.map(x => `<div>※ ${escapeHTML(x)}</div>`).join('')}
            </div>` : ''}
        </div>
        <div class="modal-foot">
          <button class="btn-secondary" onclick="closeCopyComparePopup()">닫기</button>
          <button class="btn-primary" onclick="closeCopyComparePopup(); startSession();">이 카피로 심화토론 시작</button>
        </div>
      </div>
    </div>
  `);
}

function closeCopyComparePopup() {
  const el = document.getElementById('copy_compare_popup');
  if (el) el.remove();
}

function buildCopySessionQuery(data, rawQuery) {
  const q = (rawQuery || data.query || '').trim();
  if (q) return q;
  return `${data.brand} ${data.product} 카피 A/B 중 어떤 문구가 더 AI Agent와 브랜드 페르소나에 적합한가?`;
}

async function startSession() {
  let query = (document.getElementById('ns_query')?.value || '').trim();
  if (State.sessionMode !== 'copy' && !query) {
    toast('토론 주제를 입력하세요', 'error');
    return;
  }
  if (!State.selectedPersonas.length) {
    toast('페르소나를 1명 이상 선택하세요', 'error');
    return;
  }

  const chosenPersonas = State.personas.filter(p => State.selectedPersonas.includes(p.name));
  const btn = document.getElementById('btn_start_session');
  btn.disabled = true;
  btn.textContent = State.sessionMode === 'copy' ? '토론 준비 중...' : '분석 중...';

  let payload;
  if (State.sessionMode === 'copy') {
    const data = collectCopyCompareData();
    const err = validateCopyCompareData(data);
    if (err) {
      toast(err, 'error');
      btn.disabled = false;
      btn.textContent = '토론 시작';
      return;
    }
    query = buildCopySessionQuery(data, query);
    const commonHeader = `[브랜드 기준] ${data.brand}\n[제품/카테고리] ${data.product}\n`;
    payload = {
      query,
      mode: 'compare',
      personas: chosenPersonas,
      max_rounds: State.maxRounds || 1,
      side_a: {
        label: '카피 A',
        url: '',
        copy_text: `${commonHeader}[카피 A]\n${data.copy_a}`,
        attachment_ids: [],
        image_urls: [],
      },
      side_b: {
        label: '카피 B',
        url: '',
        copy_text: `${commonHeader}[카피 B]\n${data.copy_b}`,
        attachment_ids: [],
        image_urls: [],
      },
    };
  } else if (State.sessionMode === 'compare') {
    const urlA = document.getElementById('ns_url_A').value.trim();
    const urlB = document.getElementById('ns_url_B').value.trim();
    const labelA = document.getElementById('ns_label_A').value.trim() || '우리';
    const labelB = document.getElementById('ns_label_B').value.trim() || '비교 대상';
    if ((!urlA && !State.uploadedA.length && !State.visualA.length) || (!urlB && !State.uploadedB.length && !State.visualB.length)) {
      toast('양쪽 모두 URL, 파일, KV 이미지 중 하나는 필요해요', 'error');
      btn.disabled = false;
      btn.textContent = '분석 시작';
      return;
    }
    payload = {
      query,
      mode: 'compare',
      personas: chosenPersonas,
      max_rounds: State.maxRounds || 1,
      side_a: { label: labelA, url: urlA, attachment_ids: State.uploadedA.map(f => f.id), image_urls: State.visualA.map(v => v.url) },
      side_b: { label: labelB, url: urlB, attachment_ids: State.uploadedB.map(f => f.id), image_urls: State.visualB.map(v => v.url) },
    };
  } else {
    const url = document.getElementById('ns_url').value.trim();
    const copyText = (document.getElementById('ns_copy_text')?.value || '').trim();
    if (!url && !State.uploadedFiles.length && !copyText && !State.visualUrls.length) {
      toast('URL, 파일, 카피 문구, KV 이미지 중 하나는 필요해요', 'error');
      btn.disabled = false;
      btn.textContent = '분석 시작';
      return;
    }
    payload = {
      query,
      url,
      copy_text: copyText,
      mode: 'single',
      personas: chosenPersonas,
      attachment_ids: State.uploadedFiles.map(f => f.id),
      image_urls: State.visualUrls.map(v => v.url),
      max_rounds: State.maxRounds || 1,
    };
  }

  try {
    const r = await fetch('/api/sessions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '세션 생성 실패');
    closeModal();
    await loadSessions();
    await loadSession(d.session_id);
    toast(State.sessionMode === 'copy' ? '카피 비교 세션 생성 완료 · 자동 진행을 누르세요' : '분석 완료 · 자동 진행을 누르세요');
  } catch (e) {
    toast('실패: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = State.sessionMode === 'copy' ? '토론 시작' : '분석 시작';
  }
}
