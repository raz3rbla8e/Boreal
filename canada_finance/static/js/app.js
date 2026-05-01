// ── SECURITY: HTML ESCAPING ───────────────────────────────────────────────────
function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(str) {
  return escapeHtml(str);
}

// ── API FETCH WRAPPER ─────────────────────────────────────────────────────────
let _csrfToken = null;

async function _ensureCsrf() {
  if (_csrfToken) return _csrfToken;
  try {
    const res = await fetch('/api/csrf-token');
    const data = await res.json();
    _csrfToken = data.csrf_token;
  } catch(e) { _csrfToken = ''; }
  return _csrfToken;
}

async function apiFetch(url, opts = {}) {
  try {
    // Attach CSRF token to mutating requests
    const method = (opts.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
      const token = await _ensureCsrf();
      opts.headers = opts.headers || {};
      opts.headers['X-CSRF-Token'] = token;
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      let msg = `Server error (${res.status})`;
      try { const body = await res.json(); if (body.error) msg = body.error; } catch(e) {}
      toast(msg, 'error');
      return null;
    }
    return await res.json();
  } catch(e) {
    toast('Network error — is the server running?', 'error');
    return null;
  }
}

let EXPENSE_CATS = [];
let INCOME_CATS = [];
let ALL_CATEGORIES = [];
let isDemo = false;
const PALETTE = ["#6ee7b7","#f59e0b","#60a5fa","#a78bfa","#f87171","#34d399",
  "#fbbf24","#818cf8","#fb7185","#4ade80","#e879f9","#38bdf8","#fb923c","#a3e635"];

let months = [], currentMonthIdx = 0, donutChart = null;
let currentYear = new Date().getFullYear();

// ── DASHBOARD LAYOUT CUSTOMIZATION ────────────────────────────────────────────
const DEFAULT_PANELS = [
  {id: 'spending-by-category', label: 'Spending by Category', visible: true},
  {id: 'donut-chart', label: 'Breakdown Chart', visible: true},
  {id: 'averages', label: 'Monthly Averages', visible: true},
  {id: 'recent-txns', label: 'Recent Transactions', visible: true},
  {id: 'recurring', label: 'Recurring & Subscriptions', visible: true},
  {id: 'spending-trends', label: 'Spending Trends', visible: true},
  {id: 'savings-goals', label: 'Savings Goals', visible: true},
  {id: 'net-worth', label: 'Net Worth', visible: true},
  {id: 'account-balances', label: 'Account Balances', visible: true},
];
let dashboardLayout = null;

function getDashboardLayout() {
  return dashboardLayout || DEFAULT_PANELS.map(p => ({...p}));
}

function loadDashboardLayout(settings) {
  try {
    if (settings && settings.dashboard_layout) {
      const saved = JSON.parse(settings.dashboard_layout);
      if (Array.isArray(saved) && saved.length) {
        const savedIds = new Set(saved.map(p => p.id));
        const merged = [...saved];
        DEFAULT_PANELS.forEach(dp => { if (!savedIds.has(dp.id)) merged.push({...dp}); });
        dashboardLayout = merged.filter(p => DEFAULT_PANELS.some(dp => dp.id === p.id));
        return;
      }
    }
  } catch(e) {}
  dashboardLayout = null;
}

function applyDashboardLayout() {
  const layout = getDashboardLayout();
  const container = document.getElementById('dashboard-panels');
  if (!container) return;
  layout.forEach(p => {
    const panel = container.querySelector(`[data-panel-id="${p.id}"]`);
    if (panel) {
      container.appendChild(panel);
      if (p.visible) panel.classList.remove('panel-hidden');
      else panel.classList.add('panel-hidden');
    }
  });
}

function isPanelVisible(panelId) {
  const layout = getDashboardLayout();
  const p = layout.find(x => x.id === panelId);
  return p ? p.visible : true;
}

function saveDashboardLayout(layout) {
  dashboardLayout = layout;
  apiFetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({dashboard_layout: JSON.stringify(layout)})});
}

// ── COLLAPSIBLE PANELS ────────────────────────────────────────────────────────
function initCollapsiblePanels() {
  const container = document.getElementById('dashboard-panels');
  if (!container) return;
  const collapsed = JSON.parse(localStorage.getItem('panelCollapsed') || '{}');
  container.querySelectorAll('.panel[data-panel-id]').forEach(panel => {
    const title = panel.querySelector('.panel-title');
    if (!title || title.querySelector('.panel-collapse-chevron')) return;
    // Add chevron
    const chevron = document.createElement('span');
    chevron.className = 'panel-collapse-chevron';
    chevron.textContent = '▾';
    title.insertBefore(chevron, title.firstChild);
    // Restore collapsed state
    if (collapsed[panel.dataset.panelId]) panel.classList.add('panel-collapsed');
    // Click handler on title
    title.addEventListener('click', function(e) {
      // Don't collapse if clicking a button inside the title
      if (e.target.closest('button')) return;
      panel.classList.toggle('panel-collapsed');
      const state = JSON.parse(localStorage.getItem('panelCollapsed') || '{}');
      state[panel.dataset.panelId] = panel.classList.contains('panel-collapsed');
      localStorage.setItem('panelCollapsed', JSON.stringify(state));
    });
  });
}

// ── AUTO-HIDE EMPTY PANELS ────────────────────────────────────────────────────
function autoHideEmptyPanels() {
  const container = document.getElementById('dashboard-panels');
  if (!container) return;
  container.querySelectorAll('.panel[data-panel-id]').forEach(panel => {
    const id = panel.dataset.panelId;
    // Skip user-hidden panels (they're already hidden via customize)
    if (panel.classList.contains('panel-hidden')) return;
    let hasData = true;
    switch(id) {
      case 'spending-by-category': {
        const el = document.getElementById('cat-list');
        hasData = el && el.children.length > 0 && !el.querySelector(':scope > .empty:only-child');
        break;
      }
      case 'donut-chart':
        hasData = !!donutChart;
        break;
      case 'averages': {
        const el = document.getElementById('averages-list');
        hasData = el && el.children.length > 0 && !el.querySelector(':scope > .empty:only-child');
        break;
      }
      case 'recent-txns': {
        const el = document.getElementById('recent-txns');
        hasData = el && el.children.length > 0 && !el.querySelector('.empty');
        break;
      }
      case 'recurring': {
        const el = document.getElementById('recurring-list');
        hasData = el && el.children.length > 0 && !el.querySelector(':scope > .empty:only-child');
        break;
      }
      case 'spending-trends':
        hasData = !!trendsChart;
        break;
      case 'savings-goals': {
        const el = document.getElementById('goals-dashboard-list');
        hasData = el && el.children.length > 0 && !el.querySelector(':scope > .empty:only-child');
        break;
      }
      case 'net-worth': {
        const wrap = panel.querySelector('.chart-wrap');
        hasData = wrap && !wrap.querySelector('.empty') && !!document.getElementById('net-worth-chart');
        break;
      }
      case 'account-balances': {
        const el = document.getElementById('account-balances-list');
        hasData = el && el.children.length > 0 && !el.querySelector(':scope > .empty:only-child');
        break;
      }
    }
    if (hasData) panel.classList.remove('panel-auto-hidden');
    else panel.classList.add('panel-auto-hidden');
  });
}

function openCustomizeModal() {
  renderCustomizeList('customize-panel-list');
  document.getElementById('customize-modal').classList.add('open');
}

function renderCustomizeList(containerId) {
  const layout = getDashboardLayout();
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = layout.map((p, i) => `
    <div class="customize-item" draggable="true" data-panel-id="${escapeAttr(p.id)}">
      <span class="drag-handle">&#x2807;</span>
      <div class="customize-arrows">
        <button class="btn-icon" onclick="movePanelInList('${containerId}',${i},-1)" ${i===0?'disabled style="opacity:.3"':''}>&#x25B2;</button>
        <button class="btn-icon" onclick="movePanelInList('${containerId}',${i},1)" ${i===layout.length-1?'disabled style="opacity:.3"':''}>&#x25BC;</button>
      </div>
      <span class="customize-label">${escapeHtml(p.label)}</span>
      <label class="toggle" onclick="event.stopPropagation()">
        <input type="checkbox" ${p.visible ? 'checked' : ''} onchange="togglePanelVisibility('${escapeAttr(p.id)}',this.checked)">
        <span class="toggle-slider"></span>
      </label>
    </div>`).join('');
  initCustomizeDragDrop(el);
}

function initCustomizeDragDrop(container) {
  let dragEl = null;
  let dropped = false;
  container.querySelectorAll('.customize-item').forEach(item => {
    item.addEventListener('dragstart', e => {
      dragEl = item; dropped = false; item.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', '');
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      container.querySelectorAll('.customize-item').forEach(i => i.classList.remove('drag-over'));
      if (dropped) onDragReorder(container);
      dragEl = null; dropped = false;
    });
    item.addEventListener('dragover', e => {
      e.preventDefault(); e.dataTransfer.dropEffect = 'move';
      if (item !== dragEl) item.classList.add('drag-over');
    });
    item.addEventListener('dragleave', () => item.classList.remove('drag-over'));
    item.addEventListener('drop', e => {
      e.preventDefault();
      if (dragEl && dragEl !== item) {
        const items = [...container.querySelectorAll('.customize-item')];
        const from = items.indexOf(dragEl), to = items.indexOf(item);
        if (from < to) item.after(dragEl); else item.before(dragEl);
        dropped = true;
      }
      container.querySelectorAll('.customize-item').forEach(i => i.classList.remove('drag-over'));
    });
  });
}

function onDragReorder(container) {
  const layout = [...container.querySelectorAll('.customize-item')].map(item => ({
    id: item.dataset.panelId,
    label: DEFAULT_PANELS.find(p => p.id === item.dataset.panelId)?.label || '',
    visible: item.querySelector('input[type="checkbox"]').checked
  }));
  saveDashboardLayout(layout);
  applyDashboardLayout();
  refreshAllCustomizeLists();
}

function movePanelInList(containerId, idx, dir) {
  const layout = getDashboardLayout();
  const newIdx = idx + dir;
  if (newIdx < 0 || newIdx >= layout.length) return;
  [layout[idx], layout[newIdx]] = [layout[newIdx], layout[idx]];
  saveDashboardLayout(layout);
  applyDashboardLayout();
  refreshAllCustomizeLists();
}

function togglePanelVisibility(panelId, visible) {
  const layout = getDashboardLayout();
  const p = layout.find(x => x.id === panelId);
  if (p) p.visible = visible;
  saveDashboardLayout(layout);
  applyDashboardLayout();
  if (visible && months.length) {
    if (panelId === 'averages') renderAverages();
    if (panelId === 'recurring') renderRecurring();
    if (panelId === 'spending-trends') renderTrends();
    if (panelId === 'savings-goals') renderGoalsDashboard();
    if (panelId === 'net-worth') renderNetWorth();
    if (panelId === 'account-balances') renderAccountBalances();
  }
  refreshAllCustomizeLists();
}

function refreshAllCustomizeLists() {
  ['customize-panel-list','settings-panel-list'].forEach(id => {
    if (document.getElementById(id)) renderCustomizeList(id);
  });
}

function resetDashboardLayout() {
  dashboardLayout = null;
  saveDashboardLayout(DEFAULT_PANELS.map(p => ({...p})));
  applyDashboardLayout();
  refreshAllCustomizeLists();
  toast('Dashboard reset to default \u2713','success');
  if (months.length) { renderAverages(); renderRecurring(); }
}

async function loadCategories() {
  ALL_CATEGORIES = await apiFetch('/api/categories') || [];
  EXPENSE_CATS = ALL_CATEGORIES.filter(c=>c.type==='Expense').map(c=>c.name);
  INCOME_CATS = ALL_CATEGORIES.filter(c=>c.type==='Income').map(c=>c.name);
  EXPENSE_CATS.push('UNCATEGORIZED');
}

// ── THEME ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  const dark = document.getElementById('theme-toggle').checked;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  if (isDemo) return; // Don't save theme in demo mode
  apiFetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: dark ? 'dark' : 'light'})});
}

// ── DEMO MODE ─────────────────────────────────────────────────────────────────
function applyDemoRestrictions() {
  // Disable sidebar buttons that are blocked in demo mode
  document.querySelectorAll('.nav-btn').forEach(btn => {
    const onclick = btn.getAttribute('onclick') || '';
    if (onclick.includes("nav('import')")) {
      btn.classList.add('demo-disabled');
      btn.setAttribute('onclick', "toast('Import is disabled in demo mode','error')");
    }
    if (onclick.includes('openAddModal')) {
      btn.classList.add('demo-disabled');
      btn.setAttribute('onclick', "toast('Adding transactions is disabled in demo mode','error')");
    }
  });
  // Disable the import drop zone on page load
  applyDemoToImport();
}

function applyDemoToTransactions() {
  if (!isDemo) return;
  // Hide delete buttons (inline X) in transaction rows
  document.querySelectorAll('.del-btn').forEach(el => el.style.display = 'none');
  // Hide bulk delete button
  const bulkDel = document.querySelector('#bulk-toolbar .btn-sm[onclick="bulkDelete()"]');
  if (bulkDel) bulkDel.style.display = 'none';
  // Disable inline "+ Add" button in filter row
  const addBtn = document.querySelector('#sec-transactions .filter-row .btn-sm[onclick="openAddModal()"]');
  if (addBtn) {
    addBtn.classList.add('demo-disabled');
    addBtn.setAttribute('onclick', "toast('Adding transactions is disabled in demo mode','error')");
  }
}

