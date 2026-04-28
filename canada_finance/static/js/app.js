let EXPENSE_CATS = [];
let INCOME_CATS = [];
let ALL_CATEGORIES = [];
const PALETTE = ["#6ee7b7","#f59e0b","#60a5fa","#a78bfa","#f87171","#34d399",
  "#fbbf24","#818cf8","#fb7185","#4ade80","#e879f9","#38bdf8","#fb923c","#a3e635"];

let months = [], currentMonthIdx = 0, donutChart = null;
let currentYear = new Date().getFullYear();

async function loadCategories() {
  ALL_CATEGORIES = await fetch('/api/categories').then(r=>r.json());
  EXPENSE_CATS = ALL_CATEGORIES.filter(c=>c.type==='Expense').map(c=>c.name);
  INCOME_CATS = ALL_CATEGORIES.filter(c=>c.type==='Income').map(c=>c.name);
  EXPENSE_CATS.push('UNCATEGORIZED');
}

// ── THEME ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  const dark = document.getElementById('theme-toggle').checked;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: dark ? 'dark' : 'light'})});
}

// ── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  // Load categories from DB
  await loadCategories();

  // Load settings
  const settings = await fetch('/api/settings').then(r=>r.json());
  const dark = settings.theme !== 'light';
  document.getElementById('theme-toggle').checked = dark;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');

  const res = await fetch('/api/months');
  months = await res.json();
  if (!months.length) {
    document.getElementById('month-display').textContent = 'No data yet — import a CSV!';
    populateCatFilter();
    updateCatOptions('f-category','f-type');
    populateBudgetCat();
    updateHiddenCount();
    return;
  }
  currentMonthIdx = 0;
  document.getElementById('f-date').value = new Date().toISOString().slice(0,10);
  populateCatFilter();
  updateCatOptions('f-category','f-type');
  populateBudgetCat();
  renderMonth();
  loadSettings();
  updateHiddenCount();
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
  document.getElementById('month-display').textContent = fmtMonth(m);
  const [summary, txns] = await Promise.all([
    fetch(`/api/summary?month=${m}`).then(r=>r.json()),
    fetch(`/api/transactions?month=${m}`).then(r=>r.json()),
  ]);
  renderCards(summary, txns);
  renderCatList(summary.by_category);
  renderDonut(summary.by_category);
  renderRecentTxns(txns.filter(t=>t.type==='Expense').slice(0,6));
  renderAverages();
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
    const bPct = c.budget ? Math.min(c.total/c.budget*100,100).toFixed(0) : null;
    const bColor = c.budget ? (c.total>c.budget?'var(--red)':c.total>c.budget*.8?'var(--amber)':'var(--accent)') : 'var(--accent)';
    return `<div class="cat-row" onclick="filterByCat('${c.category}')">
      <span class="cat-name">${c.category}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/max*100).toFixed(0)}%;background:${bColor}"></div></div>
      ${c.budget ? `<span class="cat-budget ${c.total>c.budget?'over':''}">${Math.round(c.total/c.budget*100)}%</span>` : ''}
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
  const data = await fetch('/api/averages').then(r=>r.json());
  const el = document.getElementById('averages-list');
  if (!data.length) { el.innerHTML = '<div class="empty">Not enough data yet</div>'; return; }
  const maxAvg = data[0].avg_monthly || 1;
  const n = data[0].months_seen;
  document.getElementById('avg-subtitle').textContent = `last ${n} month${n!==1?'s':''}`;
  el.innerHTML = data.map(r => `
    <div class="cat-row" onclick="filterByCat('${r.category}')" style="cursor:pointer">
      <span class="cat-name">${r.category}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(r.avg_monthly/maxAvg*100).toFixed(0)}%"></div></div>
      <span class="cat-amt">${fmt(r.avg_monthly)}<span style="color:var(--muted);font-size:10px">/mo</span></span>
    </div>`).join('');
}

// ── RECENT TXNS ───────────────────────────────────────────────────────────────
function renderRecentTxns(txns) {
  document.getElementById('recent-txns').innerHTML = txns.length
    ? txns.map(t=>`<tr onclick="openEditModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
        <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${t.date}</td>
        <td>${t.name}</td>
        <td><span class="badge">${t.category}</span></td>
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
  const search = document.getElementById('search-input')?.value.trim() || '';
  const banner = document.getElementById('search-banner');
  const hiddenParam = showingHidden ? '&hidden=1' : '';

  const url = search
    ? `/api/transactions?search=${encodeURIComponent(search)}&type=${encodeURIComponent(typ)}${hiddenParam}`
    : `/api/transactions?month=${m}&type=${encodeURIComponent(typ)}&category=${encodeURIComponent(cat)}${hiddenParam}`;

  const txns = await fetch(url).then(r=>r.json());
  const tbody = document.getElementById('all-txns');
  const empty = document.getElementById('txn-empty');

  if (search) {
    const total = txns.reduce((s,t)=>t.type==='Expense'?s+t.amount:s,0);
    banner.style.display='block';
    banner.innerHTML = `${txns.length} result${txns.length!==1?'s':''} for "<strong>${search}</strong>"` +
      (total>0?` &nbsp;·&nbsp; ${fmt(total)} total`:'') +
      ` &nbsp;<span style="cursor:pointer;color:var(--accent)" onclick="clearSearch()">✕ clear</span>`;
  } else { banner.style.display='none'; }

  if (!txns.length) { tbody.innerHTML=''; empty.style.display='block'; empty.textContent = showingHidden ? 'No hidden transactions' : 'No transactions found'; return; }
  empty.style.display='none';
  tbody.innerHTML = txns.map(t=>{
    const actionBtn = showingHidden
      ? `<button class="btn-ghost btn-sm" style="font-size:11px;padding:3px 8px" onclick="event.stopPropagation();unhideTx(${t.id})">Unhide</button>`
      : `<button class="del-btn" onclick="event.stopPropagation();deleteTx(${t.id})">×</button>`;
    return `<tr onclick="openEditModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
    <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${t.date}</td>
    <td>${t.name}</td>
    <td><span class="badge">${t.category}</span></td>
    <td style="color:var(--muted);font-size:11px">${t.account}</td>
    <td><span class="badge ${t.type.toLowerCase()}">${t.type}</span></td>
    <td style="text-align:right" class="${t.type==='Income'?'amt-income':'amt-expense'}">${fmt(t.amount)}</td>
    <td>${actionBtn}</td>
  </tr>`;
  }).join('');
}

