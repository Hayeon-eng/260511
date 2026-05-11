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