function applyDemoToEditModal() {
  if (!isDemo) return;
  // Hide delete button in edit modal
  const delBtn = document.querySelector('#edit-modal .btn-red');
  if (delBtn) delBtn.style.display = 'none';
}

function applyDemoToSettings() {
  if (!isDemo) return;
  // Disable add category button
  const addCatBtn = document.querySelector('#sec-settings .btn[onclick="addCategory()"]');
  if (addCatBtn) { addCatBtn.classList.add('demo-disabled'); addCatBtn.setAttribute('onclick', "toast('Disabled in demo mode','error')"); }
  // Disable set budget button
  const budgetBtn = document.querySelector('#sec-settings .btn[onclick="saveBudget()"]');
  if (budgetBtn) { budgetBtn.classList.add('demo-disabled'); budgetBtn.setAttribute('onclick', "toast('Disabled in demo mode','error')"); }
  // Disable add rule button
  const addRuleBtn = document.querySelector('#sec-settings .btn[onclick="openRuleModal()"]');
  if (addRuleBtn) { addRuleBtn.classList.add('demo-disabled'); addRuleBtn.setAttribute('onclick', "toast('Disabled in demo mode','error')"); }
  // Disable load template button
  const templateBtn = document.querySelector('#sec-settings .btn[onclick="openTemplateModal()"]');
  if (templateBtn) { templateBtn.classList.add('demo-disabled'); templateBtn.setAttribute('onclick', "toast('Disabled in demo mode','error')"); }
  // Hide category rename/delete buttons
  document.querySelectorAll('#expense-cat-list .btn-icon, #income-cat-list .btn-icon').forEach(btn => {
    const onclick = btn.getAttribute('onclick') || '';
    if (onclick.includes('renameCategory') || onclick.includes('deleteCategory')) {
      btn.style.display = 'none';
    }
  });
  // Hide budget remove buttons
  document.querySelectorAll('#budget-list .btn-red').forEach(btn => btn.style.display = 'none');
  // Hide learned merchant remove buttons
  document.querySelectorAll('#learned-list .btn-ghost').forEach(btn => {
    const onclick = btn.getAttribute('onclick') || '';
    if (onclick.includes('deleteLearned')) btn.style.display = 'none';
  });
}

function applyDemoToImport() {
  if (!isDemo) return;
  const dropZone = document.getElementById('drop-zone');
  if (dropZone) {
    dropZone.classList.add('demo-disabled');
    dropZone.setAttribute('onclick', '');
    dropZone.querySelector('strong').textContent = 'Import is disabled in demo mode';
    dropZone.querySelector('p').textContent = 'Download the app to import your own bank data.';
  }
}

async function resetDemo() {
  if (!confirm('Reset all demo data to its original state?')) return;
  const res = await fetch('/api/demo/reset', {method:'POST'});
  if (res.ok) {
    toast('Demo data reset ✓', 'success');
    setTimeout(() => location.reload(), 500);
  } else {
    toast('Reset failed', 'error');
  }
}

// ── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  // Check demo mode
  const demoRes = await apiFetch('/api/demo');
  if (demoRes && demoRes.demo) {
    isDemo = true;
    document.getElementById('demo-banner').style.display = 'flex';
    document.title = '[Demo] Boreal';
    applyDemoRestrictions();
  }

  // Load categories from DB
  await loadCategories();

  // Load settings
  const settings = await apiFetch('/api/settings') || {theme:'dark'};
  const dark = settings.theme !== 'light';
  document.getElementById('theme-toggle').checked = dark;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  loadDashboardLayout(settings);

  months = await apiFetch('/api/months') || [];
  if (!months.length) {
    document.getElementById('empty-state').style.display = 'flex';
    document.getElementById('dashboard-content').style.display = 'none';
    populateCatFilter();
    populateAccountFilter();
    updateCatOptions('f-category','f-type');
    populateBudgetCat();
    updateHiddenCount();
    renderAverages();
    renderRecurring();
    return;
  }
  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('dashboard-content').style.display = '';
  applyDashboardLayout();
  initCollapsiblePanels();
  currentMonthIdx = 0;
  document.getElementById('f-date').value = new Date().toISOString().slice(0,10);
  populateCatFilter();
  populateAccountFilter();
  updateCatOptions('f-category','f-type');
  populateBudgetCat();
  renderMonth();
  loadSettings();
  updateHiddenCount();
  autoPostSchedules();
}

const fmt = n => '$' + Math.abs(n).toLocaleString('en-CA',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtMonth = m => { const [y,mo]=m.split('-'); return new Date(y,mo-1).toLocaleString('default',{month:'long',year:'numeric'}); };

// ── MONTH NAV ─────────────────────────────────────────────────────────────────
function changeMonth(dir) {
  currentMonthIdx = Math.max(0, Math.min(months.length-1, currentMonthIdx-dir));
  renderMonth();
}

async function renderMonth() {
  const m = months[currentMonthIdx];
  const monthEl = document.getElementById('month-display');
  // Update only the text node, preserve the month-menu child
  const textNode = Array.from(monthEl.childNodes).find(n => n.nodeType === Node.TEXT_NODE);
  if (textNode) textNode.textContent = fmtMonth(m);
  else monthEl.insertBefore(document.createTextNode(fmtMonth(m)), monthEl.firstChild);
  const [summary, txnData] = await Promise.all([
    apiFetch(`/api/summary?month=${m}`),
    apiFetch(`/api/transactions?month=${m}`),
  ]);
  if (!summary || !txnData) return;
  const txns = txnData.transactions || txnData;
  renderCards(summary, txns);
  renderCatList(summary.by_category);
  renderDonut(summary.by_category);
  renderRecentTxns(txns.filter(t=>t.type==='Expense').slice(0,6));
  renderBudgetAlerts(summary.by_category);
  const renderPromises = [];
  if (isPanelVisible('averages')) renderPromises.push(renderAverages());
  if (isPanelVisible('recurring')) renderPromises.push(renderRecurring());
  if (isPanelVisible('spending-trends')) renderPromises.push(renderTrends());
  if (isPanelVisible('savings-goals')) renderPromises.push(renderGoalsDashboard());
  if (isPanelVisible('net-worth')) renderPromises.push(renderNetWorth());
  if (isPanelVisible('account-balances')) renderPromises.push(renderAccountBalances());
  await Promise.all(renderPromises);
  autoHideEmptyPanels();
  if (document.getElementById('sec-transactions').classList.contains('active')) loadTransactions();
}

// ── CARDS ─────────────────────────────────────────────────────────────────────
function renderCards(s, txns) {
  document.getElementById('card-income').textContent = fmt(s.income);
  const srcs = s.income_by_category.map(c=>`${c.category}: ${fmt(c.total)}`).join(' · ');
  document.getElementById('card-income-src').textContent = srcs || '—';

  document.getElementById('card-expense').textContent = fmt(s.expenses);
  const diff = s.expenses - s.prev_expenses;
  const vsEl = document.getElementById('card-expense-vs');
  if (s.prev_expenses > 0) {
    vsEl.textContent = (diff>=0?'↑ ':'↓ ') + fmt(Math.abs(diff)) + ' vs last month';
    vsEl.className = 'card-sub ' + (diff>0?'down':'up');
  } else { vsEl.textContent = txns.filter(t=>t.type==='Expense').length + ' transactions'; vsEl.className='card-sub'; }

  const net = document.getElementById('card-net');
  net.textContent = (s.net<0?'-':'+') + fmt(s.net);
  net.className = 'card-value ' + (s.net>=0?'green':'red');
  document.getElementById('card-net-sub').textContent = 'income − expenses';

  document.getElementById('card-rate').textContent = s.savings_rate + '%';
  const rateEl = document.getElementById('card-rate-sub');
  rateEl.textContent = s.savings_rate >= 20 ? '🎯 great saving!' : s.savings_rate >= 10 ? 'of income saved' : 'of income saved';
  rateEl.className = 'card-sub ' + (s.savings_rate>=20?'up':s.savings_rate<0?'down':'');
}

// ── CAT LIST ──────────────────────────────────────────────────────────────────
function renderCatList(cats) {
  const max = cats[0]?.total || 1;
  document.getElementById('cat-list').innerHTML = cats.length ? cats.map(c => {
    const hasBudget = c.budget && c.budget > 0;
    const barWidth = hasBudget ? Math.min(c.total/c.budget*100,100).toFixed(0) : (c.total/max*100).toFixed(0);
    const barColor = hasBudget ? (c.total>c.budget?'var(--red)':c.total>c.budget*.8?'var(--amber)':'var(--accent)') : 'var(--accent)';
    return `<div class="cat-row" onclick="filterByCat('${escapeAttr(c.category)}')">
      <span class="cat-name">${escapeHtml(c.category)}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${barWidth}%;background:${barColor}"></div></div>
      ${hasBudget ? `<span class="cat-budget ${c.total>c.budget?'over':''}">${Math.round(c.total/c.budget*100)}%</span>` : ''}
      <span class="cat-amt">${fmt(c.total)}</span>
    </div>`;
  }).join('') : '<div class="empty">No expenses this month</div>';
}

// ── DONUT ─────────────────────────────────────────────────────────────────────
function renderDonut(cats) {
  const ctx = document.getElementById('donut-chart').getContext('2d');
  if (donutChart) donutChart.destroy();
  if (!cats.length) return;
  donutChart = new Chart(ctx, {
    type:'doughnut',
    data:{ labels:cats.map(c=>c.category), datasets:[{data:cats.map(c=>c.total),
      backgroundColor:PALETTE, borderWidth:2, borderColor:getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()}]},
    options:{cutout:'68%',plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>` ${fmt(c.raw)}`}}}}
  });
}

// ── RECURRING ─────────────────────────────────────────────────────────────────
async function renderAverages() {
  const data = await apiFetch('/api/averages') || [];
  const el = document.getElementById('averages-list');
  if (!data.length) { el.innerHTML = '<div class="empty">Not enough data yet</div>'; return; }
  const maxAvg = data[0].avg_monthly || 1;
  const n = data[0].months_seen;
  document.getElementById('avg-subtitle').textContent = `last ${n} month${n!==1?'s':''}`;
  el.innerHTML = data.map(r => `
    <div class="cat-row" onclick="filterByCat('${escapeAttr(r.category)}')" style="cursor:pointer">
      <span class="cat-name">${escapeHtml(r.category)}</span>
      <span class="cat-amt" style="margin-left:auto">${fmt(r.avg_monthly)}<span style="color:var(--muted);font-size:10px">/mo</span></span>
    </div>`).join('');
}

// ── RECURRING / SUBSCRIPTIONS ─────────────────────────────────────────────────
async function renderRecurring() {
  const data = await apiFetch('/api/recurring') || {};
  const el = document.getElementById('recurring-list');
  const sub = document.getElementById('recurring-subtitle');
  const items = data.recurring || [];
  if (!items.length) { el.innerHTML = '<div class="empty">Not enough data yet (need 3+ months)</div>'; sub.textContent=''; return; }
  sub.textContent = `${items.length} detected · ${fmt(data.total_monthly_committed)}/mo committed`;
  el.innerHTML = items.map(r => {
    const priceNote = r.price_changed
      ? `<span style="color:var(--amber);font-size:10px;margin-left:4px">⚠ price changed (${fmt(r.min_amount)}→${fmt(r.max_amount)})</span>`
      : '';
    return `<div class="cat-row">
      <span class="cat-name">${escapeHtml(r.name)}${priceNote}</span>
      <span class="badge" style="margin-left:auto;margin-right:8px">${escapeHtml(r.category)}</span>
      <span class="cat-amt">${fmt(r.avg_amount)}<span style="color:var(--muted);font-size:10px">/mo</span></span>
    </div>`;
  }).join('');
}

// ── RECENT TXNS ───────────────────────────────────────────────────────────────
function renderRecentTxns(txns) {
  document.getElementById('recent-txns').innerHTML = txns.length
    ? txns.map(t=>`<tr onclick="openEditModal(${escapeAttr(JSON.stringify(t))})">
        <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${escapeHtml(t.date)}</td>
        <td>${escapeHtml(t.name)}</td>
        <td><span class="badge">${escapeHtml(t.category)}</span></td>
        <td style="text-align:right" class="amt-expense">${fmt(t.amount)}</td>
      </tr>`).join('')
    : '<tr><td colspan="4" class="empty">No transactions</td></tr>';
}

// ── SEARCH & TRANSACTIONS ─────────────────────────────────────────────────────
let searchTimer = null;
function onSearchInput() { clearTimeout(searchTimer); searchTimer = setTimeout(loadTransactions, 180); }
function clearSearch() { document.getElementById('search-input').value=''; loadTransactions(); }

