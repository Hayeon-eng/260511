// =========================================
// Welcome Screen
// =========================================
function renderWelcome() {
  document.getElementById('main_inner').innerHTML = `
    <div class="welcome">
      <h1>AI 토론으로 콘텐츠를 진단하세요</h1>
      <p>여러 페르소나가 동시에 같은 콘텐츠를 보고 데이터·콘텐츠·AI Commerce·UX·브랜드 메시지 적합도 5개 축으로 분석합니다. AI Agent가 이 페이지를 인용·추천할지가 핵심 질문입니다.</p>
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
          <p>기본 제공되는 분석가를 살펴보세요</p>
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

