// =========================================
// New Session Modal
// =========================================
function openNewSessionModal() {
  State.uploadedFiles = [];     // 단일 모드용
  State.uploadedA = [];         // 비교 모드 A
  State.uploadedB = [];         // 비교 모드 B
  State.maxRounds = 1;
  State.sessionMode = 'single'; // 'single' | 'compare'
  // 토큰 절약을 위해 기본은 1라운드 + 1명만 선택
  const preferred = State.personas.find(p => p.name === 'AICommerceHacker') || State.personas.find(p => (p.focus_dimensions || []).includes('AI Commerce')) || State.personas[0];
  State.selectedPersonas = preferred ? [preferred.name] : [];
  renderNewSessionModal();
}

function renderNewSessionModal() {
  const isCompare = State.sessionMode === 'compare';
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
            <div class="seg-row">
              <div class="seg ${!isCompare?'active':''}" onclick="pickMode('single')">📄 단일 분석</div>
              <div class="seg ${isCompare?'active':''}" onclick="pickMode('compare')">🆚 A/B 비교</div>
            </div>
            <div class="hint">${isCompare ? '두 콘텐츠(우리 vs 경쟁사, 또는 A안 vs B안)를 같은 페르소나들이 비교 토론합니다.' : '하나의 URL 또는 파일을 5개 축으로 진단합니다.'}</div>
          </div>

          <div class="field">
            <label>토론 주제 *</label>
            <input class="input" id="ns_query" placeholder="${isCompare ? '예: 우리 페이지 vs 애플 페이지, AI 추천에 누가 더 잘 들어갈까?' : '예: 우리 신제품 페이지가 AI Agent 추천에 잘 들어갈까?'}">
          </div>

          ${isCompare ? `
            <!-- 비교 모드: A/B 카드 두 개 -->
            <div class="compare-grid">
              ${['A','B'].map(side => {
                const label = side === 'A' ? '좌측 (A)' : '우측 (B)';
                const arr = side === 'A' ? State.uploadedA : State.uploadedB;
                return `
                <div class="compare-card">
                  <div class="compare-card-head">${label}</div>
                  <div class="field" style="margin-bottom:10px">
                    <label>라벨</label>
                    <input class="input" id="ns_label_${side}" placeholder="${side === 'A' ? '우리 페이지' : '애플 페이지'}">
                  </div>
                  <div class="field" style="margin-bottom:10px">
                    <label>URL (웹페이지 또는 YouTube)</label>
                    <input class="input" id="ns_url_${side}" placeholder="https://...">
                    <div class="hint">YouTube는 가능한 경우 자막/자동자막과 페이지 메타데이터를 분석합니다. 영상 화면 자체는 분석하지 않습니다.</div>
                  </div>
                  <div class="field" style="margin-bottom:0">
                    <label>첨부 (PDF · 이미지)</label>
                    <div class="upload-zone-mini" onclick="document.getElementById('ns_file_${side}').click()">
                      📎 클릭해서 추가
                    </div>
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
          ` : `
            <!-- 단일 모드 -->
            <div class="field">
              <label>분석할 URL (웹페이지 또는 YouTube)</label>
              <input class="input" id="ns_url" placeholder="https://example.com/product/... 또는 https://youtube.com/watch?v=...">
              <div class="hint">URL이 없으면 첨부파일만 분석할 수도 있습니다. YouTube는 가능한 경우 자막/자동자막과 페이지 메타데이터를 분석합니다. 영상 화면 자체는 분석하지 않습니다.</div>
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
          `}

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
          <button class="btn-primary" id="btn_start_session" onclick="startSession()">분석 시작</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById('modal_root').innerHTML = html;
}

function pickMode(mode) {
  State.sessionMode = mode;
  renderNewSessionModal();
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

async function handleUpload(ev, side) {
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
  renderNewSessionModal();
}

function removeUpload(id, side) {
  if (side === 'A') State.uploadedA = State.uploadedA.filter(f => f.id !== id);
  else if (side === 'B') State.uploadedB = State.uploadedB.filter(f => f.id !== id);
  else State.uploadedFiles = State.uploadedFiles.filter(f => f.id !== id);
  renderNewSessionModal();
}

async function startSession() {
  const query = document.getElementById('ns_query').value.trim();
  if (!query) { toast('토론 주제를 입력하세요', 'error'); return; }
  if (!State.selectedPersonas.length) { toast('페르소나를 1명 이상 선택하세요', 'error'); return; }

  const chosenPersonas = State.personas.filter(p => State.selectedPersonas.includes(p.name));
  const btn = document.getElementById('btn_start_session');
  btn.disabled = true;
  btn.textContent = '분석 중...';

  let payload;
  if (State.sessionMode === 'compare') {
    const urlA = document.getElementById('ns_url_A').value.trim();
    const urlB = document.getElementById('ns_url_B').value.trim();
    const labelA = document.getElementById('ns_label_A').value.trim() || '우리';
    const labelB = document.getElementById('ns_label_B').value.trim() || '비교 대상';
    if ((!urlA && !State.uploadedA.length) || (!urlB && !State.uploadedB.length)) {
      toast('양쪽 모두 URL 또는 파일이 필요해요', 'error');
      btn.disabled = false; btn.textContent = '분석 시작';
      return;
    }
    payload = {
      query, mode: 'compare',
      personas: chosenPersonas,
      max_rounds: State.maxRounds || 1,
      side_a: { label: labelA, url: urlA, attachment_ids: State.uploadedA.map(f => f.id) },
      side_b: { label: labelB, url: urlB, attachment_ids: State.uploadedB.map(f => f.id) },
    };
  } else {
    const url = document.getElementById('ns_url').value.trim();
    if (!url && !State.uploadedFiles.length) {
      toast('URL 또는 파일 중 하나는 필요해요', 'error');
      btn.disabled = false; btn.textContent = '분석 시작';
      return;
    }
    payload = {
      query, url, mode: 'single',
      personas: chosenPersonas,
      attachment_ids: State.uploadedFiles.map(f => f.id),
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
    toast('분석 완료 · 자동 진행을 누르세요');
  } catch (e) {
    toast('실패: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = '분석 시작';
  }
}

