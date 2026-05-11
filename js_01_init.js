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
  const defaults = (State.config && State.config.default_personas) || [];
  const currentNames = new Set((State.personas || []).map(p => p.name));
  const hasMissingDefault = defaults.some(p => !currentNames.has(p.name));
  if (State.personas.length === 0 || hasMissingDefault) {
    try {
      const r = await fetch('/api/personas/seed_defaults', { method: 'POST' });
      const d = await r.json();
      if (d.personas) State.personas = d.personas;
    } catch (e) { console.error(e); }
  }
}

