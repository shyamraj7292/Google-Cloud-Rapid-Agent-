/**
 * Copa Agent ⚽ — Main Application JS
 * World Cup 2026 DevOps Command Center
 * Gemini 2.0 · Google Cloud Agent Builder · GitLab MCP
 */

// ── Config ──────────────────────────────────────────────────
const CONFIG = {
  API_BASE: '/api',
  KICKOFF: new Date('2026-06-11T20:00:00Z'), // Estadio Azteca opening match UTC
};

// ── State ───────────────────────────────────────────────────
const state = {
  sessionId: null,
  isWaiting: false,
  messages: [],
  actions: [],
  autoFixedCount: 0,
  guardianActive: false,
  liveProjects: [],       // filled from /api/dashboard/projects
};

// ── World Cup 2026 venues (names/cities are real; deployment status is
// derived live from real pipeline health, not hardcoded) ─────
const VENUES = [
  { name:'MetLife Stadium',         city:'East Rutherford, NJ', flag:'🇺🇸' },
  { name:'AT&T Stadium',            city:'Arlington, TX',       flag:'🇺🇸' },
  { name:'SoFi Stadium',            city:'Inglewood, CA',       flag:'🇺🇸' },
  { name:'Hard Rock Stadium',       city:'Miami Gardens, FL',   flag:'🇺🇸' },
  { name:'Lumen Field',             city:'Seattle, WA',         flag:'🇺🇸' },
  { name:'Gillette Stadium',        city:'Foxborough, MA',      flag:'🇺🇸' },
  { name:'Lincoln Financial Field', city:'Philadelphia, PA',    flag:'🇺🇸' },
  { name:'Mercedes-Benz Stadium',   city:'Atlanta, GA',         flag:'🇺🇸' },
  { name:'NRG Stadium',             city:'Houston, TX',         flag:'🇺🇸' },
  { name:'Arrowhead Stadium',       city:'Kansas City, MO',     flag:'🇺🇸' },
  { name:"Levi's Stadium",          city:'Santa Clara, CA',     flag:'🇺🇸' },
  { name:'BMO Field',               city:'Toronto, ON',         flag:'🇨🇦' },
  { name:'BC Place',                city:'Vancouver, BC',       flag:'🇨🇦' },
  { name:'Estadio Azteca',          city:'Mexico City',         flag:'🇲🇽' },
  { name:'Estadio BBVA',            city:'Monterrey',           flag:'🇲🇽' },
  { name:'Estadio Akron',           city:'Guadalajara',         flag:'🇲🇽' },
];

const QUICK_MSGS = {
  triage: 'The ticketing API pipeline is failing — investigate the root cause, fix the code, and open a merge request.',
  deploy: 'Deploy all services for MetLife Stadium — there\'s a match tonight. Follow the match day protocol.',
  status: 'Show me the overall pipeline health and status across all World Cup repos.',
  sprint: 'Generate a sprint summary: open issues, velocity, and merge request stats.',
  surge: 'Kickoff is starting at MetLife Stadium and fans are flooding in — check traffic, and scale up if there\'s a surge.',
};

const TOOL_ICONS = {
  list_pipelines: '🔍', list_pipeline_jobs: '📋', get_pipeline_job_log: '📄',
  get_file_contents: '📂', create_branch: '🌿', create_or_update_file: '✏️',
  create_merge_request: '🔀', create_issue: '📌', run_pipeline: '🚀',
  get_platform_status: '📡', search_runbooks: '📖',
  write_runbook_entry: '🧠', create_postmortem: '📄',
  get_stadium_traffic: '📈', scale_service: '⚙️',
};

