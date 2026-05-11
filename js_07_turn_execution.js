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
  // 직전 발언과 라운드 다르면 구분선
  const s = State.currentSession;
  const turns = s ? (s.turns || []) : [];
  // appendTurnCard 호출 시점에서 t는 이미 turns에 추가된 상태
  const idx = turns.findIndex(x => x.id === t.id);
  const prev = idx > 0 ? turns[idx-1] : null;
  const showRoundDivider = !prev || (t.round !== prev.round);
  feed.insertAdjacentHTML('beforeend', renderTurnCard(t, { showRoundDivider }));
  // 카운트 갱신
  const cnt = document.getElementById('turns_count');
  if (cnt) cnt.textContent = turns.length;
  feed.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

const THINKING_MESSAGES = {
  'DataNerd': ['JSON-LD 스키마 살펴보는 중', '구조화 데이터 점검 중', '메타 태그 들여다보는 중'],
  'SchemaSurgeon': ['스키마 결손 진단 중', 'Schema.org 구조 분석 중', '기술 SEO 처방 작성 중'],
  '감성젠지': ['카피 ㄹㅇ인지 보는 중', '갬성 분석 중', '첫 1초 이탈 포인트 보는 중'],
  '카피노예': ['헤드라인 해부 중', '메시지 위계 분석 중', '답변형 문장 검토 중'],
  'AICommerceHacker': ['AI 추천 노출 가능성 추적 중', 'Product 스키마 점검 중', 'Merchant Center 친화도 보는 중'],
  'PriceComparer': ['가격·리뷰 노출 확인 중', '비교 데이터 찾는 중', '구매 결정 정보 점검 중'],
  'UXResearcher': ['스캐닝 패턴 관찰 중', '정보 구조 분석 중', '모바일 가독성 보는 중'],
  'SkepticalShopper': ['신뢰 시그널 확인 중', '첫인상 평가 중', '의사결정 마찰 보는 중'],
};
function thinkingMessageFor(name) {
  const arr = THINKING_MESSAGES[name];
  if (arr && arr.length) return arr[Math.floor(Math.random() * arr.length)];
  return `${name}가 분석 중`;
}

function appendThinking(persona) {
  const feed = document.getElementById('discussion_feed');
  if (!feed) return;
  removeThinking();
  const msg = thinkingMessageFor(persona.name);
  feed.insertAdjacentHTML('beforeend', `
    <div class="thinking-card" id="thinking_now">
      <div class="turn-avatar-v2" style="background:${persona.color}1A; color:${persona.color}; border:2px solid ${persona.color}33; width:36px; height:36px; font-size:16px">${escapeHTML(persona.emoji || '💬')}</div>
      <div style="flex:1">
        <div style="font-weight:700; font-size:14px">${escapeHTML(persona.name)}</div>
        <div style="font-size:12.5px; color:var(--text-secondary)">${escapeHTML(msg)}…</div>
      </div>
      <div class="thinking-dots"><span></span><span></span><span></span></div>
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

function toggleExportMenu(ev) {
  ev.stopPropagation();
  const menu = document.getElementById('export_menu');
  if (menu) menu.classList.toggle('open');
  // 바깥 클릭 시 닫기
  setTimeout(() => {
    const close = (e) => {
      if (menu && !menu.contains(e.target)) {
        menu.classList.remove('open');
        document.removeEventListener('click', close);
      }
    };
    document.addEventListener('click', close);
  }, 50);
}

async function exportSession(format) {
  const s = State.currentSession;
  if (!s) return;
  format = format || 'md';
  const path = format === 'md' ? `/api/sessions/${s.id}/export`
              : `/api/sessions/${s.id}/export/${format}`;
  window.open(path, '_blank');
  // 메뉴 닫기
  const menu = document.getElementById('export_menu');
  if (menu) menu.classList.remove('open');
}

