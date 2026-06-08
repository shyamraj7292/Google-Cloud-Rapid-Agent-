/**
 * Copa Agent ⚽ — Main Application JavaScript
 * Handles chat, pipelines, venues, quick actions, and API communication.
 */

// ============================================================
//  CONFIG
// ============================================================
const CONFIG = {
  API_BASE: '/api',
  TYPING_DELAY: 800,
  ACTION_STAGGER: 400,
};

// ============================================================
//  STATE
// ============================================================
const state = {
  sessionId: null,
  isWaiting: false,
  messages: [],
  actions: [],
};

// ============================================================
//  DATA
// ============================================================
const PROJECTS = [
  {
    name: 'worldcup-fan-app',
    desc: 'React PWA — schedules, scores, venue maps',
    pipelineId: '#78',
    status: 'success',
    branch: 'main',
    updated: '2 min ago',
  },
  {
    name: 'worldcup-ticketing-api',
    desc: 'Python FastAPI ticketing microservice',
    pipelineId: '#43',
    status: 'failed',
    branch: 'main',
    updated: '15 min ago',
  },
  {
    name: 'worldcup-stadium-dashboard',
    desc: 'Real-time stadium ops dashboard',
    pipelineId: '#31',
    status: 'running',
    branch: 'main',
    updated: 'Just now',
  },
];

const VENUES = [
  { name: 'MetLife Stadium',            city: 'East Rutherford, NJ', country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'AT&T Stadium',              city: 'Arlington, TX',       country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'SoFi Stadium',              city: 'Inglewood, CA',       country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'Hard Rock Stadium',         city: 'Miami Gardens, FL',   country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'Lumen Field',               city: 'Seattle, WA',         country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'Gillette Stadium',          city: 'Foxborough, MA',      country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'Lincoln Financial Field',   city: 'Philadelphia, PA',    country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'Mercedes-Benz Stadium',     city: 'Atlanta, GA',         country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'NRG Stadium',               city: 'Houston, TX',         country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'Arrowhead Stadium',         city: 'Kansas City, MO',     country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: "Levi's Stadium",            city: 'Santa Clara, CA',     country: 'USA',    flag: '🇺🇸', status: 'deployed' },
  { name: 'BMO Field',                 city: 'Toronto, ON',         country: 'Canada', flag: '🇨🇦', status: 'staging' },
  { name: 'BC Place',                  city: 'Vancouver, BC',       country: 'Canada', flag: '🇨🇦', status: 'deployed' },
  { name: 'Estadio Azteca',            city: 'Mexico City',         country: 'Mexico', flag: '🇲🇽', status: 'deployed' },
  { name: 'Estadio BBVA',              city: 'Monterrey',           country: 'Mexico', flag: '🇲🇽', status: 'staging' },
  { name: 'Estadio Akron',             city: 'Guadalajara',         country: 'Mexico', flag: '🇲🇽', status: 'deployed' },
];

const QUICK_ACTION_MESSAGES = {
  triage: 'The ticketing API pipeline is failing. Can you investigate the root cause and propose a fix?',
  deploy: 'Deploy all services for MetLife Stadium — there\'s a match tonight. Follow match day protocol.',
  status: 'Show me the overall pipeline health and status across all World Cup repos.',
  sprint: 'Generate a sprint summary report — include open issues, velocity, and merge request stats.',
};

// ============================================================
//  DOM REFERENCES
// ============================================================
const DOM = {};

function cacheDom() {
  DOM.chatMessages = document.getElementById('chat-messages');
  DOM.chatInput = document.getElementById('chat-input');
  DOM.btnSend = document.getElementById('btn-send');
  DOM.btnClearChat = document.getElementById('btn-clear-chat');
  DOM.btnRefresh = document.getElementById('btn-refresh');
  DOM.pipelineGrid = document.getElementById('pipeline-grid');
  DOM.actionsTimeline = document.getElementById('actions-timeline');
  DOM.venueGrid = document.getElementById('venue-grid');
  DOM.actionFeed = document.getElementById('action-feed');
  DOM.actionFeedItems = document.getElementById('action-feed-items');
  DOM.healthPct = document.getElementById('health-pct');
  DOM.platformStatus = document.getElementById('platform-status');
}

// ============================================================
//  INITIALIZATION
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  cacheDom();
  renderPipelines();
  renderVenues();
  bindEvents();
  loadEngineMode();

  // Initialize Lucide icons
  if (window.lucide) {
    lucide.createIcons();
  }
});