// ── DOM cache ───────────────────────────────────────────────
const DOM = {};
function cacheDom() {
  DOM.chatMessages    = document.getElementById('chat-messages');
  DOM.chatInput       = document.getElementById('chat-input');
  DOM.btnSend         = document.getElementById('btn-send');
  DOM.btnClearChat    = document.getElementById('btn-clear-chat');
  DOM.btnRefresh      = document.getElementById('btn-refresh');
  DOM.pipelineGrid    = document.getElementById('pipeline-grid');
  DOM.actionsTimeline = document.getElementById('actions-timeline');
  DOM.venueGrid       = document.getElementById('venue-grid');
  DOM.actionFeed      = document.getElementById('action-feed');
  DOM.actionFeedItems = document.getElementById('action-feed-items');
  DOM.healthPct       = document.getElementById('health-pct');
  DOM.platformStatus  = document.getElementById('platform-status');
  DOM.mcCountdown     = document.getElementById('mc-countdown');
  DOM.mcHealth        = document.getElementById('mc-health');
  DOM.mcFixed         = document.getElementById('mc-fixed');
  DOM.readinessBar    = document.getElementById('readiness-bar-fill');
  DOM.readinessLabel  = document.getElementById('readiness-label');
  DOM.pipelineCount   = document.getElementById('pipeline-count');
  DOM.actionsCount    = document.getElementById('actions-count');
  DOM.agentModeChip   = document.getElementById('agent-mode-chip');
  DOM.guardianSwitch  = document.getElementById('guardian-switch');
}

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  cacheDom();
  renderVenues();
  bindEvents();
  loadEngineMode();
  startCountdown();
  loadLivePipelines();          // try live GitLab data first
  if (window.lucide) lucide.createIcons();
});

// ── Event binding ────────────────────────────────────────────
function bindEvents() {
  DOM.btnSend.addEventListener('click', handleSend);
  DOM.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });
  DOM.chatInput.addEventListener('input', () => {
    DOM.chatInput.style.height = 'auto';
    DOM.chatInput.style.height = Math.min(DOM.chatInput.scrollHeight, 120) + 'px';
  });
  DOM.btnClearChat.addEventListener('click', clearChat);
  DOM.btnRefresh.addEventListener('click', () => { loadLivePipelines(); });
  document.querySelectorAll('.quick-action-btn[data-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const msg = QUICK_MSGS[btn.dataset.action];
      if (msg) { DOM.chatInput.value = msg; handleSend(); }
    });
  });
  // Auto-Guardian toggle
  const guardianToggle = document.getElementById('guardian-toggle');
  if (guardianToggle) {
    guardianToggle.addEventListener('click', () => {
      state.guardianActive = !state.guardianActive;
      DOM.guardianSwitch.classList.toggle('active', state.guardianActive);
      const label = guardianToggle.querySelector('.guardian-label');
      if (label) label.style.color = state.guardianActive ? '#00ff87' : '';
      if (state.guardianActive) {
        addChatMessage('agent', '🛡️ <strong>Auto-Guardian activated.</strong> I\'m now monitoring all pipelines. I\'ll alert you — and optionally auto-fix — any failures as they happen. The World Cup starts in 2 days; nothing is breaking on my watch. ⚽');
      }
    });
  }
}

// ── Engine Mode Badge ─────────────────────────────────────────
async function loadEngineMode() {
  const badge = document.getElementById('engine-badge');
  if (!badge) return;
  try {
    const res = await fetch(`${CONFIG.API_BASE}/agent/mode`);
    if (!res.ok) throw new Error();
    const m = await res.json();
    const isLive = m.gitlab_mode === 'live' || m.gitlab_mode === 'mcp+live';
    const isMcp  = m.gitlab_mode === 'mcp+live';
    const backendLabel = { vertex:'Vertex AI', gemini:'Gemini', scripted:'Demo' }[m.agent_backend] || m.agent_backend;
    const gitlabLabel  = isMcp ? 'MCP+LIVE' : (isLive ? 'LIVE' : 'sim');
    badge.textContent  = `● ${backendLabel} · GitLab ${gitlabLabel}`;
    badge.classList.toggle('engine-badge--live', isLive);
    badge.title = `Agent: ${m.agent_backend} (${m.model}) · GitLab: ${m.gitlab_mode}`;
    if (DOM.agentModeChip) {
      DOM.agentModeChip.textContent = m.agent_backend;
      DOM.agentModeChip.style.color = m.agent_backend === 'gemini' ? '#00ff87' : '#4dabf7';
    }
  } catch {
    badge.textContent = '● Demo Engine';
  }
}