async function loadTransactions() {
  const m = months[currentMonthIdx] || '';
  const typ = document.getElementById('filter-type')?.value || '';
  const cat = document.getElementById('filter-cat')?.value || '';
  const acct = document.getElementById('filter-account')?.value || '';
  const search = document.getElementById('search-input')?.value.trim() || '';
  const banner = document.getElementById('search-banner');
  const hiddenParam = showingHidden ? '&hidden=1' : '';
  const acctParam = acct ? `&account=${encodeURIComponent(acct)}` : '';

  const url = search
    ? `/api/transactions?search=${encodeURIComponent(search)}&type=${encodeURIComponent(typ)}${hiddenParam}&limit=50&offset=0`
    : `/api/transactions?month=${m}&type=${encodeURIComponent(typ)}&category=${encodeURIComponent(cat)}${acctParam}${hiddenParam}&limit=50&offset=0`;

  const data = await apiFetch(url);
  if (!data) return;
  const txns = data.transactions || data;
  const hasMore = data.has_more || false;
  const total = data.total || txns.length;
  const tbody = document.getElementById('all-txns');
  const empty = document.getElementById('txn-empty');
  const loadMoreBtn = document.getElementById('load-more-btn');

  // Store current query for "Load More"
  loadTransactions._lastUrl = url.replace(/&offset=\d+/, '').replace(/&limit=\d+/, '');
  loadTransactions._currentOffset = txns.length;

  if (search) {
    const expTotal = txns.reduce((s,t)=>t.type==='Expense'?s+t.amount:s,0);
    banner.style.display='block';
    banner.innerHTML = `${total} result${total!==1?'s':''} for "<strong>${escapeHtml(search)}</strong>"` +
      (expTotal>0?` &nbsp;·&nbsp; ${fmt(expTotal)} total`:'') +
      ` &nbsp;<span style="cursor:pointer;color:var(--accent)" onclick="clearSearch()">✕ clear</span>`;
  } else { banner.style.display='none'; }

  if (!txns.length) { tbody.innerHTML=''; empty.style.display='block'; empty.textContent = showingHidden ? 'No hidden transactions' : 'No transactions found'; if(loadMoreBtn) loadMoreBtn.style.display='none'; return; }
  empty.style.display='none';
  tbody.innerHTML = renderTxnRows(txns);
  if (loadMoreBtn) loadMoreBtn.style.display = hasMore ? '' : 'none';
  applyDemoToTransactions();
}

function renderTxnRows(txns) {
  return txns.map(t=>{
    const actionBtn = showingHidden
      ? `<button class="btn-ghost btn-sm" style="font-size:11px;padding:3px 8px" onclick="event.stopPropagation();unhideTx(${t.id})">Unhide</button>`
      : `<button class="del-btn" onclick="event.stopPropagation();deleteTx(${t.id})">×</button>`;
    return `<tr onclick="openEditModal(${escapeAttr(JSON.stringify(t))})" class="${selectedIds.has(t.id)?'selected':''}">
    <td><input type="checkbox" ${selectedIds.has(t.id)?'checked':''} onclick="event.stopPropagation();toggleSelect(${t.id},this)"></td>
    <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${escapeHtml(t.date)}</td>
    <td>${escapeHtml(t.name)}</td>
    <td><span class="badge">${escapeHtml(t.category)}</span></td>
    <td style="color:var(--muted);font-size:11px">${escapeHtml(t.account)}</td>
    <td><span class="badge ${escapeAttr(t.type.toLowerCase())}">${escapeHtml(t.type)}</span></td>
    <td style="text-align:right" class="${t.type==='Income'?'amt-income':'amt-expense'}">${fmt(t.amount)}</td>
    <td>${actionBtn}</td>
  </tr>`;
  }).join('');
}

async function loadMoreTransactions() {
  const offset = loadTransactions._currentOffset || 0;
  const baseUrl = loadTransactions._lastUrl || '';
  if (!baseUrl) return;
  const url = `${baseUrl}&limit=50&offset=${offset}`;
  const data = await apiFetch(url);
  if (!data) return;
  const txns = data.transactions || data;
  const hasMore = data.has_more || false;
  const tbody = document.getElementById('all-txns');
  const loadMoreBtn = document.getElementById('load-more-btn');
  tbody.innerHTML += renderTxnRows(txns);
  loadTransactions._currentOffset = offset + txns.length;
  if (loadMoreBtn) loadMoreBtn.style.display = hasMore ? '' : 'none';
}

async function deleteTx(id) {
  if (!confirm('Delete this transaction?')) return;
  await apiFetch(`/api/delete/${id}`, {method:'DELETE'});
  toast('Deleted','success'); showUndoButton(); renderMonth(); loadTransactions();
}
function filterByCat(cat) {
  nav('transactions');
  document.getElementById('filter-cat').value = cat;
  document.getElementById('filter-type').value = 'Expense';
  loadTransactions();
}
function populateCatFilter() {
  const sel = document.getElementById('filter-cat');
  const current = sel.value;
  sel.innerHTML = '<option value="">All</option>';
  [...EXPENSE_CATS,...INCOME_CATS].forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o);});
  if (current) sel.value = current;
}
async function populateAccountFilter() {
  const sel = document.getElementById('filter-account');
  if (!sel) return;
  const current = sel.value;
  const accounts = await apiFetch('/api/accounts') || [];
  sel.innerHTML = '<option value="">All Accounts</option>';
  accounts.forEach(a=>{const o=document.createElement('option');o.value=a;o.textContent=a;sel.appendChild(o);});
  if (current) sel.value = current;
  // Also populate account dropdowns in Add/Edit modals
  populateModalAccountDropdowns(accounts);
}

function populateModalAccountDropdowns(accounts) {
  const defaults = ['Cash', 'Other'];
  const allAccounts = [...new Set([...accounts, ...defaults])];
  ['f-account', 'e-account'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = allAccounts.map(a => `<option value="${escapeAttr(a)}">${escapeHtml(a)}</option>`).join('');
    if (current && allAccounts.includes(current)) sel.value = current;
  });
}

// ── BULK SELECTION ────────────────────────────────────────────────────────────
let selectedIds = new Set();
function toggleSelect(id, el) {
  if (selectedIds.has(id)) { selectedIds.delete(id); el.closest('tr').classList.remove('selected'); }
  else { selectedIds.add(id); el.closest('tr').classList.add('selected'); }
  updateBulkToolbar();
}
function updateBulkToolbar() {
  const bar = document.getElementById('bulk-toolbar');
  if (selectedIds.size > 0) { bar.style.display='flex'; document.getElementById('bulk-count').textContent=`${selectedIds.size} selected`; }
  else { bar.style.display='none'; }
}
function clearSelection() { selectedIds.clear(); document.querySelectorAll('#all-txns tr.selected').forEach(r=>r.classList.remove('selected')); updateBulkToolbar(); }
async function bulkDelete() {
  if (!confirm(`Delete ${selectedIds.size} transaction(s)?`)) return;
  await apiFetch('/api/bulk-delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids:[...selectedIds]})});
  toast(`Deleted ${selectedIds.size}`,'success'); showUndoButton(); clearSelection(); renderMonth(); loadTransactions();
}
async function bulkCategorize() {
  const sel = document.getElementById('bulk-cat-select');
  sel.innerHTML = EXPENSE_CATS.map(c=>`<option value="${escapeAttr(c)}">${escapeHtml(c)}</option>`).join('');
  document.getElementById('bulk-cat-modal').classList.add('open');
}
async function submitBulkCategorize() {
  const cat = document.getElementById('bulk-cat-select').value;
  if (!cat) return;
  closeModal('bulk-cat-modal');
  const res = await apiFetch('/api/bulk-categorize', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids:[...selectedIds], category:cat})});
  let msg = `Categorized ${selectedIds.size} → ${cat}`;
  if (res && res.learned) msg += ` · learned ${res.learned} merchant${res.learned===1?'':'s'}`;
  if (res && res.retro_fixed) msg += ` · fixed ${res.retro_fixed} other`;
  toast(msg,'success'); clearSelection(); renderMonth(); loadTransactions();
}
async function bulkHide() {
  const ids = [...selectedIds];
  await apiFetch('/api/bulk-hide', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids})});
  toast(`Hidden ${ids.length}`,'success');
  // Ask if user wants to create auto-hide rules for future imports
  const suggestions = await apiFetch('/api/suggest-hide-rules', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids})});
  clearSelection(); renderMonth(); loadTransactions(); updateHiddenCount();
  if (suggestions && suggestions.suggestions && suggestions.suggestions.length > 0) {
    showRuleSuggestionModal(suggestions.suggestions);
  }
}
async function bulkUnhide() {
  await apiFetch('/api/bulk-unhide', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids:[...selectedIds]})});
  toast(`Unhidden ${selectedIds.size}`,'success'); clearSelection(); renderMonth(); loadTransactions(); updateHiddenCount();
}

// ── RULE SUGGESTION MODAL ─────────────────────────────────────────────────────
function showRuleSuggestionModal(suggestions) {
  const list = document.getElementById('rule-suggest-list');
  list.innerHTML = suggestions.map((s, i) => `
    <label style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)">
      <input type="checkbox" checked data-idx="${i}" data-desc="${escapeAttr(s.description)}">
      <span style="flex:1;font-size:13px">${escapeHtml(s.description)}</span>
      <span style="font-size:11px;color:var(--muted)">${s.count} txn${s.count!==1?'s':''}</span>
    </label>
  `).join('');
  document.getElementById('rule-suggest-modal').classList.add('open');
}

async function submitRuleSuggestions() {
  const checkboxes = document.querySelectorAll('#rule-suggest-list input[type="checkbox"]:checked');
  if (checkboxes.length === 0) {
    closeModal('rule-suggest-modal');
    return;
  }
  const rules = [];
  checkboxes.forEach(cb => {
    const desc = cb.dataset.desc;
    rules.push({
      name: `Auto-hide: ${desc}`,
      action: 'hide',
      conditions: [{field: 'description', operator: 'contains', value: desc}],
    });
  });
  const res = await apiFetch('/api/rules/bulk-create', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rules})});
  closeModal('rule-suggest-modal');
  if (res && res.ok) {
    toast(`Created ${res.created} auto-hide rule${res.created!==1?'s':''}`, 'success');
  }
}

// ── YEAR VIEW ─────────────────────────────────────────────────────────────────
function changeYear(dir) { currentYear += dir; renderYear(); }
async function renderYear() {
  document.getElementById('year-display').textContent = currentYear;
  const data = await apiFetch(`/api/year/${currentYear}`);
  if (!data) return;
  const maxVal = Math.max(...data.months.map(m=>Math.max(m.income,m.expenses)), 1);

  document.getElementById('year-cards').innerHTML = `
    <div class="card"><div class="card-label">Total Income</div>
      <div class="card-value green">${fmt(data.total_income)}</div></div>
    <div class="card"><div class="card-label">Total Expenses</div>
      <div class="card-value red">${fmt(data.total_expenses)}</div></div>
    <div class="card"><div class="card-label">Net Saved</div>
      <div class="card-value ${data.total_income-data.total_expenses>=0?'green':'red'}">${fmt(data.total_income-data.total_expenses)}</div></div>`;

  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  document.getElementById('year-bars').innerHTML = data.months.map((m,i)=>`
    <div class="year-bar-row">
      <span class="year-month">${monthNames[i]}</span>
      <div class="year-bar-wrap">
        <div class="year-bar income" style="width:${(m.income/maxVal*100).toFixed(0)}%"></div>
        <div class="year-bar expense" style="width:${(m.expenses/maxVal*100).toFixed(0)}%"></div>
      </div>
      <div class="year-amounts">
        <span class="amt-income" style="font-size:11px">${m.income>0?fmt(m.income):''}</span>
        <span class="amt-expense" style="font-size:11px">${m.expenses>0?fmt(m.expenses):''}</span>
      </div>
    </div>`).join('');

  const maxCat = data.top_categories[0]?.total || 1;
  document.getElementById('year-cats').innerHTML = data.top_categories.length
    ? data.top_categories.map(c=>`
      <div class="cat-row">
        <span class="cat-name">${escapeHtml(c.category)}</span>
        <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/maxCat*100).toFixed(0)}%"></div></div>
        <span class="cat-amt">${fmt(c.total)}</span>
      </div>`).join('')
    : '<div class="empty">No data</div>';
}

// ── SETTINGS ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  renderCustomizeList('settings-panel-list');
  loadCategoryList();
  loadBudgets();
  loadLearned();
  loadRules();
  loadGoalsSettings();
  loadGroupsSettings();
  loadAccountsSettings();
  loadSchedulesSettings();
}

function renderCatRow(c) {
  const icon = c.icon ? `<span style="margin-right:4px">${c.icon}</span>` : '';
  const badge = c.user_created ? '<span style="font-size:9px;color:var(--accent);font-family:var(--mono);margin-left:6px">custom</span>' : '';
  return `<div class="settings-row" data-cat-id="${c.id}">
    <div style="display:flex;align-items:center;gap:6px;flex:1">
      ${icon}<span class="settings-label">${c.name}</span>${badge}
    </div>
    <div style="display:flex;gap:4px">
      <button class="btn-icon" onclick="renameCategory(${c.id},'${c.name.replace(/'/g,"\\'")}','${(c.icon||'').replace(/'/g,"\\'")}')">✏️</button>
      <button class="btn-icon" onclick="deleteCategory(${c.id},'${c.name.replace(/'/g,"\\'")}','${c.type}')">🗑️</button>
    </div>
  </div>`;
}

function loadCategoryList() {
  document.getElementById('expense-cat-list').innerHTML =
    ALL_CATEGORIES.filter(c=>c.type==='Expense').map(renderCatRow).join('')
    || '<div style="color:var(--muted);font-size:12px">No expense categories</div>';
  document.getElementById('income-cat-list').innerHTML =
    ALL_CATEGORIES.filter(c=>c.type==='Income').map(renderCatRow).join('')
    || '<div style="color:var(--muted);font-size:12px">No income categories</div>';
}