function bindEvents() {
  // Send message
  DOM.btnSend.addEventListener('click', handleSend);
  DOM.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Auto-resize textarea
  DOM.chatInput.addEventListener('input', () => {
    DOM.chatInput.style.height = 'auto';
    DOM.chatInput.style.height = Math.min(DOM.chatInput.scrollHeight, 120) + 'px';
  });

  // Clear chat
  DOM.btnClearChat.addEventListener('click', clearChat);

  // Refresh
  DOM.btnRefresh.addEventListener('click', () => {
    renderPipelines();
    renderVenues();
    if (window.lucide) lucide.createIcons();
  });

  // Quick actions
  document.querySelectorAll('.quick-action-btn[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      const message = QUICK_ACTION_MESSAGES[action];
      if (message) {
        DOM.chatInput.value = message;
        handleSend();
      }
    });
  });
}

// ============================================================
//  ENGINE MODE BADGE
// ============================================================
async function loadEngineMode() {
  const badge = document.getElementById('engine-badge');
  if (!badge) return;
  try {
    const res = await fetch(`${CONFIG.API_BASE}/agent/mode`);
    if (!res.ok) throw new Error();
    const m = await res.json();
    const live = m.gitlab_mode === 'live';
    const backend = { vertex: 'Vertex AI', gemini: 'Gemini', scripted: 'Demo Engine' }[m.agent_backend] || m.agent_backend;
    badge.textContent = `● ${backend} · GitLab ${live ? 'LIVE' : 'sim'}`;
    badge.classList.toggle('engine-badge--live', live);
    badge.title = `Agent: ${m.agent_backend} (${m.model}) · GitLab: ${m.gitlab_mode}`;
  } catch {
    badge.textContent = '● Demo Engine';
  }
}

// ============================================================
//  CHAT LOGIC
// ============================================================
async function handleSend() {
  const message = DOM.chatInput.value.trim();
  if (!message || state.isWaiting) return;

  // Clear input
  DOM.chatInput.value = '';
  DOM.chatInput.style.height = 'auto';

  // Add user message
  addChatMessage('user', message);

  // Show typing
  state.isWaiting = true;
  DOM.btnSend.disabled = true;
  const typingEl = showTypingIndicator();

  try {
    await streamFromAgent(message, typingEl);
  } catch (err) {
    removeElement(typingEl);
    addChatMessage('agent', `⚠️ Live agent unreachable (${err.message}). Showing demo flow.`);
    // Client-side fallback so the UI is never dead.
    const demoResponse = generateDemoResponse(message);
    showActionFeed(true);
    for (const action of demoResponse.actions) {
      addActionFeedItem(action);
      addTimelineItem(action);
      await sleep(CONFIG.ACTION_STAGGER);
    }
    addChatMessage('agent', demoResponse.reply); // already HTML
  }

  state.isWaiting = false;
  DOM.btnSend.disabled = false;
  DOM.chatInput.focus();
}

/**
 * Stream the agent's reason→act→observe loop via Server-Sent Events.
 * Renders each status line and tool action live as the agent works.
 */