async function deleteTx(id) {
  if (!confirm('Delete this transaction?')) return;
  await fetch(`/api/delete/${id}`, {method:'DELETE'});
  toast('Deleted','success'); renderMonth(); loadTransactions();
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

// ── YEAR VIEW ─────────────────────────────────────────────────────────────────
function changeYear(dir) { currentYear += dir; renderYear(); }
async function renderYear() {
  document.getElementById('year-display').textContent = currentYear;
  const data = await fetch(`/api/year/${currentYear}`).then(r=>r.json());
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
        <span class="cat-name">${c.category}</span>
        <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/maxCat*100).toFixed(0)}%"></div></div>
        <span class="cat-amt">${fmt(c.total)}</span>
      </div>`).join('')
    : '<div class="empty">No data</div>';
}

// ── SETTINGS ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  loadCategoryList();
  loadBudgets();
  loadLearned();
  loadRules();
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
  const res = await fetch('/api/categories', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, type, icon})}).then(r=>r.json());
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
  const res = await fetch(`/api/categories/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name: newName.trim(), icon: newIcon.trim()})}).then(r=>r.json());
  if (res.ok) {
    await loadCategories();
    loadCategoryList();
    populateCatFilter();
    populateBudgetCat();
    toast('Renamed ✓','success');
  } else toast(res.error||'Error','error');
}