async function addCategory() {
  const name = document.getElementById('new-cat-name').value.trim();
  const icon = document.getElementById('new-cat-icon').value.trim();
  const type = document.getElementById('new-cat-type').value;
  if (!name) return toast('Enter a category name','error');
  const res = await apiFetch('/api/categories', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, type, icon})});
  if (!res) return;
  if (res.ok) {
    document.getElementById('new-cat-name').value = '';
    document.getElementById('new-cat-icon').value = '';
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Category added ✓','success');
  } else toast(res.error||'Error','error');
}

async function renameCategory(id, oldName, oldIcon) {
  const newName = prompt('Rename category:', oldName);
  if (!newName || newName.trim() === oldName) return;
  const newIcon = prompt('Icon (emoji, optional):', oldIcon) || '';
  const res = await apiFetch(`/api/categories/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name: newName.trim(), icon: newIcon.trim()})});
  if (!res) return;
  if (res.ok) {
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Renamed ✓','success');
  } else toast(res.error||'Error','error');
}

async function deleteCategory(id, name, type) {
  const res = await apiFetch(`/api/categories/${id}`, {method:'DELETE'});
  if (!res) return;
  if (res.error === 'in_use') {
    const sameCats = ALL_CATEGORIES.filter(c=>c.type===type && c.name!==name).map(c=>c.name);
    const target = prompt(`${res.count} transactions use "${name}".\nReassign them to which category?\n\nOptions: ${sameCats.join(', ')}`);
    if (!target) return;
    if (!sameCats.includes(target)) return toast('Invalid category','error');
    const res2 = await apiFetch(`/api/categories/${id}?reassign=${encodeURIComponent(target)}`, {method:'DELETE'});
    if (!res2) return;
    if (res2.ok) {
      await loadCategories();
      loadCategoryList();
      populateCatFilter();
      populateBudgetCat();
      toast(`Deleted & reassigned ${res2.reassigned} transactions ✓`,'success');
      if (months.length) renderMonth();
    } else toast(res2.error||'Error','error');
  } else if (res.ok) {
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Deleted ✓','success');
  } else toast(res.error||'Error','error');
}

async function loadBudgets() {
  const budgets = await apiFetch('/api/budgets') || [];
  document.getElementById('budget-list').innerHTML = budgets.length
    ? budgets.map(b=>`<div class="settings-row" id="budget-row-${escapeAttr(b.category)}">
        <div style="flex:1"><div class="settings-label">${escapeHtml(b.category)}</div>
          <div class="settings-sub">${fmt(b.monthly_limit)}/month</div></div>
        <div style="display:flex;gap:4px">
          <button class="btn-icon" onclick="startEditBudget('${escapeAttr(b.category)}',${b.monthly_limit})">✏️</button>
          <button class="btn-icon" onclick="deleteBudget('${escapeAttr(b.category)}')">🗑️</button>
        </div>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px;margin-bottom:8px">No budgets set</div>';
}

function startEditBudget(cat, currentAmt) {
  const row = document.getElementById('budget-row-' + cat);
  if (!row) return;
  row.innerHTML = `<div style="flex:1"><div class="settings-label">${escapeHtml(cat)}</div></div>
    <div style="display:flex;gap:6px;align-items:center">
      <input type="number" id="edit-budget-amt" value="${currentAmt}" style="width:90px" min="1" step="0.01"
        onkeydown="if(event.key==='Enter')saveEditBudget('${escapeAttr(cat)}');if(event.key==='Escape')loadBudgets()">
      <button class="btn btn-sm" onclick="saveEditBudget('${escapeAttr(cat)}')">Save</button>
      <button class="btn-icon" onclick="loadBudgets()">✕</button>
    </div>`;
  row.querySelector('#edit-budget-amt').focus();
}

async function saveEditBudget(cat) {
  const amt = document.getElementById('edit-budget-amt').value;
  if (!amt || parseFloat(amt) <= 0) return toast('Enter a valid amount','error');
  await apiFetch('/api/budgets', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({category: cat, amount: parseFloat(amt)})});
  loadBudgets(); toast('Budget updated ✓','success');
}

function populateBudgetCat() {
  const sel = document.getElementById('budget-cat');
  const current = sel.value;
  sel.innerHTML = '<option value="">Select category…</option>';
  EXPENSE_CATS.forEach(c=>{ if(c!=='UNCATEGORIZED'){ const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o); }});
  if (current) sel.value = current;
}

async function saveBudget() {
  const cat = document.getElementById('budget-cat').value;
  const amt = document.getElementById('budget-amt').value;
  if (!cat || !amt) return toast('Select category and amount','error');
  await apiFetch('/api/budgets', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({category:cat, amount:parseFloat(amt)})});
  document.getElementById('budget-amt').value='';
  loadBudgets(); toast('Budget set ✓','success');
}

async function deleteBudget(cat) {
  await apiFetch(`/api/budgets/${encodeURIComponent(cat)}`, {method:'DELETE'});
  loadBudgets(); toast('Removed','success');
}

