// =========================================
// Init
// =========================================
window.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  await loadPersonas();
  await loadSessions();
  await seedDefaultsIfEmpty();
  renderSidebar();
  renderWelcome();
});

async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    State.config = await r.json();
  } catch (e) {
    toast('설정 로드 실패', 'error');
  }
}

async function loadPersonas() {
  try {
    const r = await fetch('/api/personas');
    const d = await r.json();
    State.personas = d.personas || [];
  } catch (e) { console.error(e); }
}

async function loadSessions() {
  try {
    const r = await fetch('/api/sessions');
    const d = await r.json();
    State.sessions = d.sessions || [];
  } catch (e) { console.error(e); }
}

async function seedDefaultsIfEmpty() {
  if (State.personas.length === 0) {
    try {
      const r = await fetch('/api/personas/seed_defaults', { method: 'POST' });
      const d = await r.json();
      if (d.personas) State.personas = d.personas;
    } catch (e) { console.error(e); }
  }
}