async function deleteCategory(id, name, type) {
  const res = await fetch(`/api/categories/${id}`, {method:'DELETE'}).then(r=>r.json());
  if (res.error === 'in_use') {
    const sameCats = ALL_CATEGORIES.filter(c=>c.type===type && c.name!==name).map(c=>c.name);
    const target = prompt(`${res.count} transactions use "${name}".\nReassign them to which category?\n\nOptions: ${sameCats.join(', ')}`);
    if (!target) return;
    if (!sameCats.includes(target)) return toast('Invalid category','error');
    const res2 = await fetch(`/api/categories/${id}?reassign=${encodeURIComponent(target)}`, {method:'DELETE'}).then(r=>r.json());
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
  const budgets = await fetch('/api/budgets').then(r=>r.json());
  document.getElementById('budget-list').innerHTML = budgets.length
    ? budgets.map(b=>`<div class="settings-row">
        <div><div class="settings-label">${b.category}</div>
          <div class="settings-sub">${fmt(b.monthly_limit)}/month</div></div>
        <button class="btn btn-red btn-sm" onclick="deleteBudget('${b.category}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px;margin-bottom:8px">No budgets set</div>';
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
  await fetch('/api/budgets', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({category:cat, amount:parseFloat(amt)})});
  document.getElementById('budget-amt').value='';
  loadBudgets(); toast('Budget set ✓','success');
}

async function deleteBudget(cat) {
  await fetch(`/api/budgets/${encodeURIComponent(cat)}`, {method:'DELETE'});
  loadBudgets(); toast('Removed','success');
}

async function loadLearned() {
  const rows = await fetch('/api/learned').then(r=>r.json());
  document.getElementById('learned-list').innerHTML = rows.length
    ? rows.map(r=>`<div class="settings-row">
        <div><div class="settings-label" style="font-family:var(--mono);font-size:12px">${r.keyword}</div>
          <div class="settings-sub">→ ${r.category}</div></div>
        <button class="btn btn-ghost btn-sm" onclick="deleteLearned('${r.keyword.replace(/'/g,"\\'")}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px">None yet — edit a transaction category to start learning</div>';
}

async function deleteLearned(keyword) {
  await fetch(`/api/learned/${encodeURIComponent(keyword)}`, {method:'DELETE'});
  loadLearned(); toast('Removed','success');
}

function showBudgetPanel() {
  const el = document.getElementById('budget-panel');
  el.scrollIntoView({behavior:'smooth'});
}

// ── MODALS ────────────────────────────────────────────────────────────────────
function updateCatOptions(selId, typeId) {
  const type = document.getElementById(typeId).value;
  const sel = document.getElementById(selId);
  const cats = type === 'Income' ? INCOME_CATS : EXPENSE_CATS;
  sel.innerHTML = cats.map(c=>`<option>${c}</option>`).join('');
}

function openAddModal() {
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
  const acc = document.getElementById('e-account');
  for (let o of acc.options) if (o.value===t.account) { o.selected=true; break; }
  document.getElementById('edit-modal').classList.add('open');
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
  const res = await fetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (data.ok) {
    toast('Added ✓','success'); closeModal('add-modal');
    const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
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
  const res = await fetch(`/api/update/${id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (data.ok) {
    const extra = data.retro_fixed>0 ? ` · fixed ${data.retro_fixed} other${data.retro_fixed>1?'s':''}` : '';
    toast(`Saved ✓${extra}`,'success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
  } else toast(data.error||'Error','error');
}

async function deleteFromEdit() {
  if (!confirm('Delete this transaction?')) return;
  await fetch(`/api/delete/${document.getElementById('e-id').value}`, {method:'DELETE'});
  toast('Deleted','success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
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

  // First pass: detect each file
  for (const f of files) {
    const detectFd = new FormData();
    detectFd.append('file', f);
    const det = await fetch('/api/detect-csv', {method:'POST', body:detectFd}).then(r=>r.json());
    if (det.detected) {
      knownFd.append('files', f);
      hasKnown = true;
    } else {
      unknownFiles.push({file: f, headers: det.headers, preview: det.preview, raw_text: det.raw_text});
    }
  }

  // Import known files normally
  if (hasKnown) {
    const data = await fetch('/api/import', {method:'POST', body:knownFd}).then(r=>r.json());
    const resultsHtml = data.map(r => {
      const staleWarn = isStaleConfig(r.last_verified)
        ? `<div style="color:var(--amber);font-size:10px;font-family:var(--mono)">⚠ config last verified ${r.last_verified}</div>` : '';
      return `<div class="result-row">
        <div style="flex:1"><div>${r.file}</div><div class="result-bank">${r.bank}</div>${staleWarn}</div>
        <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
        <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
      </div>`;
    }).join('');
    document.getElementById('import-results').innerHTML = resultsHtml;
    const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
    if (months.length) { currentMonthIdx=0; renderMonth(); }
    toast(`Imported ${data.reduce((s,r)=>s+r.added,0)} transactions`,'success');
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
  const ths = info.headers.map(h => `<th>${h}</th>`).join('');
  const rows = info.preview.map(r =>
    `<tr>${info.headers.map(h => `<td>${r[h]||''}</td>`).join('')}</tr>`
  ).join('');
  table.innerHTML = `<thead><tr>${ths}</tr></thead><tbody>${rows}</tbody>`;

  // Populate dropdowns
  const selects = ['wiz-date-col','wiz-desc-col','wiz-amt-col','wiz-debit-col','wiz-credit-col'];
  selects.forEach(id => {
    const sel = document.getElementById(id);
    sel.innerHTML = '<option value="">— select —</option>' +
      info.headers.map(h => `<option value="${h}">${h}</option>`).join('');
  });

  // Auto-guess columns
  info.headers.forEach(h => {
    const hl = h.toLowerCase();
    if (hl.includes('date')) document.getElementById('wiz-date-col').value = h;
    if (hl.includes('description') || hl.includes('payee') || hl.includes('name'))
      document.getElementById('wiz-desc-col').value = h;
    if (hl === 'amount' || hl.includes('amount'))
      document.getElementById('wiz-amt-col').value = h;
    if (hl.includes('debit') || hl.includes('withdrawal'))
      document.getElementById('wiz-debit-col').value = h;
    if (hl.includes('credit') || hl.includes('deposit'))
      document.getElementById('wiz-credit-col').value = h;
  });

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
  const res = await fetch('/api/preview-parse', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({raw_text: wizardState.raw_text, mapping})
  }).then(r=>r.json());
  const el = document.getElementById('wizard-preview-parsed');
  if (res.transactions && res.transactions.length) {
    el.innerHTML = `<div style="font-size:11px;color:var(--muted);margin-bottom:6px">
      ${res.total} transaction${res.total!==1?'s':''} found (showing first ${res.transactions.length})</div>` +
      res.transactions.map(t => `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span style="color:var(--muted);font-family:var(--mono);width:80px">${t.date}</span>
        <span style="flex:1">${t.name}</span>
        <span class="badge ${t.type.toLowerCase()}">${t.type}</span>
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
  const saveRes = await fetch('/api/save-bank-config', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(mapping)}).then(r=>r.json());
  if (!saveRes.ok) { toast(saveRes.error||'Error saving config','error'); return; }
  // Re-import the file using the new config
  const fd = new FormData();
  fd.append('files', wizardState.file);
  const data = await fetch('/api/import', {method:'POST', body:fd}).then(r=>r.json());
  const prev = document.getElementById('import-results').innerHTML;
  document.getElementById('import-results').innerHTML = prev + data.map(r=>`
    <div class="result-row">
      <div style="flex:1"><div>${r.file}</div><div class="result-bank">${r.bank} <span style="color:var(--accent);font-size:10px">(new config)</span></div></div>
      <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
      <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
    </div>`).join('');
  closeModal('csv-wizard-modal');
  const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
  if (months.length) { currentMonthIdx=0; renderMonth(); }
  toast(`Config saved! Imported ${data.reduce((s,r)=>s+r.added,0)} transactions`,'success');
  // Process next unknown file in queue
  if (wizardState.queue && wizardState.queue.length) {
    setTimeout(() => openCsvWizard(wizardState.queue.shift()), 300);
  }
}

// ── IMPORT RULES UI ──────────────────────────────────────────────────────────
let showingHidden = false;

async function loadRules() {
  const rules = await fetch('/api/rules').then(r=>r.json());
  const el = document.getElementById('rules-list');
  if (!rules.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:12px;font-family:var(--mono)">No rules — add one or load a template</div>';
    return;
  }
  el.innerHTML = rules.map(r => {
    const condText = r.conditions.map(c =>
      `${c.field} ${c.operator} "${c.value}"`
    ).join(' AND ');
    const enabledCheck = r.enabled ? 'checked' : '';
    let actionInfo = '';
    if (r.action === 'label' && r.action_value) {
      try { const v = JSON.parse(r.action_value); actionInfo = ` → ${v.type||''} / ${v.category||''}`; } catch(e) {}
    }
    return `<div class="rule-row">
      <label class="toggle" style="flex-shrink:0">
        <input type="checkbox" ${enabledCheck} onchange="toggleRule(${r.id}, this.checked)">
        <span class="toggle-slider"></span>
      </label>
      <div class="rule-info">
        <div class="rule-name">${r.name}
          <span class="rule-action-badge ${r.action}">${r.action}</span>${actionInfo}
        </div>
        <div class="rule-conditions-summary">${condText}</div>
      </div>
      <button class="btn-icon" onclick='editRule(${JSON.stringify(r).replace(/'/g,"&#39;")})'>✏️</button>
      <button class="btn-icon" onclick="deleteRule(${r.id})">🗑️</button>
    </div>`;
  }).join('');
}

async function toggleRule(id, enabled) {
  await fetch(`/api/rules/${id}`, {method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({enabled: enabled ? 1 : 0})});
  toast(enabled ? 'Rule enabled' : 'Rule disabled', 'success');
}

async function deleteRule(id) {
  if (!confirm('Delete this rule?')) return;
  await fetch(`/api/rules/${id}`, {method:'DELETE'});
  loadRules();
  toast('Rule deleted', 'success');
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
    <select class="cond-op" style="width:120px">
      <option value="contains" ${operator==='contains'?'selected':''}>contains</option>
      <option value="equals" ${operator==='equals'?'selected':''}>equals</option>
      <option value="greater_than" ${operator==='greater_than'?'selected':''}>greater than</option>
      <option value="less_than" ${operator==='less_than'?'selected':''}>less than</option>
    </select>
    <input type="text" class="cond-value" value="${(value||'').replace(/"/g,'&quot;')}" placeholder="value" style="flex:1;min-width:100px">
    <button class="btn-icon" onclick="this.parentElement.remove()" style="color:var(--red)">×</button>`;
  document.getElementById('rule-conditions-list').appendChild(row);
  if (field) updateOperatorOptions(row.querySelector('.cond-field'));
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
      <option value="equals">equals</option>`;
  }
  if ([...opSelect.options].some(o => o.value === current)) opSelect.value = current;
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
  sel.innerHTML = cats.filter(c => c !== 'UNCATEGORIZED').map(c => `<option>${c}</option>`).join('');
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
    const res = await fetch(`/api/rules/${editId}`, {method:'PATCH',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r=>r.json());
    if (res.ok) { toast('Rule updated ✓', 'success'); closeModal('rule-modal'); loadRules(); }
    else toast(res.error||'Error', 'error');
  } else {
    const res = await fetch('/api/rules', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r=>r.json());
    if (res.ok) { toast('Rule created ✓', 'success'); closeModal('rule-modal'); loadRules(); }
    else toast(res.error||'Error', 'error');
  }
}

