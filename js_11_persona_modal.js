// =========================================
// Persona Modal (Create / Edit / Delete)
// =========================================
const COLORS = ['#0A84FF', '#5856D6', '#BF5AF2', '#FF375F', '#FF3B30', '#FF9500', '#FFCC00', '#30D158', '#5AC8FA', '#00C7BE'];
const EMOJIS = ['💬','📊','✍️','🛍️','🎨','🩺','💫','🤨','🔎','🧠','🚀','💎','⚡','🎯','🔥','🌟'];

function openPersonaModal(pid) {
  const editing = pid ? State.personas.find(p => p.id === pid) : null;
  renderPersonaModal(editing);
}

function renderPersonaModal(editing) {
  const p = editing || { name:'', description:'', personality:'', expertise:'',
                        focus_dimensions:[], color:COLORS[0], emoji:EMOJIS[0] };
  const isEdit = !!editing;

  document.getElementById('modal_root').innerHTML = `
    <div class="modal-overlay" onclick="if(event.target===this) closeModal()">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">${isEdit ? '페르소나 편집' : '새 페르소나 만들기'}</div>
          <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
        <div class="modal-body">
          ${!isEdit ? `
            <div class="persona-guide-box">
              <div class="persona-guide-title">💡 좋은 페르소나의 조건</div>
              <div class="persona-guide-text">실제 사람처럼 <strong>구체적인 정체성</strong>을 부여할수록 토론에서 날카로운 인사이트가 나옵니다. 단순히 "디자이너" 같은 직무가 아니라, <strong>관심사·습관·말투·취향·약점</strong>까지 정의하세요.</div>
              <div class="persona-guide-example">
                <strong>예시:</strong> "30대 자취 직장인, 출근길 인스타에서 광고 본 제품을 AI Agent에 물어보고 결정. 가성비에 민감하지만 디자인 떨어지면 안 산다. 까칠하고 의심 많음."
              </div>
            </div>
          ` : ''}

          <div class="field">
            <label>닉네임 *</label>
            <input class="input" id="pf_name" value="${escapeAttr(p.name)}" placeholder="예: 감성젠지 / DataNerd / 자취직장러 / OldFashioned아재">
            <div class="hint">실명보다 캐릭터·정체성이 드러나는 닉네임을 추천합니다. 별명·세대·태도·직업이 섞인 것이 좋아요.</div>
          </div>

          <div class="field">
            <label>설명 (정체성)</label>
            <textarea class="textarea" id="pf_desc" placeholder="이 페르소나가 어떤 사람인지 — 나이대·생활 패턴·소비 습관·관심사를 구체적으로.
예) 27세 N년차 디지털 마케터. 출근길 뉴스레터·트위터로 트렌드 흡수. 새 가전 살 때 무조건 유튜브 리뷰 3개 이상 본 다음 산다.">${escapeAttr(p.description)}</textarea>
            <div class="hint">💡 나이·직업·라이프스타일·정보 수집 습관·구매 패턴까지 적으면 더 풍부한 의견이 나옵니다.</div>
          </div>

          <div class="field">
            <label>성격 · 말투</label>
            <textarea class="textarea" id="pf_pers" placeholder="어떤 톤·태도로 발언할지.
예) 직설적이고 의심 많음. '근데', '솔직히' 자주 씀. 광고 같은 카피는 즉시 의심.">${escapeAttr(p.personality)}</textarea>
            <div class="hint">💡 자주 쓰는 표현·말버릇·반응 스타일을 적으면 페르소나 톤이 일관되게 유지됩니다.</div>
          </div>

          <div class="field">
            <label>전문 분야 · 관심사</label>
            <textarea class="textarea" id="pf_exp" placeholder="이 페르소나가 깊이 아는 영역, 평소 관심 두는 주제.
예) UX 라이팅, 모바일 첫인상, 1초 안에 의사결정 끝내는 사용자 패턴">${escapeAttr(p.expertise)}</textarea>
            <div class="hint">💡 evidence를 짚을 때 이 분야를 우선 본다는 신호가 됩니다.</div>
          </div>

          <div class="field">
            <label>주력 분석 축 (여러 개 선택 가능)</label>
            <div class="dim-toggle-row" id="pf_dims">
              ${AXES.map(ax => `
                <div class="dim-toggle ${p.focus_dimensions.includes(ax) ? 'active' : ''}" data-axis="${escapeAttr(ax)}" onclick="toggleDim(this)">
                  ${AXIS_EMOJI[ax]} ${escapeHTML(ax)}
                </div>
              `).join('')}
            </div>
            <div class="hint">선택하지 않으면 모든 축에서 발언 가능합니다. 본인 정체성에 가까운 축을 1~2개 고르면 일관성이 좋아져요.</div>
          </div>
          <div class="field">
            <label>아바타 이모지</label>
            <div class="emoji-pick-row" id="pf_emojis">
              ${EMOJIS.map(e => `<div class="emoji-pick ${e===p.emoji?'active':''}" data-emoji="${e}" onclick="pickEmoji(this)">${e}</div>`).join('')}
            </div>
          </div>
          <div class="field">
            <label>컬러</label>
            <div class="color-row" id="pf_colors">
              ${COLORS.map(c => `<div class="color-pick ${c===p.color?'active':''}" data-color="${c}" style="background:${c}" onclick="pickColor(this)"></div>`).join('')}
            </div>
          </div>
        </div>
        <div class="modal-foot">
          ${isEdit ? `<button class="btn-danger" onclick="deletePersona('${p.id}')">삭제</button>` : ''}
          <button class="btn-secondary" onclick="closeModal()">취소</button>
          <button class="btn-primary" onclick="${isEdit ? `savePersona('${p.id}')` : 'savePersona()'}">${isEdit ? '저장' : '추가'}</button>
        </div>
      </div>
    </div>
  `;
}

function toggleDim(el) { el.classList.toggle('active'); }
function pickColor(el) {
  document.querySelectorAll('#pf_colors .color-pick').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}
function pickEmoji(el) {
  document.querySelectorAll('#pf_emojis .emoji-pick').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

async function savePersona(pid) {
  const name = document.getElementById('pf_name').value.trim();
  if (!name) { toast('닉네임은 필수예요', 'error'); return; }
  const data = {
    name,
    description: document.getElementById('pf_desc').value.trim(),
    personality: document.getElementById('pf_pers').value.trim(),
    expertise: document.getElementById('pf_exp').value.trim(),
    focus_dimensions: Array.from(document.querySelectorAll('#pf_dims .dim-toggle.active')).map(e => e.dataset.axis),
    color: document.querySelector('#pf_colors .color-pick.active')?.dataset.color || COLORS[0],
    emoji: document.querySelector('#pf_emojis .emoji-pick.active')?.dataset.emoji || EMOJIS[0],
  };
  try {
    if (pid) {
      await fetch(`/api/personas/${pid}`, { method: 'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data) });
      toast('수정 완료');
    } else {
      await fetch('/api/personas', { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data) });
      toast('추가 완료');
    }
    await loadPersonas();
    renderSidebar();
    closeModal();
  } catch (e) {
    toast('저장 실패', 'error');
  }
}

async function deletePersona(pid) {
  if (!confirm('이 페르소나를 삭제할까요?')) return;
  try {
    await fetch(`/api/personas/${pid}`, { method: 'DELETE' });
    await loadPersonas();
    renderSidebar();
    closeModal();
    toast('삭제됨');
  } catch (e) { toast('삭제 실패', 'error'); }
}

