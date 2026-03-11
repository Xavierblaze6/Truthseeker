// ── Config ────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";

// ── Session ───────────────────────────────────────────────────────────────
let sessionId = localStorage.getItem("ts_session_id");
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem("ts_session_id", sessionId);
}

// ── State ─────────────────────────────────────────────────────────────────
let credibilityChart = null;
let chatOpen = false;

// ── DOM refs ──────────────────────────────────────────────────────────────
const claimInput        = document.getElementById("claim-input");
const checkBtn          = document.getElementById("check-btn");
const charCountEl       = document.getElementById("char-count");
const loadingEl         = document.getElementById("loading");
const resultsPanel      = document.getElementById("results-panel");
const verdictBadge      = document.getElementById("verdict-badge");
const scoreValue        = document.getElementById("score-value");
const reasoningText     = document.getElementById("reasoning-text");
const wikiSnippet       = document.getElementById("wiki-snippet");
const webSnippet        = document.getElementById("web-snippet");
const redditSnippet     = document.getElementById("reddit-snippet");
const supportingList    = document.getElementById("supporting-list");
const contradictingList = document.getElementById("contradicting-list");
const chatPanel         = document.getElementById("chat-panel");
const chatBody          = document.getElementById("chat-body");
const chatChevron       = document.getElementById("chat-chevron");
const chatMessages      = document.getElementById("chat-messages");
const chatInput         = document.getElementById("chat-input");

const steps = {
  wiki:   document.getElementById("step-wiki"),
  web:    document.getElementById("step-web"),
  reddit: document.getElementById("step-reddit"),
  ai:     document.getElementById("step-ai"),
};

// ── Character counter ─────────────────────────────────────────────────────
claimInput.addEventListener("input", () => {
  charCountEl.textContent = claimInput.value.length;
});

// ── Loading step sequencer ────────────────────────────────────────────────
let stepTimers = [];

function startLoadingSteps() {
  const order   = ["wiki", "web", "reddit", "ai"];
  const delays  = [0, 500, 1000, 1700];
  order.forEach(k => { steps[k].className = "step"; });
  stepTimers = delays.map((delay, i) =>
    setTimeout(() => {
      if (i > 0) steps[order[i - 1]].className = "step done";
      steps[order[i]].className = "step active";
    }, delay)
  );
}

function stopLoadingSteps() {
  stepTimers.forEach(clearTimeout);
  Object.values(steps).forEach(s => { s.className = "step done"; });
}

// ── Fact-check handler ────────────────────────────────────────────────────
async function handleFactCheck() {
  const claim = claimInput.value.trim();
  if (!claim) { claimInput.focus(); return; }

  setLoading(true);
  resultsPanel.classList.add("hidden");
  chatPanel.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/fact-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim, session_id: sessionId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Server error");
    }
    renderResults(await res.json());
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

// ── Render results ────────────────────────────────────────────────────────
function renderResults(data) {
  const verdict = (data.verdict || "UNVERIFIED").toUpperCase();
  const score   = Number(data.credibility_score) || 0;

  // Verdict badge
  verdictBadge.textContent = verdict;
  verdictBadge.className   = "verdict-badge " + verdict.toLowerCase();

  // Chart + count-up score animation
  renderChart(score);
  animateScore(score);

  // Analysis
  reasoningText.textContent = data.reasoning || "No reasoning provided.";

  // Snippets
  wikiSnippet.textContent   = data.wikipedia_snippet || "No Wikipedia results found.";
  webSnippet.textContent    = data.web_snippets      || "No web results found.";
  redditSnippet.textContent = data.reddit_snippets   || "No Reddit results found.";

  // Pill lists
  renderPills(supportingList,    data.supporting_sources);
  renderPills(contradictingList, data.contradicting_sources);

  // Stagger source cards into view
  const sourceCards = [
    document.getElementById("wiki-card"),
    document.getElementById("web-card"),
    document.getElementById("reddit-card"),
  ];
  sourceCards.forEach((card, i) => {
    card.classList.remove("fade-slide-up");
    void card.offsetWidth; // force reflow to restart animation
    card.style.animationDelay = `${i * 120}ms`;
    card.classList.add("fade-slide-up");
  });

  // Reveal panels
  resultsPanel.classList.remove("hidden");
  chatPanel.classList.remove("hidden");
  chatMessages.innerHTML = "";

  // Auto-open chat on first result
  if (!chatOpen) toggleChat();

  setTimeout(() => {
    resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 80);
}

// ── Score count-up ────────────────────────────────────────────────────────
function animateScore(target) {
  let current = 0;
  const step  = target / 40;
  const timer = setInterval(() => {
    current += step;
    if (current >= target) { current = target; clearInterval(timer); }
    scoreValue.textContent = Math.round(current);
  }, 25);
}

// ── Chart.js doughnut ─────────────────────────────────────────────────────
function scoreToColor(score) {
  if (score <= 40) return "#ef4444";
  if (score <= 70) return "#f59e0b";
  return "#22c55e";
}

function renderChart(score) {
  const ctx       = document.getElementById("credibility-chart").getContext("2d");
  const color     = scoreToColor(score);
  const remainder = 100 - score;

  if (credibilityChart) {
    credibilityChart.data.datasets[0].data            = [score, remainder];
    credibilityChart.data.datasets[0].backgroundColor = [color, "#1a1a24"];
    credibilityChart.update();
    return;
  }

  credibilityChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data:            [score, remainder],
        backgroundColor: [color, "#1a1a24"],
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      cutout: "74%",
      animation: { animateRotate: true, duration: 800 },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────
function renderPills(ulEl, items) {
  if (!items || items.length === 0) {
    ulEl.innerHTML = '<li class="pill">None</li>';
    return;
  }
  ulEl.innerHTML = items.map(s => `<li class="pill">${escapeHtml(s)}</li>`).join("");
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setLoading(show) {
  if (show) {
    loadingEl.classList.remove("hidden");
    checkBtn.disabled = true;
    checkBtn.classList.add("scanning");
    startLoadingSteps();
  } else {
    loadingEl.classList.add("hidden");
    checkBtn.disabled = false;
    checkBtn.classList.remove("scanning");
    stopLoadingSteps();
  }
}

function showError(message) {
  const el = document.createElement("div");
  el.className = "card animate-in";
  el.style.cssText = "border-color:#ef4444;color:#ef4444;";
  el.textContent = `Error: ${message}`;
  loadingEl.insertAdjacentElement("afterend", el);
  setTimeout(() => el.remove(), 6000);
}

// ── Collapsible chat ──────────────────────────────────────────────────────
function toggleChat() {
  chatOpen = !chatOpen;
  chatBody.classList.toggle("open", chatOpen);
  chatChevron.classList.toggle("open", chatOpen);
}

// ── Chat handler ──────────────────────────────────────────────────────────
async function handleChat() {
  const message = chatInput.value.trim();
  if (!message) return;

  appendBubble(message, "user");
  chatInput.value    = "";
  chatInput.disabled = true;

  const typingEl = showTyping();

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Server error");
    }
    removeTyping(typingEl);
    appendBubble((await res.json()).reply, "assistant");
  } catch (err) {
    removeTyping(typingEl);
    appendBubble(`Error: ${err.message}`, "assistant");
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
  }
}

function appendBubble(text, role) {
  const bubble = document.createElement("div");
  bubble.className   = `bubble ${role}`;
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.innerHTML = '<span class="typing-dot"></span>'
               + '<span class="typing-dot"></span>'
               + '<span class="typing-dot"></span>';
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return el;
}

function removeTyping(el) {
  if (el && el.parentNode) el.remove();
}