async function testRule() {
  const data = getRuleFormData();
  if (!data) return;
  const res = await fetch('/api/rules/test', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r=>r.json());
  const el = document.getElementById('rule-test-results');
  el.style.display = 'block';
  if (res.count === 0) {
    el.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:8px 0">No existing transactions match this rule.</div>';
    return;
  }
  el.innerHTML = `<div style="font-size:12px;color:var(--accent);margin-bottom:8px;font-family:var(--mono)">
    This rule would affect ${res.count} transaction${res.count!==1?'s':''}</div>` +
    res.transactions.map(t => `<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:11px">
      <span style="color:var(--muted);font-family:var(--mono);width:75px;flex-shrink:0">${t.date}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.name}</span>
      <span class="badge ${t.type.toLowerCase()}" style="font-size:10px">${t.type}</span>
      <span style="font-family:var(--mono);width:70px;text-align:right">${fmt(t.amount)}</span>
    </div>`).join('');
}

async function applyAllRules() {
  if (!confirm('Apply all enabled rules to every existing transaction? This will hide/label matching transactions.')) return;
  const res = await fetch('/api/rules/apply-all', {method:'POST'}).then(r=>r.json());
  toast(`Rules applied — ${res.affected} transaction${res.affected!==1?'s':''} affected`, 'success');
  if (res.affected > 0 && months.length) renderMonth();
  updateHiddenCount();
}