async function loadLearned() {
  const rows = await apiFetch('/api/learned') || [];
  document.getElementById('learned-list').innerHTML = rows.length
    ? rows.map(r=>`<div class="settings-row">
        <div><div class="settings-label" style="font-family:var(--mono);font-size:12px">${escapeHtml(r.keyword)}</div>
          <div class="settings-sub">→ ${escapeHtml(r.category)}</div></div>
        <button class="btn btn-ghost btn-sm" onclick="deleteLearned('${escapeAttr(r.keyword)}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px">None yet — edit a transaction category to start learning</div>';
}

async function deleteLearned(keyword) {
  await apiFetch(`/api/learned/${encodeURIComponent(keyword)}`, {method:'DELETE'});
  loadLearned(); toast('Removed','success');
}

function showBudgetPanel() {
  nav('settings');
  switchSettingsTab('general');
  const el = document.getElementById('budget-panel');
  setTimeout(() => el.scrollIntoView({behavior:'smooth'}), 50);
}

// ── MODALS ────────────────────────────────────────────────────────────────────
function updateCatOptions(selId, typeId) {
  const type = document.getElementById(typeId).value;
  const sel = document.getElementById(selId);
  const cats = type === 'Income' ? INCOME_CATS : EXPENSE_CATS;
  sel.innerHTML = cats.map(c=>`<option value="${escapeAttr(c)}">${escapeHtml(c)}</option>`).join('');
}

function openAddModal() {
  if (isDemo) { toast('Adding transactions is disabled in demo mode', 'error'); return; }
  updateCatOptions('f-category','f-type');
  document.getElementById('add-modal').classList.add('open');
}

function openEditModal(t) {
  document.getElementById('e-id').value = t.id;
  document.getElementById('e-date').value = t.date;
  document.getElementById('e-type').value = t.type;
  document.getElementById('e-name').value = t.name;
  document.getElementById('e-amount').value = t.amount;
  document.getElementById('e-notes').value = t.notes || '';
  updateCatOptions('e-category','e-type');
  document.getElementById('e-category').value = t.category;
  // Ensure account is in the dropdown, then select it
  const acc = document.getElementById('e-account');
  let found = false;
  for (let o of acc.options) { if (o.value === t.account) { o.selected = true; found = true; break; } }
  if (!found) { const o = document.createElement('option'); o.value = t.account; o.textContent = t.account; acc.appendChild(o); acc.value = t.account; }
  document.getElementById('edit-modal').classList.add('open');
  document.getElementById('split-section').style.display = 'none';
  document.getElementById('split-btn').style.display = '';
  applyDemoToEditModal();
}

function closeModal(id) { document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.modal-backdrop').forEach(el=>
  el.addEventListener('click', e=>{ if(e.target===e.currentTarget) el.classList.remove('open'); }));

async function submitAdd() {
  const body = {
    date: document.getElementById('f-date').value,
    type: document.getElementById('f-type').value,
    name: document.getElementById('f-name').value.trim(),
    category: document.getElementById('f-category').value,
    amount: document.getElementById('f-amount').value,
    account: document.getElementById('f-account').value,
    notes: document.getElementById('f-notes').value.trim(),
  };
  if (!body.date||!body.name||!body.amount) return toast('Fill required fields','error');
  const data = await apiFetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  if (!data) return;
  if (data.ok) {
    toast('Added ✓','success'); closeModal('add-modal');
    months = await apiFetch('/api/months') || [];
    const idx = months.indexOf(body.date.slice(0,7)); if(idx!==-1) currentMonthIdx=idx;
    renderMonth();
    ['f-name','f-amount','f-notes'].forEach(id=>document.getElementById(id).value='');
  } else toast(data.error||'Error','error');
}

async function submitEdit() {
  const id = document.getElementById('e-id').value;
  const body = {
    date: document.getElementById('e-date').value,
    type: document.getElementById('e-type').value,
    name: document.getElementById('e-name').value.trim(),
    category: document.getElementById('e-category').value,
    amount: parseFloat(document.getElementById('e-amount').value),
    account: document.getElementById('e-account').value,
    notes: document.getElementById('e-notes').value.trim(),
  };
  const data = await apiFetch(`/api/update/${id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  if (!data) return;
  if (data.ok) {
    const extra = data.retro_fixed>0 ? ` · fixed ${data.retro_fixed} other${data.retro_fixed>1?'s':''}` : '';
    toast(`Saved ✓${extra}`,'success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
  } else toast(data.error||'Error','error');
}

async function deleteFromEdit() {
  if (!confirm('Delete this transaction?')) return;
  await apiFetch(`/api/delete/${document.getElementById('e-id').value}`, {method:'DELETE'});
  toast('Deleted','success'); showUndoButton(); closeModal('edit-modal'); renderMonth(); loadTransactions();
}

// ── IMPORT ────────────────────────────────────────────────────────────────────
let wizardState = {};

function handleDrop(e) {
  e.preventDefault(); document.getElementById('drop-zone').classList.remove('drag');
  handleFiles(e.dataTransfer.files);
}

function isStaleConfig(lastVerified) {
  if (!lastVerified) return false;
  const parts = lastVerified.split('-');
  const cfgDate = new Date(parseInt(parts[0]), parseInt(parts[1])-1, 1);
  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
  return cfgDate < sixMonthsAgo;
}

async function handleFiles(files) {
  if (!files.length) return;
  const unknownFiles = [];
  const knownFd = new FormData();
  let hasKnown = false;
  const ofxFd = new FormData();
  let hasOfx = false;

  // First pass: detect each file
  for (const f of files) {
    const ext = f.name.toLowerCase().split('.').pop();
    if (ext === 'ofx' || ext === 'qfx') {
      ofxFd.append('files', f);
      hasOfx = true;
      continue;
    }
    const detectFd = new FormData();
    detectFd.append('file', f);
    const det = await apiFetch('/api/detect-csv', {method:'POST', body:detectFd});
    if (!det) continue;
    if (det.detected) {
      knownFd.append('files', f);
      hasKnown = true;
    } else {
      unknownFiles.push({file: f, headers: det.headers, preview: det.preview, raw_text: det.raw_text});
    }
  }

  const allResults = [];

  // Import OFX files
  if (hasOfx) {
    const data = await apiFetch('/api/import-ofx', {method:'POST', body:ofxFd});
    if (data) allResults.push(...data);
  }

  // Import known CSV files normally
  if (hasKnown) {
    const data = await apiFetch('/api/import', {method:'POST', body:knownFd});
    if (data) allResults.push(...data);
  }

  if (allResults.length) {
    const resultsHtml = allResults.map(r => {
      const staleWarn = isStaleConfig(r.last_verified)
        ? `<div style="color:var(--amber);font-size:10px;font-family:var(--mono)">⚠ config last verified ${escapeHtml(r.last_verified)}</div>` : '';
      return `<div class="result-row">
        <div style="flex:1"><div>${escapeHtml(r.file)}</div><div class="result-bank">${escapeHtml(r.bank)}</div>${staleWarn}</div>
        <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
        <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
      </div>`;
    }).join('');
    document.getElementById('import-results').innerHTML = resultsHtml;
    months = await apiFetch('/api/months') || [];
    if (months.length) {
      currentMonthIdx=0; renderMonth();
      document.getElementById('empty-state').style.display = 'none';
      document.getElementById('dashboard-content').style.display = '';
    }
    toast(`Imported ${allResults.reduce((s,r)=>s+r.added,0)} transactions`,'success');
  }

  // Open wizard for the first unknown file
  if (unknownFiles.length) {
    openCsvWizard(unknownFiles[0]);
    // Queue remaining unknowns
    wizardState.queue = unknownFiles.slice(1);
  }
}

function openCsvWizard(info) {
  wizardState.headers = info.headers;
  wizardState.preview = info.preview;
  wizardState.raw_text = info.raw_text;
  wizardState.file = info.file;

  // Build preview table
  const table = document.getElementById('wizard-preview-table');
  const ths = info.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('');
  const rows = info.preview.map(r =>
    `<tr>${info.headers.map(h => `<td>${escapeHtml(r[h]||'')}</td>`).join('')}</tr>`
  ).join('');
  table.innerHTML = `<thead><tr>${ths}</tr></thead><tbody>${rows}</tbody>`;

  // Populate dropdowns
  const selects = ['wiz-date-col','wiz-desc-col','wiz-amt-col','wiz-debit-col','wiz-credit-col'];
  selects.forEach(id => {
    const sel = document.getElementById(id);
    sel.innerHTML = '<option value="">— select —</option>' +
      info.headers.map(h => `<option value="${escapeAttr(h)}">${escapeHtml(h)}</option>`).join('');
  });

  // Auto-guess columns
  let guessedDebit = false, guessedCredit = false;
  info.headers.forEach(h => {
    const hl = h.toLowerCase();
    if (hl.includes('date')) document.getElementById('wiz-date-col').value = h;
    if (hl.includes('description') || hl.includes('payee') || hl.includes('name'))
      document.getElementById('wiz-desc-col').value = h;
    if (hl === 'amount' || hl.includes('amount'))
      document.getElementById('wiz-amt-col').value = h;
    if (hl.includes('debit') || hl.includes('withdrawal'))
      { document.getElementById('wiz-debit-col').value = h; guessedDebit = true; }
    if (hl.includes('credit') || hl.includes('deposit'))
      { document.getElementById('wiz-credit-col').value = h; guessedCredit = true; }
  });

  // Auto-switch to split mode if both debit and credit columns were detected
  if (guessedDebit && guessedCredit) {
    document.getElementById('wiz-amt-mode').value = 'split';
    toggleAmountMode();
  }

  wizardStep(1);
  document.getElementById('csv-wizard-modal').classList.add('open');
}

function wizardStep(n) {
  [1,2,3].forEach(i => document.getElementById(`wizard-step-${i}`).style.display = i===n ? '' : 'none');
}

function toggleAmountMode() {
  const mode = document.getElementById('wiz-amt-mode').value;
  document.getElementById('wiz-single-amt').style.display = mode==='single' ? '' : 'none';
  document.getElementById('wiz-split-amt').style.display = mode==='split' ? '' : 'none';
}

async function wizardPreview() {
  const mapping = getWizardMapping();
  if (!mapping) return;
  const res = await apiFetch('/api/preview-parse', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({raw_text: wizardState.raw_text, mapping})
  });
  if (!res) return;
  const el = document.getElementById('wizard-preview-parsed');
  if (res.transactions && res.transactions.length) {
    el.innerHTML = `<div style="font-size:11px;color:var(--muted);margin-bottom:6px">
      ${res.total} transaction${res.total!==1?'s':''} found (showing first ${res.transactions.length})</div>` +
      res.transactions.map(t => `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span style="color:var(--muted);font-family:var(--mono);width:80px">${escapeHtml(t.date)}</span>
        <span style="flex:1">${escapeHtml(t.name)}</span>
        <span class="badge ${escapeAttr(t.type.toLowerCase())}">${escapeHtml(t.type)}</span>
        <span class="${t.type==='Income'?'amt-income':'amt-expense'}" style="font-family:var(--mono)">${fmt(t.amount)}</span>
      </div>`).join('');
  } else {
    el.innerHTML = '<div style="color:var(--red);font-size:12px">No transactions parsed — check column mapping</div>';
  }
}

function getWizardMapping() {
  const dateCol = document.getElementById('wiz-date-col').value;
  const descCol = document.getElementById('wiz-desc-col').value;
  const bankName = document.getElementById('wiz-bank-name').value.trim() || 'Unknown Bank';
  const dateFmt = document.getElementById('wiz-date-fmt').value;
  const amtMode = document.getElementById('wiz-amt-mode').value;
  if (!dateCol || !descCol) { toast('Select date and description columns','error'); return null; }
  const mapping = {date_column: dateCol, description_column: descCol,
    bank_name: bankName, date_format: dateFmt, amount_mode: amtMode};
  if (amtMode === 'single') {
    mapping.amount_column = document.getElementById('wiz-amt-col').value;
    mapping.amount_sign = 'standard';
    if (!mapping.amount_column) { toast('Select amount column','error'); return null; }
  } else {
    mapping.debit_column = document.getElementById('wiz-debit-col').value;
    mapping.credit_column = document.getElementById('wiz-credit-col').value;
    if (!mapping.debit_column || !mapping.credit_column) { toast('Select debit and credit columns','error'); return null; }
  }
  return mapping;
}

async function wizardSaveAndImport() {
  const mapping = getWizardMapping();
  if (!mapping) return;
  // Pick unique headers from the CSV for detection
  mapping.detection_headers = wizardState.headers.slice(0, 3);
  // Save config
  const saveRes = await apiFetch('/api/save-bank-config', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(mapping)});
  if (!saveRes || !saveRes.ok) { toast(saveRes?.error||'Error saving config','error'); return; }
  // Re-import the file using the new config
  const fd = new FormData();
  fd.append('files', wizardState.file);
  const data = await apiFetch('/api/import', {method:'POST', body:fd});
  if (!data) return;
  const prev = document.getElementById('import-results').innerHTML;
  document.getElementById('import-results').innerHTML = prev + data.map(r=>`
    <div class="result-row">
      <div style="flex:1"><div>${escapeHtml(r.file)}</div><div class="result-bank">${escapeHtml(r.bank)} <span style="color:var(--accent);font-size:10px">(new config)</span></div></div>
      <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
      <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
    </div>`).join('');
  closeModal('csv-wizard-modal');
  months = await apiFetch('/api/months') || [];
  if (months.length) {
    currentMonthIdx=0; renderMonth();
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('dashboard-content').style.display = '';
  }
  toast(`Config saved! Imported ${data.reduce((s,r)=>s+r.added,0)} transactions`,'success');
  // Process next unknown file in queue
  if (wizardState.queue && wizardState.queue.length) {
    setTimeout(() => openCsvWizard(wizardState.queue.shift()), 300);
  }
}

// ── IMPORT RULES UI ──────────────────────────────────────────────────────────
let showingHidden = false;

async function loadRules() {
  const rules = await apiFetch('/api/rules') || [];
  const el = document.getElementById('rules-list');
  if (!rules.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:12px;font-family:var(--mono)">No rules — add one or load a template</div>';
    return;
  }
  el.innerHTML = rules.map((r, idx) => {
    const opLabels = {contains:'contains', not_contains:'NOT contains', contains_any:'contains any of',
      equals:'equals', not_equals:'NOT equals', starts_with:'starts with', ends_with:'ends with',
      greater_than:'>', less_than:'<'};
    const condText = r.conditions.map(c =>
      `${escapeHtml(c.field)} ${opLabels[c.operator]||escapeHtml(c.operator)} "${escapeHtml(c.value)}"`
    ).join(' AND ');
    const enabledCheck = r.enabled ? 'checked' : '';
    let actionInfo = '';
    if (r.action === 'label' && r.action_value) {
      try { const v = JSON.parse(r.action_value); actionInfo = ` → ${escapeHtml(v.type||'')} / ${escapeHtml(v.category||'')}`; } catch(e) {}
    }
    return `<div class="rule-row" data-rule-id="${r.id}">
      <div class="rule-priority" style="display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0;min-width:28px">
        <button class="btn-icon btn-reorder" onclick="moveRule(${r.id},-1)" title="Move up" ${idx===0?'disabled':''}
          style="font-size:10px;padding:0;line-height:1;opacity:${idx===0?'.3':'1'}">▲</button>
        <span style="font-size:11px;font-family:var(--mono);color:var(--muted)">${idx+1}</span>
        <button class="btn-icon btn-reorder" onclick="moveRule(${r.id},1)" title="Move down" ${idx===rules.length-1?'disabled':''}
          style="font-size:10px;padding:0;line-height:1;opacity:${idx===rules.length-1?'.3':'1'}">▼</button>
      </div>
      <label class="toggle" style="flex-shrink:0">
        <input type="checkbox" ${enabledCheck} onchange="toggleRule(${r.id}, this.checked)">
        <span class="toggle-slider"></span>
      </label>
      <div class="rule-info">
        <div class="rule-name">${escapeHtml(r.name)}
          <span class="rule-action-badge ${escapeAttr(r.action)}">${escapeHtml(r.action)}</span>${actionInfo}
        </div>
        <div class="rule-conditions-summary">${condText}</div>
      </div>
      <button class="btn-icon" onclick='editRule(${escapeAttr(JSON.stringify(r))})'>✏️</button>
      <button class="btn-icon" onclick="deleteRule(${r.id})">🗑️</button>
    </div>`;
  }).join('');
}

async function toggleRule(id, enabled) {
  await apiFetch(`/api/rules/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({enabled: enabled ? 1 : 0})});
  toast(enabled ? 'Rule enabled' : 'Rule disabled', 'success');
}

async function deleteRule(id) {
  if (!confirm('Delete this rule?')) return;
  await apiFetch(`/api/rules/${id}`, {method:'DELETE'});
  loadRules();
  toast('Rule deleted', 'success');
}

async function moveRule(id, direction) {
  // Get current rule order from DOM
  const rows = [...document.querySelectorAll('#rules-list .rule-row')];
  const ids = rows.map(r => parseInt(r.dataset.ruleId));
  const idx = ids.indexOf(id);
  if (idx < 0) return;
  const newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= ids.length) return;
  // Swap
  [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
  await apiFetch('/api/rules/reorder', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({order: ids})});
  loadRules();
}

function openRuleModal(editData) {
  document.getElementById('rule-edit-id').value = editData ? editData.id : '';
  document.getElementById('rule-modal-title').textContent = editData ? 'Edit Import Rule' : 'Add Import Rule';
  document.getElementById('rule-name').value = editData ? editData.name : '';
  document.getElementById('rule-test-results').style.display = 'none';

  // Action
  const action = editData ? editData.action : 'hide';
  document.querySelectorAll('input[name="rule-action"]').forEach(r => r.checked = r.value === action);

  // Label fields
  if (editData && editData.action === 'label' && editData.action_value) {
    try {
      const v = JSON.parse(editData.action_value);
      document.getElementById('rule-label-type').value = v.type || 'Expense';
      updateRuleCatOptions();
      setTimeout(() => { document.getElementById('rule-label-category').value = v.category || ''; }, 50);
    } catch(e) {}
  } else {
    document.getElementById('rule-label-type').value = 'Expense';
    updateRuleCatOptions();
  }
  toggleLabelFields();

  // Conditions
  const condList = document.getElementById('rule-conditions-list');
  condList.innerHTML = '';
  if (editData && editData.conditions.length) {
    editData.conditions.forEach(c => addConditionRow(c.field, c.operator, c.value));
  } else {
    addConditionRow();
  }

  document.getElementById('rule-modal').classList.add('open');
}

function editRule(ruleData) {
  openRuleModal(ruleData);
}

function addConditionRow(field, operator, value) {
  const row = document.createElement('div');
  row.className = 'condition-row';
  row.innerHTML = `
    <select class="cond-field" onchange="updateOperatorOptions(this)" style="width:120px">
      <option value="description" ${field==='description'?'selected':''}>Description</option>
      <option value="amount" ${field==='amount'?'selected':''}>Amount</option>
      <option value="account" ${field==='account'?'selected':''}>Account</option>
      <option value="type" ${field==='type'?'selected':''}>Type</option>
    </select>
    <select class="cond-op" style="width:130px">
      <option value="contains" ${operator==='contains'?'selected':''}>contains</option>
      <option value="not_contains" ${operator==='not_contains'?'selected':''}>not contains</option>
      <option value="contains_any" ${operator==='contains_any'?'selected':''}>contains any</option>
      <option value="equals" ${operator==='equals'?'selected':''}>equals</option>
      <option value="not_equals" ${operator==='not_equals'?'selected':''}>not equals</option>
      <option value="starts_with" ${operator==='starts_with'?'selected':''}>starts with</option>
      <option value="ends_with" ${operator==='ends_with'?'selected':''}>ends with</option>
      <option value="greater_than" ${operator==='greater_than'?'selected':''}>greater than</option>
      <option value="less_than" ${operator==='less_than'?'selected':''}>less than</option>
    </select>
    <input type="text" class="cond-value" value="${(value||'').replace(/"/g,'&quot;')}" placeholder="value (case-insensitive)" style="flex:1;min-width:100px">
    <button class="btn-icon" onclick="this.parentElement.remove()" style="color:var(--red)">×</button>`;
  document.getElementById('rule-conditions-list').appendChild(row);
  if (field) updateOperatorOptions(row.querySelector('.cond-field'));
  // Update placeholder based on operator
  const opSelect = row.querySelector('.cond-op');
  opSelect.addEventListener('change', () => updateCondPlaceholder(row));
  updateCondPlaceholder(row);
}

function updateCondPlaceholder(row) {
  const op = row.querySelector('.cond-op').value;
  const input = row.querySelector('.cond-value');
  if (op === 'contains_any') input.placeholder = 'comma-separated, e.g. vaibhav, jonas';
  else input.placeholder = 'value (case-insensitive)';
}

function updateOperatorOptions(fieldSelect) {
  const opSelect = fieldSelect.parentElement.querySelector('.cond-op');
  const val = fieldSelect.value;
  const current = opSelect.value;
  if (val === 'amount') {
    opSelect.innerHTML = `
      <option value="equals">equals</option>
      <option value="greater_than">greater than</option>
      <option value="less_than">less than</option>`;
  } else {
    opSelect.innerHTML = `
      <option value="contains">contains</option>
      <option value="not_contains">not contains</option>
      <option value="contains_any">contains any</option>
      <option value="equals">equals</option>
      <option value="not_equals">not equals</option>
      <option value="starts_with">starts with</option>
      <option value="ends_with">ends with</option>`;
  }
  if ([...opSelect.options].some(o => o.value === current)) opSelect.value = current;
  updateCondPlaceholder(fieldSelect.closest('.condition-row'));
}

function toggleLabelFields() {
  const action = document.querySelector('input[name="rule-action"]:checked')?.value;
  const fields = document.getElementById('rule-label-fields');
  fields.style.display = action === 'label' ? 'flex' : 'none';
}

function updateRuleCatOptions() {
  const type = document.getElementById('rule-label-type').value;
  const sel = document.getElementById('rule-label-category');
  const cats = type === 'Income' ? INCOME_CATS : EXPENSE_CATS;
  sel.innerHTML = cats.filter(c => c !== 'UNCATEGORIZED').map(c => `<option value="${escapeAttr(c)}">${escapeHtml(c)}</option>`).join('');
}

function getRuleFormData() {
  const name = document.getElementById('rule-name').value.trim();
  if (!name) { toast('Enter a rule name', 'error'); return null; }
  const conditions = [];
  document.querySelectorAll('#rule-conditions-list .condition-row').forEach(row => {
    const field = row.querySelector('.cond-field').value;
    const operator = row.querySelector('.cond-op').value;
    const value = row.querySelector('.cond-value').value.trim();
    if (value) conditions.push({field, operator, value});
  });
  if (!conditions.length) { toast('Add at least one condition', 'error'); return null; }
  const action = document.querySelector('input[name="rule-action"]:checked')?.value || 'hide';
  let action_value = '';
  if (action === 'label') {
    action_value = JSON.stringify({
      type: document.getElementById('rule-label-type').value,
      category: document.getElementById('rule-label-category').value,
    });
  }
  return {name, action, action_value, conditions};
}

async function saveRule() {
  const data = getRuleFormData();
  if (!data) return;
  const editId = document.getElementById('rule-edit-id').value;
  if (editId) {
    const res = await apiFetch(`/api/rules/${editId}`, {method:'PATCH',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    if (!res) return;
    if (res.ok) { toast('Rule updated ✓', 'success'); closeModal('rule-modal'); loadRules(); }
    else toast(res.error||'Error', 'error');
  } else {
    const res = await apiFetch('/api/rules', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    if (!res) return;
    if (res.ok) { toast('Rule created ✓', 'success'); closeModal('rule-modal'); loadRules(); }
    else toast(res.error||'Error', 'error');
  }
}

async function testRule() {
  const data = getRuleFormData();
  if (!data) return;
  const res = await apiFetch('/api/rules/test', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  if (!res) return;
  const el = document.getElementById('rule-test-results');
  el.style.display = 'block';
  if (res.count === 0) {
    el.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:8px 0">No existing transactions match this rule.</div>';
    return;
  }
  el.innerHTML = `<div style="font-size:12px;color:var(--accent);margin-bottom:8px;font-family:var(--mono)">
    This rule would affect ${res.count} transaction${res.count!==1?'s':''}</div>` +
    res.transactions.map(t => `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:11px">
      <span style="color:var(--muted);font-family:var(--mono);width:75px;flex-shrink:0">${escapeHtml(t.date)}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(t.name)}</span>
      <span class="badge ${escapeAttr(t.type.toLowerCase())}" style="font-size:10px">${escapeHtml(t.type)}</span>
      <span style="font-family:var(--mono);width:70px;text-align:right">${fmt(t.amount)}</span>
    </div>`).join('');
}

async function applyAllRules() {
  if (!confirm('Apply all enabled rules to every existing transaction? This will hide/label matching transactions.')) return;
  const res = await apiFetch('/api/rules/apply-all', {method:'POST'});
  if (!res) return;
  toast(`Rules applied — ${res.affected} transaction${res.affected!==1?'s':''} affected`, 'success');
  if (res.affected > 0 && months.length) renderMonth();
  updateHiddenCount();
}

async function openTemplateModal() {
  document.getElementById('template-modal').classList.add('open');
  const templates = await apiFetch('/api/rule-templates') || [];
  const el = document.getElementById('template-list');
  if (!templates.length) {
    el.innerHTML = '<div class="empty">No templates found</div>';
    return;
  }
  el.innerHTML = templates.map(t => `<div class="settings-row">
    <div style="flex:1">
      <div class="settings-label">${escapeHtml(t.name)}</div>
      <div class="settings-sub">${escapeHtml(t.description)} · ${t.rule_count} rule${t.rule_count!==1?'s':''}</div>
    </div>
    <button class="btn btn-sm" onclick="loadTemplate('${escapeAttr(t.file)}', '${escapeAttr(t.name)}', ${t.rule_count})">Load</button>
  </div>`).join('');
}

async function loadTemplate(file, name, count) {
  if (!confirm(`Load "${name}"? This will add ${count} rule${count!==1?'s':''} to your list. Existing rules are not affected.`)) return;
  const res = await apiFetch('/api/rule-templates/load', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({file})});
  if (!res) return;
  if (res.ok) {
    toast(`Loaded ${res.loaded} rule${res.loaded!==1?'s':''} from ${name} ✓`, 'success');
    closeModal('template-modal');
    loadRules();
  } else toast(res.error||'Error', 'error');
}

// ── HIDDEN TRANSACTIONS ──────────────────────────────────────────────────────

async function updateHiddenCount() {
  const res = await apiFetch('/api/transactions/hidden-count');
  if (!res) return;
  const badge = document.getElementById('hidden-count-badge');
  const btn = document.getElementById('hidden-toggle');
  badge.textContent = res.count;
  btn.style.display = res.count > 0 ? '' : 'none';
  if (res.count === 0 && showingHidden) toggleHiddenView();
}

function toggleHiddenView() {
  showingHidden = !showingHidden;
  clearSelection();
  const btn = document.getElementById('hidden-toggle');
  const title = document.querySelector('#sec-transactions .txn-title');
  const hideBtn = document.getElementById('bulk-hide-btn');
  const unhideBtn = document.getElementById('bulk-unhide-btn');
  if (showingHidden) {
    btn.classList.remove('btn-ghost');
    btn.style.background = 'rgba(248,113,113,.15)';
    btn.style.borderColor = 'rgba(248,113,113,.3)';
    btn.style.color = 'var(--red)';
    title.textContent = 'Hidden Transactions';
    hideBtn.style.display = 'none';
    unhideBtn.style.display = '';
  } else {
    btn.classList.add('btn-ghost');
    btn.style.background = '';
    btn.style.borderColor = '';
    btn.style.color = '';
    title.textContent = 'All Transactions';
    hideBtn.style.display = '';
    unhideBtn.style.display = 'none';
  }
  loadTransactions();
}

async function unhideTx(id) {
  await apiFetch(`/api/transactions/${id}/unhide`, {method:'PATCH'});
  toast('Transaction unhidden ✓', 'success');
  loadTransactions();
  updateHiddenCount();
  if (months.length) renderMonth();
}

async function hideTx(id) {
  await apiFetch(`/api/transactions/${id}/hide`, {method:'PATCH'});
  toast('Transaction hidden ✓', 'success');
  loadTransactions();
  updateHiddenCount();
  if (months.length) renderMonth();
}

// ── NAV ───────────────────────────────────────────────────────────────────────
function nav(id) {
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(`sec-${id}`).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b=>{
    if (b.getAttribute('onclick')?.includes(`'${id}'`)) b.classList.add('active');
  });
  if (window.innerWidth <= 768) closeMobileMenu();
  if (id==='dashboard' && document.getElementById('empty-state').style.display !== 'none') refreshDashboard();
  if (id==='transactions') { loadTransactions(); setTimeout(applyDemoToTransactions, 100); }
  if (id==='year') renderYear();
  if (id==='settings') { loadSettings(); setTimeout(applyDemoToSettings, 200); }
  if (id==='import') applyDemoToImport();
}

// ── SETTINGS TABS ─────────────────────────────────────────────────────────────
function switchSettingsTab(tabName) {
  document.querySelectorAll('.settings-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
  document.querySelectorAll('.settings-tab-pane').forEach(p => p.classList.toggle('active', p.dataset.tabPane === tabName));
}

async function refreshDashboard() {
  months = await apiFetch('/api/months') || [];
  if (months.length) {
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('dashboard-content').style.display = '';
    applyDashboardLayout();
    initCollapsiblePanels();
    currentMonthIdx = 0;
    renderMonth();
  }
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function exportCSV(allTime) {
  const m = allTime ? '' : (months[currentMonthIdx]||'');
  window.location.href = `/api/export?month=${m}`;
  toast(`Downloading ${allTime?'all transactions':fmtMonth(m)} ✓`,'success');
}

// ── UNIFIED EXPORT MODAL ──────────────────────────────────────────────────────
function openExportModal() {
  document.getElementById('export-format').value = 'csv';
  document.getElementById('export-scope').value = 'month';
  document.getElementById('export-pdf-options').style.display = 'none';
  document.getElementById('export-include-txns').checked = false;
  document.getElementById('export-modal').classList.add('open');
}

function onExportFormatChange() {
  const fmt = document.getElementById('export-format').value;
  document.getElementById('export-pdf-options').style.display = fmt === 'pdf' ? '' : 'none';
}

function doExport() {
  const fmt = document.getElementById('export-format').value;
  const scope = document.getElementById('export-scope').value;
  closeModal('export-modal');
  if (fmt === 'csv') {
    exportCSV(scope === 'all');
  } else {
    document.getElementById('pdf-include-txns').checked = document.getElementById('export-include-txns').checked;
    exportPdf();
  }
}

// ── QUICK ACTIONS POPOVER ─────────────────────────────────────────────────────
function toggleQuickActions(e) {
  if (e) e.stopPropagation();
  const pop = document.getElementById('quick-actions-popover');
  const isOpen = pop.classList.contains('open');
  closeQuickActions();
  closeMonthMenu();
  if (!isOpen) {
    const btn = document.getElementById('quick-actions-btn');
    const rect = btn.getBoundingClientRect();
    pop.style.left = (rect.right + 8) + 'px';
    pop.style.top = rect.top + 'px';
    pop.classList.add('open');
  }
}

function closeQuickActions() {
  const pop = document.getElementById('quick-actions-popover');
  if (pop) pop.classList.remove('open');
}

// ── MONTH CONTEXT MENU ───────────────────────────────────────────────────────
function toggleMonthMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('month-menu');
  const isOpen = menu.classList.contains('open');
  closeMonthMenu();
  closeQuickActions();
  if (!isOpen) menu.classList.add('open');
}

function closeMonthMenu() {
  const menu = document.getElementById('month-menu');
  if (menu) menu.classList.remove('open');
}

// Close popovers on outside click
document.addEventListener('click', () => { closeQuickActions(); closeMonthMenu(); });

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg, type='success') {
  const el = document.getElementById('toast');
  el.textContent=msg; el.className=`toast ${type} show`;
  setTimeout(()=>el.classList.remove('show'), 2800);
}

// ── MOBILE MENU ───────────────────────────────────────────────────────────────
function toggleMobileMenu() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    closeMobileMenu();
  } else {
    sidebar.classList.add('open');
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

function closeMobileMenu() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  sidebar.classList.remove('open');
  overlay.classList.remove('open');
  document.body.style.overflow = '';
}

// Close mobile menu when a nav button is clicked
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (window.innerWidth <= 768) closeMobileMenu();
  });
});

// Close mobile menu on resize to desktop
window.addEventListener('resize', () => {
  if (window.innerWidth > 768) closeMobileMenu();
});

// ── BUDGET ALERTS ─────────────────────────────────────────────────────────────
function renderBudgetAlerts(cats) {
  const el = document.getElementById('budget-alerts');
  const alerts = cats.filter(c => c.budget && c.total >= c.budget * 0.8);
  if (!alerts.length) { el.style.display = 'none'; return; }
  el.style.display = '';
  el.innerHTML = alerts.map(c => {
    const pct = Math.round(c.total / c.budget * 100);
    const barPct = Math.min(pct, 100);
    const cls = pct >= 100 ? 'danger' : 'warning';
    return `<div class="budget-alert-item ${cls}">
      <span class="budget-alert-dot"></span>
      <span class="budget-alert-name">${escapeHtml(c.category)}</span>
      <span style="color:var(--muted);font-size:11px">${fmt(c.total)} / ${fmt(c.budget)}</span>
      <div class="budget-alert-bar"><div class="budget-alert-bar-fill" style="width:${barPct}%"></div></div>
      <span class="budget-alert-pct">${pct}%</span>
    </div>`;
  }).join('');
}

// ── SPENDING TRENDS ───────────────────────────────────────────────────────────
let trendsChart = null;
async function renderTrends() {
  const data = await apiFetch('/api/trends?months=6');
  if (!data || !data.length) return;
  const ctx = document.getElementById('trends-chart').getContext('2d');
  if (trendsChart) trendsChart.destroy();
  trendsChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => fmtMonth(d.month)),
      datasets: [
        { label: 'Income', data: data.map(d => d.income), backgroundColor: '#6ee7b7' },
        { label: 'Expenses', data: data.map(d => d.expenses), backgroundColor: '#f87171' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, ticks: { callback: v => '$' + v.toLocaleString() } } },
      plugins: { legend: { position: 'bottom' } },
    }
  });
}

// ── SAVINGS GOALS (Dashboard) ─────────────────────────────────────────────────
async function renderGoalsDashboard() {
  const goals = await apiFetch('/api/goals');
  const el = document.getElementById('goals-dashboard-list');
  if (!goals || !goals.length) { el.innerHTML = '<div class="empty">No goals set</div>'; return; }
  el.innerHTML = goals.map(g => {
    const pct = Math.min(100, Math.round(g.current_amount / g.target_amount * 100));
    const cls = pct >= 100 ? 'complete' : '';
    return `<div class="goal-card">
      <div class="goal-header">
        <span class="goal-name">${escapeHtml(g.icon)} ${escapeHtml(g.name)}</span>
        <span class="goal-amounts">${fmt(g.current_amount)} / ${fmt(g.target_amount)} (${pct}%)</span>
      </div>
      <div class="goal-bar-bg"><div class="goal-bar-fill ${cls}" style="width:${pct}%"></div></div>
      <div class="goal-actions">
        <button class="btn btn-ghost btn-sm" onclick="openContributeModal(${g.id})">+ Add</button>
      </div>
    </div>`;
  }).join('');
}

function openContributeModal(gid) {
  document.getElementById('contribute-goal-id').value = gid;
  document.getElementById('contribute-amount').value = '';
  document.getElementById('contribute-modal').classList.add('open');
}

async function submitContribute() {
  const gid = document.getElementById('contribute-goal-id').value;
  const amount = document.getElementById('contribute-amount').value;
  if (!amount || parseFloat(amount) <= 0) return toast('Enter an amount','error');
  const res = await apiFetch(`/api/goals/${gid}/contribute`, {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({amount: parseFloat(amount)})});
  if (res && res.ok) {
    closeModal('contribute-modal');
    renderGoalsDashboard();
    loadGoalsSettings();
    toast('Contribution added ✓','success');
  }
}

// ── SAVINGS GOALS (Settings) ──────────────────────────────────────────────────
async function loadGoalsSettings() {
  const goals = await apiFetch('/api/goals');
  const el = document.getElementById('goals-settings-list');
  if (!goals || !goals.length) { el.innerHTML = '<div style="color:var(--muted);font-size:12px">No goals yet</div>'; return; }
  el.innerHTML = goals.map(g => {
    const pct = Math.min(100, Math.round(g.current_amount / g.target_amount * 100));
    return `<div class="settings-row" id="goal-row-${g.id}">
      <div style="display:flex;align-items:center;gap:6px;flex:1">
        <span>${escapeHtml(g.icon)}</span>
        <span class="settings-label">${escapeHtml(g.name)}</span>
        <span style="font-size:11px;color:var(--muted)">${fmt(g.current_amount)}/${fmt(g.target_amount)} (${pct}%)</span>
      </div>
      <div style="display:flex;gap:4px">
        <button class="btn-icon" onclick="startEditGoal(${g.id},'${escapeAttr(g.name)}',${g.target_amount},${g.current_amount},'${escapeAttr(g.icon)}')">✏️</button>
        <button class="btn-icon" onclick="deleteGoal(${g.id})">🗑️</button>
      </div>
    </div>`;
  }).join('');
}

function startEditGoal(id, name, target, current, icon) {
  const row = document.getElementById('goal-row-' + id);
  if (!row) return;
  row.innerHTML = `<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1">
      <input type="text" id="edit-goal-icon" value="${escapeAttr(icon)}" style="width:42px;text-align:center" maxlength="2">
      <input type="text" id="edit-goal-name" value="${escapeAttr(name)}" style="flex:1;min-width:90px" placeholder="Name">
      <input type="number" id="edit-goal-target" value="${target}" style="width:90px" min="1" step="0.01" placeholder="Target">
      <input type="number" id="edit-goal-current" value="${current}" style="width:90px" min="0" step="0.01" placeholder="Saved">
      <button class="btn btn-sm" onclick="saveEditGoal(${id})">Save</button>
      <button class="btn-icon" onclick="loadGoalsSettings()">✕</button>
    </div>`;
  row.querySelector('#edit-goal-name').focus();
}

async function saveEditGoal(id) {
  const name = document.getElementById('edit-goal-name').value.trim();
  const target = document.getElementById('edit-goal-target').value;
  const current = document.getElementById('edit-goal-current').value;
  const icon = document.getElementById('edit-goal-icon').value.trim() || '🎯';
  if (!name) return toast('Enter a goal name','error');
  if (!target || parseFloat(target) <= 0) return toast('Enter a valid target','error');
  const res = await apiFetch(`/api/goals/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, target_amount: parseFloat(target), current_amount: parseFloat(current || 0), icon})});
  if (res && res.ok) { loadGoalsSettings(); renderGoalsDashboard(); toast('Goal updated ✓','success'); }
}