// ── World Cup Countdown ───────────────────────────────────────
function startCountdown() {
  function tick() {
    const now  = new Date();
    const diff = CONFIG.KICKOFF - now;
    if (!DOM.mcCountdown) return;

    if (diff <= 0) {
      DOM.mcCountdown.textContent = '⚽ LIVE NOW!';
      const card = document.getElementById('mc-countdown-card');
      if (card) card.style.background = 'rgba(0,255,135,0.06)';
      return;
    }

    const days  = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    const mins  = Math.floor((diff % 3600000)  / 60000);
    const secs  = Math.floor((diff % 60000)    / 1000);

    if (days > 0) {
      DOM.mcCountdown.textContent = `${days}d ${String(hours).padStart(2,'0')}h ${String(mins).padStart(2,'0')}m`;
    } else {
      DOM.mcCountdown.textContent = `${String(hours).padStart(2,'0')}:${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')}`;
    }

    // Update urgency badge
    const urgency = document.getElementById('mc-urgency');
    if (urgency) {
      if (days === 0 && hours < 6) urgency.textContent = 'IMMINENT';
      else if (days < 1) urgency.textContent = 'CRITICAL';
      else urgency.textContent = 'URGENT';
    }
  }
  tick();
  setInterval(tick, 1000);
}

// ── Live Pipeline Data ────────────────────────────────────────
async function loadLivePipelines() {
  if (!DOM.pipelineGrid) return;
  DOM.pipelineGrid.innerHTML = `
    <div class="pipeline-loading">
      <div class="spinner"></div>
      <span>Fetching live GitLab data…</span>
    </div>`;
  try {
    const res = await fetch(`${CONFIG.API_BASE}/dashboard/projects`, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.liveProjects = data.projects || [];
    if (state.liveProjects.length === 0) throw new Error('empty');
    renderPipelines(state.liveProjects);
  } catch (err) {
    state.liveProjects = [];
    DOM.pipelineGrid.innerHTML = `<div class="pipeline-loading"><span>⚠️ Couldn't load live GitLab data (${err.message}). Retrying…</span></div>`;
  }
  renderVenues();
}

// ── Pipeline renderer ─────────────────────────────────────────
function renderPipelines(projects) {
  if (!DOM.pipelineGrid) return;
  if (!projects || projects.length === 0) {
    DOM.pipelineGrid.innerHTML = `<div class="pipeline-loading"><span>No projects found.</span></div>`;
    return;
  }

  DOM.pipelineGrid.innerHTML = projects.map((p) => {
    const pl     = p.latest_pipeline || {};
    const status = pl.status || 'unknown';
    const pid    = pl.id   ? `#${pl.id}` : '—';
    const purl   = pl.web_url || p.web_url || '#';
    const ref    = pl.ref || 'main';

    const statusLabel = { success:'Passed', failed:'Failed', running:'Running',
                          canceled:'Canceled', pending:'Pending' }[status] || status;
    const statusEmoji = { success:'✅', failed:'❌', running:'🔄', canceled:'⏹', pending:'⏳' }[status] || '●';

    // Sparkline from history
    const hist    = (p.pipeline_history || []).slice(0, 6);
    const sparkHtml = hist.length
      ? `<div class="pipeline-sparkline">
           ${hist.reverse().map(s => `<span class="spark-dot spark-dot--${s}" title="${s}"></span>`).join('')}
           <span style="font-size:0.65rem;color:#5a637a;margin-left:4px">last ${hist.length}</span>
         </div>`
      : '';

    // Tags
    const tags = [];
    if (p.open_mrs   > 0) tags.push(`<span class="pipeline-tag pipeline-tag--mr">⬡ ${p.open_mrs} MR${p.open_mrs>1?'s':''}</span>`);
    if (p.open_issues> 0) tags.push(`<span class="pipeline-tag pipeline-tag--issue">◎ ${p.open_issues} issue${p.open_issues>1?'s':''}</span>`);
    const tagsHtml = tags.length ? `<div class="pipeline-card-tags">${tags.join('')}</div>` : '';

    // Fix button for failed
    const fixBtn = (status === 'failed')
      ? `<button class="pipeline-fix-btn" data-project="${p.name}" onclick="fixPipeline('${p.name}')">
           ⚡ Ask Copa Agent to Fix
         </button>`
      : '';

    return `
      <div class="pipeline-card pipeline-card--${status}">
        <div class="pipeline-card-header">
          <span class="pipeline-card-name">${p.name}</span>
          <span class="pipeline-card-status-dot"></span>
        </div>
        <div class="pipeline-card-desc">${p.description || ''}</div>
        ${sparkHtml}
        ${tagsHtml}
        <div class="pipeline-card-footer">
          <a class="pipeline-card-link" href="${purl}" target="_blank" rel="noopener">
            ${pid} · ${ref} ↗
          </a>
          <span class="pipeline-card-status-label">${statusEmoji} ${statusLabel}</span>
        </div>
        ${fixBtn}
      </div>`;
  }).join('');

  // Update stats
  const passed  = projects.filter(p => (p.latest_pipeline||{}).status === 'success').length;
  const total   = projects.length;
  const pct     = total > 0 ? Math.round((passed / total) * 100) : 0;

  if (DOM.healthPct)      DOM.healthPct.textContent = `${pct}%`;
  if (DOM.mcHealth)       DOM.mcHealth.textContent   = `${passed}/${total}`;
  if (DOM.pipelineCount)  DOM.pipelineCount.textContent = `${total} services`;
  if (DOM.readinessLabel) DOM.readinessLabel.textContent = `${pct}% ready`;
  if (DOM.readinessBar) {
    DOM.readinessBar.style.width = `${pct}%`;
    DOM.readinessBar.classList.toggle('full', pct === 100);
  }

  // Platform health dot
  if (DOM.platformStatus) {
    const dot = DOM.platformStatus.querySelector('.status-dot');
    if (dot) {
      dot.className = `status-dot status-dot--${pct >= 80 ? 'healthy' : pct >= 50 ? 'warning' : 'critical'}`;
    }
  }

  // Health icon
  const healthIcon = document.getElementById('mc-health-icon');
  if (healthIcon) healthIcon.textContent = pct === 100 ? '✅' : pct >= 60 ? '⚠️' : '🚨';

  if (window.lucide) lucide.createIcons();
}

// Quick fix button helper
function fixPipeline(projectName) {
  const msg = `The ${projectName} pipeline is failing. Investigate the root cause, fix the code, create a fix branch, commit the fix, and open a merge request.`;
  DOM.chatInput.value = msg;
  handleSend();
}

// ── Venue renderer ────────────────────────────────────────────
// Venue deployment status is derived from real, live pipeline health
// (state.liveProjects) — not per-venue hardcoded data.
function renderVenues() {
  if (!DOM.venueGrid) return;
  const projects = state.liveProjects || [];
  let status = 'pending';
  if (projects.length > 0) {
    const passed = projects.filter(p => (p.latest_pipeline || {}).status === 'success').length;
    const pct = passed / projects.length;
    status = pct === 1 ? 'deployed' : pct > 0 ? 'staging' : 'pending';
  }
  DOM.venueGrid.innerHTML = VENUES.map((v) => `
    <div class="venue-card">
      <span class="venue-status-dot venue-status-dot--${status}"></span>
      <div class="venue-info">
        <div class="venue-name">${v.name}</div>
        <div class="venue-city">${v.city}</div>
      </div>
      <span class="venue-flag">${v.flag}</span>
    </div>`).join('');
}

// ── Chat send ─────────────────────────────────────────────────
async function handleSend() {
  const message = DOM.chatInput.value.trim();
  if (!message || state.isWaiting) return;

  DOM.chatInput.value = '';
  DOM.chatInput.style.height = 'auto';
  addChatMessage('user', message);

  state.isWaiting = true;
  DOM.btnSend.disabled = true;
  const typingEl = showTypingIndicator();

  try {
    await streamFromAgent(message, typingEl);
  } catch (err) {
    removeElement(typingEl);
    addChatMessage('agent', `⚠️ Agent error: ${err.message}. Please try again.`);
  }

  state.isWaiting = false;
  DOM.btnSend.disabled = false;
  DOM.chatInput.focus();
}

// ── SSE streaming ─────────────────────────────────────────────
async function streamFromAgent(message, typingEl) {
  const res = await fetch(`${CONFIG.API_BASE}/agent/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: state.sessionId }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', gotReply = false, actionShown = false;

  const setThinking = (text) => {
    let t = typingEl.querySelector('.typing-thought');
    if (!t) {
      t = document.createElement('div');
      t.className = 'typing-thought';
      typingEl.querySelector('.message-content')?.appendChild(t);
    }
    t.textContent = text;
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

      if      (ev.type === 'session') { state.sessionId = ev.session_id; }
      else if (ev.type === 'status')  { setThinking(ev.text); }
      else if (ev.type === 'action') {
        if (!actionShown) { showActionFeed(true); actionShown = true; }
        const a = { tool_name: ev.tool, description: ev.description,
                    timestamp: ev.timestamp, status: ev.status };
        addActionFeedItem(a);
        addTimelineItem(a);
        // Increment auto-fixed counter when an MR is created
        if (ev.tool === 'create_merge_request' && ev.status === 'completed') {
          incrementFixed();
        }
      } else if (ev.type === 'approval_request') {
        if (!actionShown) { showActionFeed(true); actionShown = true; }
        addApprovalCard(ev);
        setThinking('⏸️ Waiting for your approval…');
      } else if (ev.type === 'reply') {
        removeElement(typingEl);
        addChatMessage('agent', renderMarkdown(ev.reply));
        gotReply = true;
        // Refresh pipeline data after agent action
        setTimeout(loadLivePipelines, 2000);
      }
    }
  }
  if (!gotReply) removeElement(typingEl);
}

// ── Auto-fix counter ──────────────────────────────────────────
function incrementFixed() {
  state.autoFixedCount++;
  if (DOM.mcFixed) {
    DOM.mcFixed.textContent = state.autoFixedCount;
    DOM.mcFixed.classList.remove('flash');
    void DOM.mcFixed.offsetWidth; // reflow
    DOM.mcFixed.classList.add('flash');
  }
}

// ── Chat UI helpers ───────────────────────────────────────────
function addChatMessage(role, html) {
  const isUser = role === 'user';
  const msg = document.createElement('div');
  msg.className = `chat-message chat-message--${isUser ? 'user' : 'agent'}`;
  msg.innerHTML = `
    <div class="message-avatar">${isUser ? '👤' : '⚽'}</div>
    <div class="message-content">
      <div class="message-sender">${isUser ? 'You' : 'Copa Agent'}</div>
      <div class="message-text">${isUser ? escapeHtml(html) : html}</div>
    </div>`;
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
      <div class="typing-indicator"><span></span><span></span><span></span></div>
    </div>`;
  DOM.chatMessages.appendChild(el);
  DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
  return el;
}

function clearChat() {
  const welcome = DOM.chatMessages.querySelector('.chat-message--agent');
  DOM.chatMessages.innerHTML = '';
  if (welcome) DOM.chatMessages.appendChild(welcome);
  state.messages = [];
  state.sessionId = null;
  showActionFeed(false);
  if (DOM.actionFeedItems) DOM.actionFeedItems.innerHTML = '';
  DOM.actionsTimeline.innerHTML = `
    <div class="timeline-empty">
      <i data-lucide="bot" class="icon-lg"></i>
      <p>No actions yet — give Copa Agent a mission above!</p>
    </div>`;
  if (DOM.actionsCount) DOM.actionsCount.textContent = '0 actions';
  if (window.lucide) lucide.createIcons();
}

// ── Action Feed ───────────────────────────────────────────────
function showActionFeed(show) {
  DOM.actionFeed?.classList.toggle('hidden', !show);
}

function addActionFeedItem(action) {
  if (!DOM.actionFeedItems) return;
  const icon   = TOOL_ICONS[action.tool_name] || '⚙️';
  const failed = action.status === 'failed';
  const el = document.createElement('div');
  el.className = `action-feed-item${failed ? ' af-failed' : ''}`;
  el.innerHTML = `
    <span class="af-icon">${icon}</span>
    <span class="af-tool">${action.tool_name}</span>
    <span class="af-desc">— ${action.description}</span>`;
  DOM.actionFeedItems.appendChild(el);
  DOM.actionFeedItems.scrollTop = DOM.actionFeedItems.scrollHeight;
}

// ── Human-in-the-loop approval ──────────────────────────────────
function addApprovalCard(ev) {
  if (!DOM.actionFeedItems) return;
  const icon = TOOL_ICONS[ev.tool] || '⚙️';
  const card = document.createElement('div');
  card.className = 'action-feed-item af-approval';
  card.innerHTML = `
    <span class="af-icon">${icon}</span>
    <span class="af-tool">⏸️ Approval needed</span>
    <span class="af-desc">— ${ev.description}</span>
    <div class="af-approval-buttons">
      <button class="btn-approve" type="button">✅ Approve</button>
      <button class="btn-reject" type="button">⛔ Reject</button>
    </div>`;
  DOM.actionFeedItems.appendChild(card);
  DOM.actionFeedItems.scrollTop = DOM.actionFeedItems.scrollHeight;

  const buttons = card.querySelector('.af-approval-buttons');
  const decide = async (approved) => {
    buttons.innerHTML = approved
      ? '<span class="af-decision">✅ Approved</span>'
      : '<span class="af-decision">⛔ Rejected</span>';
    try {
      await fetch(`${CONFIG.API_BASE}/agent/approvals/${ev.approval_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved }),
      });
    } catch (err) {
      console.error('Approval request failed:', err);
    }
  };
  card.querySelector('.btn-approve').addEventListener('click', () => decide(true));
  card.querySelector('.btn-reject').addEventListener('click', () => decide(false));
}

// ── Timeline ──────────────────────────────────────────────────
function addTimelineItem(action) {
  const empty = DOM.actionsTimeline.querySelector('.timeline-empty');
  if (empty) empty.remove();

  const time   = new Date(action.timestamp).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
  const icon   = TOOL_ICONS[action.tool_name] || '⚙️';
  const failed = action.status === 'failed';

  const el = document.createElement('div');
  el.className = 'timeline-item';
  el.innerHTML = `
    <span class="timeline-time">${time}</span>
    <div class="timeline-icon">${icon}</div>
    <div class="timeline-text">
      <span class="timeline-tool-chip${failed ? ' timeline-tool-chip--failed' : ''}">${action.tool_name}</span><br>
      ${action.description}
    </div>`;
  DOM.actionsTimeline.prepend(el);
  state.actions.push(action);

  // Update count badge
  if (DOM.actionsCount) DOM.actionsCount.textContent = `${state.actions.length} action${state.actions.length !== 1 ? 's' : ''}`;
}

// ── Markdown renderer ─────────────────────────────────────────
function renderMarkdown(md) {
  if (!md) return '';
  let h = escapeHtml(md);
  // Tables
  h = h.replace(/(^\|.*\|$\n?)+/gm, (block) => {
    const rows  = block.trim().split('\n').filter(r => !/^\|[\s|:-]+\|$/.test(r));
    const cells = rows.map(r => r.split('|').slice(1,-1).map(c => c.trim()));
    if (!cells.length) return block;
    const head = `<tr>${cells[0].map(c => `<th>${c}</th>`).join('')}</tr>`;
    const body = cells.slice(1).map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('');
    return `<table>${head}${body}</table>`;
  });
  h = h
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g,  '<strong>$1</strong>')
    .replace(/`([^`]+)`/g,        '<code>$1</code>')
    .replace(/^### (.*)$/gm,      '<h4>$1</h4>')
    .replace(/^\d+\.\s+(.*)$/gm,  '<div class="md-li">• $1</div>')
    .replace(/^[-*]\s+(.*)$/gm,   '<div class="md-li">• $1</div>')
    .replace(/\n/g, '<br>');
  return h;
}

// ── Utilities ─────────────────────────────────────────────────
function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
function removeElement(el)  { if (el?.parentNode) el.parentNode.removeChild(el); }