async function openTemplateModal() {
  document.getElementById('template-modal').classList.add('open');
  const templates = await fetch('/api/rule-templates').then(r=>r.json());
  const el = document.getElementById('template-list');
  if (!templates.length) {
    el.innerHTML = '<div class="empty">No templates found</div>';
    return;
  }
  el.innerHTML = templates.map(t => `<div class="settings-row">
    <div style="flex:1">
      <div class="settings-label">${t.name}</div>
      <div class="settings-sub">${t.description} · ${t.rule_count} rule${t.rule_count!==1?'s':''}</div>
    </div>
    <button class="btn btn-sm" onclick="loadTemplate('${t.file.replace(/'/g,"\\'")}', '${t.name.replace(/'/g,"\\'")}', ${t.rule_count})">Load</button>
  </div>`).join('');
}

async function loadTemplate(file, name, count) {
  if (!confirm(`Load "${name}"? This will add ${count} rule${count!==1?'s':''} to your list. Existing rules are not affected.`)) return;
  const res = await fetch('/api/rule-templates/load', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({file})}).then(r=>r.json());
  if (res.ok) {
    toast(`Loaded ${res.loaded} rule${res.loaded!==1?'s':''} from ${name} ✓`, 'success');
    closeModal('template-modal');
    loadRules();
  } else toast(res.error||'Error', 'error');
}