async function addGoal() {
  const name = document.getElementById('new-goal-name').value.trim();
  const target = document.getElementById('new-goal-target').value;
  const icon = document.getElementById('new-goal-icon').value.trim() || '🎯';
  if (!name) return toast('Enter a goal name','error');
  if (!target || parseFloat(target) <= 0) return toast('Enter a valid target','error');
  const res = await apiFetch('/api/goals', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, target_amount: parseFloat(target), icon})});
  if (res && res.ok) {
    document.getElementById('new-goal-name').value = '';
    document.getElementById('new-goal-target').value = '';
    document.getElementById('new-goal-icon').value = '';
    loadGoalsSettings();
    renderGoalsDashboard();
    toast('Goal added ✓','success');
  }
}

async function deleteGoal(id) {
  if (!confirm('Delete this goal?')) return;
  const res = await apiFetch(`/api/goals/${id}`, {method:'DELETE'});
  if (res && res.ok) {
    loadGoalsSettings();
    renderGoalsDashboard();
    toast('Goal deleted ✓','success');
  }
}

function showGoalsPanel() {
  nav('settings');
  switchSettingsTab('accounts');
  const el = document.getElementById('goals-panel');
  if (el) setTimeout(() => el.scrollIntoView({behavior:'smooth'}), 50);
}