async function streamFromAgent(message, typingEl) {
  const res = await fetch(`${CONFIG.API_BASE}/agent/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: state.sessionId }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let gotReply = false;
  let actionShown = false;

  const setThinking = (text) => {
    const t = typingEl.querySelector('.typing-thought');
    if (t) { t.textContent = text; }
    else {
      const tt = document.createElement('div');
      tt.className = 'typing-thought';
      tt.textContent = text;
      typingEl.querySelector('.message-content')?.appendChild(tt);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!raw.startsWith('data:')) continue;
      let ev;
      try { ev = JSON.parse(raw.slice(5).trim()); } catch { continue; }

      if (ev.type === 'session') {
        state.sessionId = ev.session_id;
      } else if (ev.type === 'status') {
        setThinking(ev.text);
      } else if (ev.type === 'action') {
        if (!actionShown) { showActionFeed(true); actionShown = true; }
        const a = { tool_name: ev.tool, description: ev.description, timestamp: ev.timestamp, status: ev.status };
        addActionFeedItem(a);
        addTimelineItem(a);
      } else if (ev.type === 'reply') {
        removeElement(typingEl);
        addChatMessage('agent', renderMarkdown(ev.reply));
        gotReply = true;
      }
    }
  }
  if (!gotReply) { removeElement(typingEl); }
}

/** Minimal, safe Markdown → HTML for agent replies (bold, code, links, tables, lists). */
function renderMarkdown(md) {
  if (!md) return '';
  // Escape first, then re-introduce a controlled set of tags.
  let h = escapeHtml(md);
  // Tables (| a | b | rows)
  h = h.replace(/(^\|.*\|$\n?)+/gm, (block) => {
    const rows = block.trim().split('\n').filter((r) => !/^\|[\s|:-]+\|$/.test(r));
    const cells = rows.map((r) => r.split('|').slice(1, -1).map((c) => c.trim()));
    if (!cells.length) return block;
    const head = `<tr>${cells[0].map((c) => `<th>${c}</th>`).join('')}</tr>`;
    const body = cells.slice(1).map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('');
    return `<table>${head}${body}</table>`;
  });
  h = h
    .replace(/\[([^\]]+)\]\((https?:[^)]+|#)\)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^### (.*)$/gm, '<h4>$1</h4>')
    .replace(/^\d+\.\s+(.*)$/gm, '<div class="md-li">• $1</div>')
    .replace(/^[-*]\s+(.*)$/gm, '<div class="md-li">• $1</div>')
    .replace(/\n/g, '<br>');
  return h;
}

// ============================================================
//  DEMO RESPONSE GENERATOR  (client-side fallback)
// ============================================================
function generateDemoResponse(message) {
  const msg = message.toLowerCase();
  const ts = new Date().toISOString();

  if (/pipeline|fail|broken|error|triage|investigat/.test(msg)) {
    return {
      reply: `🔍 <strong>Pipeline Triage Complete!</strong><br><br>
I investigated the failing pipeline and found the root cause:<br><br>
<strong>Pipeline</strong>: #43 in <code>worldcup-ticketing-api</code><br>
<strong>Failing Job</strong>: <code>unit_test</code><br>
<strong>Root Cause</strong>: <code>AssertionError</code> in <code>test_auth_token_validation</code> — the JWT expiry constant was changed from <code>3600</code> to <code>360</code> (typo in <code>config/auth.py</code>).<br><br>
<strong>Proposed Fix</strong>: Change <code>TOKEN_EXPIRY = 360</code> back to <code>TOKEN_EXPIRY = 3600</code>.<br><br>
Would you like me to create a branch and merge request with this fix? ⚽`,
      actions: [
        { tool_name: 'list_pipelines', description: 'Listed pipelines for worldcup-ticketing-api', timestamp: ts, status: 'completed' },
        { tool_name: 'list_pipeline_jobs', description: 'Found failing job: unit_test in pipeline #43', timestamp: ts, status: 'completed' },
        { tool_name: 'get_pipeline_job_log', description: 'Read job logs — found AssertionError in test_auth', timestamp: ts, status: 'completed' },
      ],
      session_id: state.sessionId || 'demo-session',
    };
  }

  if (/deploy|release|match\s*day|stadium/.test(msg)) {
    return {
      reply: `🏟️ <strong>Match Day Protocol Activated!</strong><br><br>
All services verified and deployed:<br><br>
<table>
<tr><th>Service</th><th>Pipeline</th><th>Status</th><th>Version</th></tr>
<tr><td><code>worldcup-fan-app</code></td><td>#78</td><td>✅ Deployed</td><td>v2.4.1</td></tr>
<tr><td><code>worldcup-ticketing-api</code></td><td>#43</td><td>✅ Deployed</td><td>v1.8.3</td></tr>
<tr><td><code>worldcup-stadium-dashboard</code></td><td>#31</td><td>✅ Deployed</td><td>v1.2.0</td></tr>
</table><br>
⚽ All systems GO for match day! Deployment freeze is now active.`,
      actions: [
        { tool_name: 'list_pipelines', description: 'Checked all 3 repo pipelines — 2 green, 1 running', timestamp: ts, status: 'completed' },
        { tool_name: 'list_pipelines', description: 'Waited for stadium-dashboard pipeline — now green', timestamp: ts, status: 'completed' },
        { tool_name: 'create_branch', description: 'Created release tags v2.4.1, v1.8.3, v1.2.0', timestamp: ts, status: 'completed' },
        { tool_name: 'trigger_pipeline', description: 'Triggered deploy pipelines for all 3 services', timestamp: ts, status: 'completed' },
      ],
      session_id: state.sessionId || 'demo-session',
    };
  }

  if (/issue|create|feature|spanish|add|i18n/.test(msg)) {
    return {
      reply: `✅ <strong>Issue → MR Pipeline Complete!</strong><br><br>
Here's what I set up:<br><br>
📋 <strong>Issue #23</strong>: Add Spanish language support to fan-app<br>
🌿 <strong>Branch</strong>: <code>feature/spanish-i18n</code><br>
📝 <strong>MR #18</strong>: Initial i18n setup with Spanish translations<br><br>
The MR includes <code>es.json</code>, <code>en.json</code>, and language detection setup. Pipeline is running on the feature branch now! ⚽`,
      actions: [
        { tool_name: 'create_issue', description: 'Created issue #23: Add Spanish language support', timestamp: ts, status: 'completed' },
        { tool_name: 'create_branch', description: 'Created branch feature/spanish-i18n', timestamp: ts, status: 'completed' },
        { tool_name: 'create_or_update_file', description: 'Added src/i18n/es.json with Spanish translations', timestamp: ts, status: 'completed' },
        { tool_name: 'create_merge_request', description: 'Opened MR #18: Initial i18n setup', timestamp: ts, status: 'completed' },
      ],
      session_id: state.sessionId || 'demo-session',
    };
  }

  if (/status|health|overview|sprint|report/.test(msg)) {
    return {
      reply: `📊 <strong>World Cup Platform Health Report</strong><br><br>
<table>
<tr><th>Repo</th><th>Pipeline</th><th>Status</th><th>Last Updated</th></tr>
<tr><td><code>worldcup-fan-app</code></td><td>#78</td><td>✅ Passed</td><td>2 min ago</td></tr>
<tr><td><code>worldcup-ticketing-api</code></td><td>#43</td><td>❌ Failed</td><td>15 min ago</td></tr>
<tr><td><code>worldcup-stadium-dashboard</code></td><td>#31</td><td>🔄 Running</td><td>Just now</td></tr>
</table><br>
<strong>Summary</strong>: 1 of 3 services has a failing pipeline. Would you like me to investigate the ticketing API failure? ⚽`,
      actions: [
        { tool_name: 'list_projects', description: 'Listed all World Cup projects', timestamp: ts, status: 'completed' },
        { tool_name: 'list_pipelines', description: 'Aggregated pipeline status across all repos', timestamp: ts, status: 'completed' },
      ],
      session_id: state.sessionId || 'demo-session',
    };
  }

  // Default greeting
  return {
    reply: `⚽ Hey! I'm <strong>Copa Agent</strong>, your AI DevOps Commander for World Cup 2026!<br><br>
Here's what I can help with:<br><br>
🔍 <strong>Triage pipeline failures</strong> — "The ticketing API pipeline is failing"<br>
🚀 <strong>Deploy services</strong> — "Deploy all services for MetLife Stadium"<br>
📋 <strong>Create issues & MRs</strong> — "Create an issue for Spanish language support"<br>
📊 <strong>Check platform health</strong> — "Show me the pipeline status"<br>
🏟️ <strong>Match day operations</strong> — "Activate match day protocol"<br><br>
What can I do for you today?`,
    actions: [],
    session_id: state.sessionId || 'demo-session',
  };
}

// ============================================================
//  CHAT UI HELPERS
// ============================================================
function addChatMessage(role, html) {
  const isUser = role === 'user';
  const msg = document.createElement('div');
  msg.className = `chat-message chat-message--${isUser ? 'user' : 'agent'}`;
  msg.innerHTML = `
    <div class="message-avatar">${isUser ? '👤' : '⚽'}</div>
    <div class="message-content">
      <div class="message-sender">${isUser ? 'You' : 'Copa Agent'}</div>
      <div class="message-text">${isUser ? escapeHtml(html) : html}</div>
    </div>
  `;
  DOM.chatMessages.appendChild(msg);
  DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
  state.messages.push({ role, content: html });
}

function showTypingIndicator() {
  const el = document.createElement('div');
  el.className = 'chat-message chat-message--agent';
  el.id = 'typing-indicator';
  el.innerHTML = `
    <div class="message-avatar">⚽</div>
    <div class="message-content">
      <div class="message-sender">Copa Agent</div>
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  DOM.chatMessages.appendChild(el);
  DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
  return el;
}

function clearChat() {
  // Keep only the welcome message
  const welcome = DOM.chatMessages.querySelector('.chat-message--agent');
  DOM.chatMessages.innerHTML = '';
  if (welcome) DOM.chatMessages.appendChild(welcome);
  state.messages = [];
  state.sessionId = null;
  showActionFeed(false);
  if (DOM.actionFeedItems) DOM.actionFeedItems.innerHTML = '';
  // Reset timeline
  DOM.actionsTimeline.innerHTML = `
    <div class="timeline-empty">
      <i data-lucide="bot" class="icon-lg"></i>
      <p>No actions yet. Ask Copa Agent to do something!</p>
    </div>
  `;
  if (window.lucide) lucide.createIcons();
}

// ============================================================
//  ACTION FEED (in chat panel)
// ============================================================
function showActionFeed(show) {
  if (DOM.actionFeed) {
    DOM.actionFeed.classList.toggle('hidden', !show);
  }
}

function addActionFeedItem(action) {
  if (!DOM.actionFeedItems) return;
  const el = document.createElement('div');
  el.className = 'action-feed-item';
  el.innerHTML = `
    <span>⚡</span>
    <span class="action-tool">${action.tool_name}</span>
    <span>— ${action.description}</span>
  `;
  DOM.actionFeedItems.appendChild(el);
  DOM.actionFeedItems.scrollTop = DOM.actionFeedItems.scrollHeight;
}

// ============================================================
//  ACTIONS TIMELINE (dashboard panel)
// ============================================================
function addTimelineItem(action) {
  // Remove the "empty" placeholder
  const empty = DOM.actionsTimeline.querySelector('.timeline-empty');
  if (empty) empty.remove();

  const time = new Date(action.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const el = document.createElement('div');
  el.className = 'timeline-item';
  el.innerHTML = `
    <span class="timeline-time">${time}</span>
    <div class="timeline-icon">⚡</div>
    <div class="timeline-text">
      <strong>${action.tool_name}</strong> — ${action.description}
    </div>
  `;
  // Prepend so newest appears at top
  DOM.actionsTimeline.prepend(el);
  state.actions.push(action);
}

// ============================================================
//  PIPELINE RENDERER
// ============================================================
function renderPipelines() {
  if (!DOM.pipelineGrid) return;
  DOM.pipelineGrid.innerHTML = PROJECTS.map((p) => {
    const statusIcon = p.status === 'success' ? '✅' : p.status === 'failed' ? '❌' : '🔄';
    const statusLabel = p.status === 'success' ? 'Passed' : p.status === 'failed' ? 'Failed' : 'Running';
    return `
      <div class="pipeline-card pipeline-card--${p.status}" title="${p.name}">
        <div class="pipeline-card-header">
          <span class="pipeline-card-name">${p.name}</span>
          <span class="pipeline-card-status-dot"></span>
        </div>
        <div class="pipeline-card-desc">${p.desc}</div>
        <div class="pipeline-card-footer">
          <span class="pipeline-card-id">${p.pipelineId} · ${p.branch}</span>
          <span class="pipeline-card-status-label">${statusIcon} ${statusLabel}</span>
        </div>
      </div>
    `;
  }).join('');

  // Update platform health
  const passed = PROJECTS.filter((p) => p.status === 'success').length;
  const pct = Math.round((passed / PROJECTS.length) * 100);
  if (DOM.healthPct) DOM.healthPct.textContent = `${pct}%`;

  // Update status dot color
  if (DOM.platformStatus) {
    const dot = DOM.platformStatus.querySelector('.status-dot');
    if (dot) {
      dot.className = 'status-dot';
      if (pct >= 80) dot.classList.add('status-dot--healthy');
      else if (pct >= 50) dot.classList.add('status-dot--warning');
      else dot.classList.add('status-dot--critical');
    }
  }
}

// ============================================================
//  VENUE RENDERER
// ============================================================
function renderVenues() {
  if (!DOM.venueGrid) return;
  DOM.venueGrid.innerHTML = VENUES.map((v) => `
    <div class="venue-card" title="${v.name}, ${v.city}">
      <span class="venue-status-dot venue-status-dot--${v.status}"></span>
      <div class="venue-info">
        <div class="venue-name">${v.name}</div>
        <div class="venue-city">${v.city}</div>
      </div>
      <span class="venue-flag">${v.flag}</span>
    </div>
  `).join('');
}

// ============================================================
//  UTILITIES
// ============================================================
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function removeElement(el) {
  if (el && el.parentNode) el.parentNode.removeChild(el);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
