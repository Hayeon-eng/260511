// =========================================
// 꼬리질문
// =========================================
function setAskInput(text) {
  const input = document.getElementById('ask_input');
  if (input) {
    input.value = text;
    input.focus();
  }
}

async function sendFollowup() {
  const s = State.currentSession;
  if (!s) return;
  const input = document.getElementById('ask_input');
  const target = document.getElementById('ask_target');
  if (!input || !input.value.trim()) {
    toast('질문을 입력하세요', 'error');
    return;
  }
  const question = input.value.trim();
  const personaName = target ? target.value : '';
  const personasFilter = personaName ? [personaName] : null;

  const sendBtn = document.querySelector('.ask-send');
  if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = '응답 생성 중…'; }
  input.value = '';

  // Thinking 표시 (대상 페르소나들)
  const targets = personasFilter
    ? (s.personas || []).filter(p => personasFilter.includes(p.name))
    : (s.personas || []);
  if (targets.length) appendThinking(targets[0]);

  try {
    const r = await fetch(`/api/sessions/${s.id}/ask`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ question, persona_names: personasFilter }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '꼬리질문 실패');

    removeThinking();
    (d.answers || []).forEach(turn => {
      s.turns = [...(s.turns || []), turn];
      appendTurnCard(turn);
    });
    toast('답변 완료');
  } catch (e) {
    removeThinking();
    toast('실패: ' + e.message, 'error');
  } finally {
    if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = '↗ 보내기'; }
  }
}