// ── CATEGORY GROUPS (Settings) ────────────────────────────────────────────────
async function loadGroupsSettings() {
  const groups = await apiFetch('/api/category-groups');
  const el = document.getElementById('groups-settings-list');
  if (!groups || !groups.length) { el.innerHTML = '<div style="color:var(--muted);font-size:12px">No groups</div>'; return; }
  const allGroups = groups.filter(g => g.id !== null);
  const groupOptions = allGroups.map(g => ({id: g.id, name: g.name}));
  el.innerHTML = groups.filter(g => g.id !== null).map(g => `
    <div class="group-block">
      <div class="group-block-header">
        <span>${escapeHtml(g.name)} <span style="font-weight:400;font-size:11px;color:var(--muted)">(${g.categories.length})</span></span>
        <div style="display:flex;gap:4px">
          <button class="btn-icon" onclick="renameGroup(${g.id},'${escapeAttr(g.name)}')">✏️</button>
          <button class="btn-icon" onclick="deleteGroup(${g.id})">🗑️</button>
        </div>
      </div>
      ${g.categories.length ? g.categories.map(c => `<div class="group-cat-item">
        <span class="group-cat-name">• ${escapeHtml(c.name)}</span>
        <select class="group-reassign-select" onchange="reassignCategory(${c.id},this.value)">
          ${groupOptions.map(go => `<option value="${go.id}"${go.id===g.id?' selected':''}>${escapeHtml(go.name)}</option>`).join('')}
          <option value=""${g.id===null?' selected':''}>Ungrouped</option>
        </select>
      </div>`).join('') : '<div style="font-size:11px;color:var(--muted);padding:4px 0">No categories in this group</div>'}
    </div>
  `).join('');
  // Show ungrouped categories if any
  const ungrouped = groups.find(g => g.id === null);
  if (ungrouped && ungrouped.categories.length) {
    el.innerHTML += `<div class="group-block" style="border-style:dashed">
      <div class="group-block-header"><span>Ungrouped <span style="font-weight:400;font-size:11px;color:var(--muted)">(${ungrouped.categories.length})</span></span></div>
      ${ungrouped.categories.map(c => `<div class="group-cat-item">
        <span class="group-cat-name">• ${escapeHtml(c.name)}</span>
        <select class="group-reassign-select" onchange="reassignCategory(${c.id},this.value)">
          ${groupOptions.map(go => `<option value="${go.id}">${escapeHtml(go.name)}</option>`).join('')}
          <option value="" selected>Ungrouped</option>
        </select>
      </div>`).join('')}
    </div>`;
  }
}

async function addGroup() {
  const name = document.getElementById('new-group-name').value.trim();
  if (!name) return toast('Enter a group name','error');
  const res = await apiFetch('/api/category-groups', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
  if (res && res.ok) {
    document.getElementById('new-group-name').value = '';
    loadGroupsSettings();
    toast('Group added ✓','success');
  }
}

async function reassignCategory(catId, groupId) {
  const body = {group_id: groupId === '' ? null : parseInt(groupId)};
  const res = await apiFetch(`/api/categories/${catId}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (res && res.ok) { loadGroupsSettings(); toast('Category moved ✓','success'); }
}

async function renameGroup(id, oldName) {
  const name = prompt('Rename group:', oldName);
  if (!name || name.trim() === oldName) return;
  const res = await apiFetch(`/api/category-groups/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: name.trim()})});
  if (res && res.ok) { loadGroupsSettings(); toast('Group renamed ✓','success'); }
}

async function deleteGroup(id) {
  if (!confirm('Delete this group? Categories will become ungrouped.')) return;
  const res = await apiFetch(`/api/category-groups/${id}`, {method:'DELETE'});
  if (res && res.ok) { loadGroupsSettings(); toast('Group deleted ✓','success'); }
}

// ── SPLIT TRANSACTIONS ───────────────────────────────────────────────────────
function openSplitUI() {
  const amount = parseFloat(document.getElementById('e-amount').value) || 0;
  document.getElementById('split-section').style.display = '';
  document.getElementById('split-btn').style.display = 'none';
  const rows = document.getElementById('split-rows');
  rows.innerHTML = '';
  addSplitRow(Math.round(amount / 2 * 100) / 100);
  addSplitRow(Math.round((amount - Math.round(amount / 2 * 100) / 100) * 100) / 100);
  updateSplitRemaining();
}

function closeSplitUI() {
  document.getElementById('split-section').style.display = 'none';
  document.getElementById('split-btn').style.display = '';
}

function addSplitRow(prefillAmt) {
  const row = document.createElement('div');
  row.className = 'split-row';
  const type = document.getElementById('e-type').value;
  const cats = type === 'Income' ? INCOME_CATS : EXPENSE_CATS;
  row.innerHTML = `
    <select class="split-cat">${cats.map(c => `<option value="${escapeAttr(c)}">${escapeHtml(c)}</option>`).join('')}</select>
    <input type="number" class="split-amt" step="0.01" min="0" value="${prefillAmt||''}" placeholder="0.00" oninput="updateSplitRemaining()">
    <button class="btn-icon" onclick="this.closest('.split-row').remove();updateSplitRemaining()">✕</button>
  `;
  document.getElementById('split-rows').appendChild(row);
}

function updateSplitRemaining() {
  const total = parseFloat(document.getElementById('e-amount').value) || 0;
  const splits = [...document.querySelectorAll('.split-amt')].map(i => parseFloat(i.value) || 0);
  const sum = splits.reduce((a, b) => a + b, 0);
  const remaining = Math.round((total - sum) * 100) / 100;
  const el = document.getElementById('split-remaining');
  el.textContent = remaining === 0 ? '✓ Balanced' : `Remaining: ${fmt(remaining)}`;
  el.style.color = remaining === 0 ? 'var(--accent)' : 'var(--red)';
}

async function submitSplit() {
  const tid = document.getElementById('e-id').value;
  const rows = document.querySelectorAll('.split-row');
  const splits = [...rows].map(r => ({
    category: r.querySelector('.split-cat').value,
    amount: parseFloat(r.querySelector('.split-amt').value) || 0,
  }));
  if (splits.length < 2) return toast('Need at least 2 split rows','error');
  const res = await apiFetch(`/api/transactions/${tid}/split`, {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({splits})});
  if (res && res.ok) {
    closeModal('edit-modal');
    toast(`Split into ${res.children} parts ✓`,'success');
    if (months.length) renderMonth();
    loadTransactions();
  }
}

// ── PDF EXPORT ────────────────────────────────────────────────────────────────
function openPdfModal() {
  document.getElementById('pdf-modal').classList.add('open');
}

function exportPdf() {
  if (!months.length) return toast('No data to export','error');
  const m = months[currentMonthIdx];
  const incTxns = document.getElementById('pdf-include-txns').checked ? '1' : '0';
  window.open(`/api/export/pdf?month=${m}&include_transactions=${incTxns}`, '_blank');
  closeModal('pdf-modal');
  toast('PDF downloading…','success');
}

// ── QUICK ACTIONS & MONTH MENU ────────────────────────────────────────────────
// Removed — sidebar buttons replaced these popover menus.

// Click-outside listener (safe with null checks)
document.addEventListener('click', function(e) {
  const wrap = document.querySelector('.quick-actions-wrap');
  if (wrap && !wrap.contains(e.target)) wrap.classList.remove('open');
  const menuWrap = document.querySelector('.month-menu-wrap');
  if (menuWrap && !menuWrap.contains(e.target)) menuWrap.classList.remove('open');
});

// ── NET WORTH ─────────────────────────────────────────────────────────────────
let netWorthChart = null;

async function renderNetWorth() {
  const data = await apiFetch('/api/net-worth');
  const wrapper = document.querySelector('[data-panel-id="net-worth"] .chart-wrap') ||
                  document.getElementById('net-worth-chart')?.parentNode;
  if (!data || !data.length) {
    if (wrapper) wrapper.innerHTML = '<div class="empty">Add accounts in Settings to see net worth</div>';
    return;
  }
  // Ensure canvas exists (may have been replaced by empty message)
  if (wrapper && !document.getElementById('net-worth-chart')) {
    wrapper.innerHTML = '<canvas id="net-worth-chart"></canvas>';
  }
  const ctx = document.getElementById('net-worth-chart');
  if (!ctx) return;
  if (netWorthChart) netWorthChart.destroy();
  netWorthChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => fmtMonth(d.month)),
      datasets: [{
        label: 'Net Worth',
        data: data.map(d => d.net_worth),
        borderColor: '#6ee7b7',
        backgroundColor: 'rgba(110,231,183,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: {legend:{display:false}},
      scales: {y:{ticks:{callback:v=>'$'+v.toLocaleString()}}},
    },
  });
}

