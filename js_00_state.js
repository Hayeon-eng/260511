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

const BRAND_AXIS = "브랜드 메시지 적합도";
const AXES = ["데이터", "콘텐츠", "AI Commerce", "UX", BRAND_AXIS];
const AXIS_EMOJI = { "데이터": "📊", "콘텐츠": "✍️", "AI Commerce": "🛍️", "UX": "🎨", [BRAND_AXIS]: "🎯" };