// ── HIDDEN TRANSACTIONS ──────────────────────────────────────────────────────

async function updateHiddenCount() {
  const res = await fetch('/api/transactions/hidden-count').then(r=>r.json());
  const badge = document.getElementById('hidden-count-badge');
  const btn = document.getElementById('hidden-toggle');
  badge.textContent = res.count;
  btn.style.display = res.count > 0 ? '' : 'none';
}

function toggleHiddenView() {
  showingHidden = !showingHidden;
  const btn = document.getElementById('hidden-toggle');
  const title = document.querySelector('#sec-transactions .txn-title');
  if (showingHidden) {
    btn.classList.remove('btn-ghost');
    btn.style.background = 'rgba(248,113,113,.15)';
    btn.style.borderColor = 'rgba(248,113,113,.3)';
    btn.style.color = 'var(--red)';
    title.textContent = 'Hidden Transactions';
  } else {
    btn.classList.add('btn-ghost');
    btn.style.background = '';
    btn.style.borderColor = '';
    btn.style.color = '';
    title.textContent = 'All Transactions';
  }
  loadTransactions();
}

async function unhideTx(id) {
  await fetch(`/api/transactions/${id}/unhide`, {method:'PATCH'});
  toast('Transaction unhidden ✓', 'success');
  loadTransactions();
  updateHiddenCount();
  if (months.length) renderMonth();
}

async function hideTx(id) {
  await fetch(`/api/transactions/${id}/hide`, {method:'PATCH'});
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
  if (id==='transactions') loadTransactions();
  if (id==='year') renderYear();
  if (id==='settings') loadSettings();
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function exportCSV(allTime) {
  const m = allTime ? '' : (months[currentMonthIdx]||'');
  window.location.href = `/api/export?month=${m}`;
  toast(`Downloading ${allTime?'all transactions':fmtMonth(m)} ✓`,'success');
}

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg, type='success') {
  const el = document.getElementById('toast');
  el.textContent=msg; el.className=`toast ${type} show`;
  setTimeout(()=>el.classList.remove('show'), 2800);
}

init();