// ── ACCOUNT BALANCES ──────────────────────────────────────────────────────────
async function renderAccountBalances() {
  const data = await apiFetch('/api/accounts-list');
  const el = document.getElementById('account-balances-list');
  if (!el) return;
  if (!data || !data.length) {
    el.innerHTML = '<div class="empty">Add accounts in Settings to track balances</div>';
    return;
  }
  const total = data.reduce((s,a) => s + a.balance, 0);
  el.innerHTML = data.map(a => {
    const color = a.balance >= 0 ? 'var(--accent)' : 'var(--red)';
    const typeLabel = a.account_type.charAt(0).toUpperCase() + a.account_type.slice(1);
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border)">
      <div><strong>${escapeHtml(a.name)}</strong> <span style="font-size:10px;color:var(--muted)">${escapeHtml(typeLabel)}</span></div>
      <div style="font-family:var(--mono);color:${color}">${fmt(a.balance)}</div>
    </div>`;
  }).join('') + `<div style="display:flex;justify-content:space-between;padding:8px 0;font-weight:600">
    <span>Total</span><span style="font-family:var(--mono);color:${total>=0?'var(--accent)':'var(--red)'}">${fmt(total)}</span></div>`;
}

// ── ACCOUNTS SETTINGS ─────────────────────────────────────────────────────────
async function loadAccountsSettings() {
  const data = await apiFetch('/api/accounts-list');
  const el = document.getElementById('accounts-settings-list');
  if (!el) return;
  if (!data || !data.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:12px">No accounts</div>';
    return;
  }
  el.innerHTML = data.map(a => `
    <div class="settings-row">
      <div style="display:flex;align-items:center;gap:6px;flex:1">
        <span class="settings-label">${escapeHtml(a.name)}</span>
        <span style="font-size:10px;color:var(--muted)">${escapeHtml(a.account_type)}</span>
        <span style="font-size:11px;color:var(--muted);font-family:var(--mono)">Balance: ${fmt(a.balance)}</span>
      </div>
      <div style="display:flex;gap:4px">
        <button class="btn-icon" onclick="editAccount(${a.id},'${escapeAttr(a.name)}','${escapeAttr(a.account_type)}',${a.opening_balance})">✏️</button>
        <button class="btn-icon" onclick="deleteAccount(${a.id})">🗑️</button>
      </div>
    </div>
  `).join('');
}

async function addAccount() {
  const name = document.getElementById('new-acct-name').value.trim();
  const account_type = document.getElementById('new-acct-type').value;
  const opening_balance = document.getElementById('new-acct-balance').value || '0';
  if (!name) return toast('Enter an account name','error');
  const res = await apiFetch('/api/accounts-list', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, account_type, opening_balance: parseFloat(opening_balance)})});
  if (res && res.ok) {
    document.getElementById('new-acct-name').value = '';
    document.getElementById('new-acct-balance').value = '';
    loadAccountsSettings();
    renderAccountBalances();
    renderNetWorth();
    toast('Account added ✓','success');
  }
}

async function editAccount(id, oldName, oldType, oldBalance) {
  const name = prompt('Rename account:', oldName);
  if (!name || name.trim() === oldName) return;
  const res = await apiFetch(`/api/accounts-list/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name: name.trim()})});
  if (res && res.ok) {
    loadAccountsSettings();
    renderAccountBalances();
    renderNetWorth();
    populateModalAccountDropdowns(await apiFetch('/api/accounts') || []);
    toast('Account renamed ✓','success');
  }
}

async function deleteAccount(id) {
  if (!confirm('Delete this account? (Transactions are not affected)')) return;
  const res = await apiFetch(`/api/accounts-list/${id}`, {method:'DELETE'});
  if (res && res.ok) {
    loadAccountsSettings();
    renderAccountBalances();
    renderNetWorth();
    toast('Account deleted ✓','success');
  }
}

function showAccountsPanel() {
  nav('settings');
  switchSettingsTab('accounts');
  const el = document.getElementById('accounts-panel');
  if (el) setTimeout(() => el.scrollIntoView({behavior:'smooth'}), 50);
}

// ── SCHEDULED TRANSACTIONS SETTINGS ───────────────────────────────────────────
async function loadSchedulesSettings() {
  const data = await apiFetch('/api/schedules');
  const el = document.getElementById('schedules-settings-list');
  if (!el) return;
  updateCatOptions('new-sched-cat','new-sched-type');
  // Populate account selector
  const schedAcctSel = document.getElementById('new-sched-account');
  if (schedAcctSel) {
    const accts = await apiFetch('/api/accounts') || [];
    schedAcctSel.innerHTML = accts.map(a => `<option value="${escapeAttr(a)}">${escapeHtml(a)}</option>`).join('');
  }
  if (!data || !data.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:12px">No scheduled transactions</div>';
    return;
  }
  el.innerHTML = data.map(s => {
    const badge = s.enabled ? '' : '<span style="color:var(--red);font-size:10px;margin-left:6px">disabled</span>';
    return `<div class="settings-row" id="sched-row-${s.id}">
      <div style="display:flex;align-items:center;gap:6px;flex:1">
        <span class="settings-label">${escapeHtml(s.name)}</span>
        <span style="font-size:10px;color:var(--muted)">${escapeHtml(s.frequency)} · ${fmt(s.amount)} · ${escapeHtml(s.account)} · due ${escapeHtml(s.next_due)}</span>
        ${badge}
      </div>
      <div style="display:flex;gap:4px">
        <button class="btn-icon" onclick="startEditSchedule(${s.id},'${escapeAttr(s.name)}','${escapeAttr(s.category)}',${s.amount},'${escapeAttr(s.frequency)}','${escapeAttr(s.next_due)}')">✏️</button>
        <button class="btn-icon" onclick="toggleSchedule(${s.id},${s.enabled?0:1})">${s.enabled?'⏸':'▶'}</button>
        <button class="btn-icon" onclick="deleteSchedule(${s.id})">🗑️</button>
      </div>
    </div>`;
  }).join('');
}

function startEditSchedule(id, name, category, amount, frequency, nextDue) {
  const row = document.getElementById('sched-row-' + id);
  if (!row) return;
  const cats = EXPENSE_CATS.concat(INCOME_CATS);
  const catOpts = cats.map(c => `<option value="${escapeAttr(c)}"${c===category?' selected':''}>${escapeHtml(c)}</option>`).join('');
  const freqOpts = ['monthly','weekly','biweekly','yearly'].map(f =>
    `<option value="${f}"${f===frequency?' selected':''}>${f}</option>`).join('');
  row.innerHTML = `<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1">
      <input type="text" id="edit-sched-name" value="${escapeAttr(name)}" style="flex:1;min-width:90px" placeholder="Name">
      <select id="edit-sched-cat" style="width:120px">${catOpts}</select>
      <input type="number" id="edit-sched-amount" value="${amount}" style="width:80px" min="0.01" step="0.01">
      <select id="edit-sched-freq" style="width:100px">${freqOpts}</select>
      <input type="date" id="edit-sched-due" value="${escapeAttr(nextDue)}" style="width:130px">
      <button class="btn btn-sm" onclick="saveEditSchedule(${id})">Save</button>
      <button class="btn-icon" onclick="loadSchedulesSettings()">✕</button>
    </div>`;
  row.querySelector('#edit-sched-name').focus();
}

async function saveEditSchedule(id) {
  const name = document.getElementById('edit-sched-name').value.trim();
  const category = document.getElementById('edit-sched-cat').value;
  const amount = document.getElementById('edit-sched-amount').value;
  const frequency = document.getElementById('edit-sched-freq').value;
  const next_due = document.getElementById('edit-sched-due').value;
  if (!name) return toast('Enter a name','error');
  if (!amount || parseFloat(amount) <= 0) return toast('Enter a valid amount','error');
  if (!next_due) return toast('Set a due date','error');
  const res = await apiFetch(`/api/schedules/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, category, amount: parseFloat(amount), frequency, next_due})});
  if (res && res.ok) { loadSchedulesSettings(); toast('Schedule updated ✓','success'); }
}

async function addSchedule() {
  const name = document.getElementById('new-sched-name').value.trim();
  const type = document.getElementById('new-sched-type').value;
  const category = document.getElementById('new-sched-cat').value;
  const amount = document.getElementById('new-sched-amount').value;
  const frequency = document.getElementById('new-sched-freq').value;
  const next_due = document.getElementById('new-sched-due').value;
  if (!name) return toast('Enter a name','error');
  if (!amount || parseFloat(amount) <= 0) return toast('Enter a valid amount','error');
  if (!next_due) return toast('Set a due date','error');
  const account = document.getElementById('new-sched-account').value || 'Default';
  const res = await apiFetch('/api/schedules', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, type, category, amount: parseFloat(amount), account, frequency, next_due})});
  if (res && res.ok) {
    document.getElementById('new-sched-name').value = '';
    document.getElementById('new-sched-amount').value = '';
    document.getElementById('new-sched-due').value = '';
    loadSchedulesSettings();
    toast('Schedule added ✓','success');
  }
}

async function toggleSchedule(id, enabled) {
  await apiFetch(`/api/schedules/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({enabled})});
  loadSchedulesSettings();
}

async function deleteSchedule(id) {
  if (!confirm('Delete this schedule?')) return;
  const res = await apiFetch(`/api/schedules/${id}`, {method:'DELETE'});
  if (res && res.ok) { loadSchedulesSettings(); toast('Schedule deleted ✓','success'); }
}

async function postDueSchedules() {
  const res = await apiFetch('/api/schedules/post-due', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: '{}'});
  if (res && res.ok) {
    loadSchedulesSettings();
    if (res.posted > 0) {
      months = await apiFetch('/api/months') || [];
      if (months.length) renderMonth();
      toast(`Posted ${res.posted} scheduled transaction(s) ✓`,'success');
    } else {
      toast('No transactions due yet','success');
    }
  }
}

// ── TRANSFERS ─────────────────────────────────────────────────────────────────
function openTransferModal() {
  document.getElementById('t-date').value = new Date().toISOString().slice(0,10);
  document.getElementById('t-amount').value = '';
  document.getElementById('t-notes').value = '';
  // Populate account dropdowns from known accounts
  apiFetch('/api/accounts').then(accounts => {
    const opts = (accounts||[]).map(a => `<option value="${escapeAttr(a)}">${escapeHtml(a)}</option>`).join('');
    document.getElementById('t-from').innerHTML = opts;
    document.getElementById('t-to').innerHTML = opts;
  });
  document.getElementById('transfer-modal').classList.add('open');
}

async function submitTransfer() {
  const from_account = document.getElementById('t-from').value;
  const to_account = document.getElementById('t-to').value;
  const amount = document.getElementById('t-amount').value;
  const date = document.getElementById('t-date').value;
  const notes = document.getElementById('t-notes').value;
  if (!from_account || !to_account) return toast('Select both accounts','error');
  if (from_account === to_account) return toast('Cannot transfer to same account','error');
  if (!amount || parseFloat(amount) <= 0) return toast('Enter a valid amount','error');
  const res = await apiFetch('/api/transfers', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({from_account, to_account, amount: parseFloat(amount), date, notes})});
  if (res && res.ok) {
    closeModal('transfer-modal');
    toast('Transfer recorded ✓','success');
    renderAccountBalances();
    renderNetWorth();
  }
}

// ── UNDO ──────────────────────────────────────────────────────────────────────
let undoTimer = null;

function showUndoButton() {
  const btn = document.getElementById('undo-btn');
  if (!btn) return;
  btn.style.display = '';
  clearTimeout(undoTimer);
  undoTimer = setTimeout(() => { btn.style.display = 'none'; }, 10000);
}

async function doUndo() {
  const res = await apiFetch('/api/undo', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: '{}'});
  if (res && res.ok) {
    document.getElementById('undo-btn').style.display = 'none';
    toast('Undo successful ✓','success');
    months = await apiFetch('/api/months') || [];
    if (months.length) renderMonth();
    loadTransactions();
  }
}

// ── POST DUE SCHEDULES ON STARTUP ────────────────────────────────────────────
async function autoPostSchedules() {
  const res = await apiFetch('/api/schedules/post-due', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: '{}'});
  if (res && res.ok && res.posted > 0) {
    toast(`Auto-posted ${res.posted} scheduled transaction(s)`,'success');
  }
}

// ── BACKUP & RESTORE ──────────────────────────────────────────────────────────
function downloadBackup() {
  window.location.href = '/api/backup';
  toast('Downloading backup…','success');
}

async function restoreBackup(file) {
  if (!file) return;
  if (!confirm('Restore from backup? This will REPLACE all current data with the backup file. This cannot be undone.')) {
    document.getElementById('restore-input').value = '';
    return;
  }
  const fd = new FormData();
  fd.append('file', file);
  const token = await _ensureCsrf();
  const res = await fetch('/api/restore', {method:'POST', body: fd, headers:{'X-CSRF-Token': token}});
  document.getElementById('restore-input').value = '';
  if (res.ok) {
    toast('Database restored ✓ — reloading…','success');
    setTimeout(() => location.reload(), 1000);
  } else {
    const data = await res.json().catch(()=>({}));
    toast(data.error || 'Restore failed','error');
  }
}

init();
