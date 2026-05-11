// =========================================
// State
// =========================================
const State = {
  config: null,
  personas: [],
  sessions: [],
  currentSessionId: null,
  currentSession: null,
  autoRun: false,
  turnIndex: 0,
  uploadedFiles: [],
  selectedPersonas: [],  // for new session modal
};

const AXES = ["데이터", "콘텐츠", "AI Commerce", "UX"];
const AXIS_EMOJI = { "데이터": "📊", "콘텐츠": "✍️", "AI Commerce": "🛍️", "UX": "🎨" };

