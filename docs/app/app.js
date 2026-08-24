/* Health Condition Tracker Web - 界面逻辑（纯前端，数据保存在本机浏览器） */
window.HCT_APP = (function () {
  var E = window.HCT_ENGINE;
  var D = window.HCT_DATA;
  var LS_KEY = 'hct_web_v1';
  var state = load() || defaultState();
  var currentTab = 'home';
  var wizard = null;
  var aform = { member: 'all', symptoms: [], custom: '', severity: null, duration: '', trend: '', useHistory: true };
  var pendingAnalyze = null;
  var $ = function (id) { return document.getElementById(id); };

  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function defaultState() {
    var me = { id: 'default', name: '我', relation: '本人', note: '', createdAt: todayISO() };
    return { config: { multiMember: false, defaultMember: 'default', city: '', province: '' }, members: [me], logs: [], meds: [], plans: [], quiz: {} };
  }
  function load() {
    try { var s = JSON.parse(localStorage.getItem(LS_KEY)); if (s && s.config && Array.isArray(s.members)) return s; } catch (e) {}
    return null;
  }
  function save() { try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) { alert('保存失败（存储空间可能已满）：' + e.message); } }
  function todayISO() { return E.todayISO(); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function fmtDate(v) { if (!v) return ''; var d = E.parseDate(v); if (!d) return String(v).slice(0, 10); return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
  function memberById(id) { for (var i = 0; i < state.members.length; i++) if (state.members[i].id === id) return state.members[i]; return state.members[0]; }
  function memberName(id) { return (memberById(id) || {}).name || '我'; }
  function logsOf(memberId) { return state.logs.filter(function (l) { return (l.member || 'default') === (memberId || 'default'); }); }
  function medsOf(memberId) { return state.meds.filter(function (m) { return (m.member || 'default') === (memberId || 'default'); }); }
  function plansOf(memberId) { return state.plans.filter(function (p) { return (p.member || 'default') === (memberId || 'default'); }); }

  /* DOM 构建助手（避免拼 HTML 字符串，天然防 XSS） */
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      var v = attrs[k];
      if (v === undefined || v === null) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'value') el.value = v;
      else if (k === 'checked' || k === 'disabled' || k === 'selected') el[k] = !!v;
      else if (k.indexOf('on') === 0) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v);
    }
    function appendKids(parent, kids) {
      if (kids === null || kids === undefined || kids === false) return;
      if (Array.isArray(kids)) { kids.forEach(function (c) { appendKids(parent, c); }); return; }
      parent.appendChild(typeof kids === 'string' ? document.createTextNode(kids) : kids);
    }
    for (var i = 2; i < arguments.length; i++) appendKids(el, arguments[i]);
    return el;
  }

  var TABS = [
    { id: 'home', label: '首页', ico: '🏠' },
    { id: 'logs', label: '记录', ico: '📋' },
    { id: 'analyze', label: '分析', ico: '🔍' },
    { id: 'charts', label: '图表', ico: '📊' },
    { id: 'profile', label: '档案', ico: '👥' },
    { id: 'settings', label: '设置', ico: '⚙️' }
  ];

  function showTab(id) {
    currentTab = id;
    TABS.forEach(function (t) { var s = $('tab-' + t.id); if (s) s.className = (t.id === id ? 'active' : ''); });
    var bar = $('tabbar');
    bar.innerHTML = '';
    TABS.forEach(function (t) {
      bar.appendChild(h('button', { class: t.id === id ? 'on' : '', onclick: function () { showTab(t.id); } },
        h('span', { class: 'ico', text: t.ico }), h('span', { text: t.label })));
    });
    renderHeader();
    renderCurrent();
  }
  function renderCurrent() {
    if (currentTab === 'home') renderHome();
    else if (currentTab === 'logs') renderLogs();
    else if (currentTab === 'analyze') renderAnalyze();
    else if (currentTab === 'charts') renderCharts();
    else if (currentTab === 'profile') renderProfile();
    else if (currentTab === 'settings') renderSettings();
  }
  function renderHeader() {
    var right = $('headerRight');
    right.innerHTML = '';
    var sel = h('select', { style: 'width:auto', onchange: function () { state.config.defaultMember = this.value; save(); renderCurrent(); } });
    if (state.config.multiMember) {
      state.members.forEach(function (m) { sel.appendChild(h('option', { value: m.id, selected: m.id === state.config.defaultMember, text: m.name })); });
    } else {
      sel.appendChild(h('option', { value: 'default', text: state.members[0].name }));
    }
    right.appendChild(sel);
  }

  /* ---------- 弹窗 ---------- */
  function openModal(node) { var m = $('modal'); m.innerHTML = ''; m.appendChild(node); $('modalMask').classList.add('open'); }
  function closeModal() { $('modalMask').classList.remove('open'); }
  document.addEventListener('DOMContentLoaded', function () {
    $('modalMask').addEventListener('click', function (e) { if (e.target === this) closeModal(); });
  });

  /* ---------- 通用小组件 ---------- */
  function stat(num, lab) { return h('div', { class: 'stat' }, h('div', { class: 'num', text: String(num) }), h('div', { class: 'lab', text: lab })); }
  function disclaimer() {
    return h('div', { class: 'disclaimer', text: '⚠️ 免责声明：本工具用于记录与提醒，所有分析仅供参考，不能替代专业医疗诊断。出现紧急情况请立即就医或拨打 120。' });
  }
  function levelClass(lvl) {
    if (lvl === '紧急') return 'critical';
    if (lvl === '中危') return 'urgent';
    if (lvl === '中') return 'mid';
    return 'low';
  }
  function riskColor(lvl) {
    if (lvl === '紧急') return 'var(--critical)';
    if (lvl === '中危') return 'var(--danger)';
    if (lvl === '中') return 'var(--warn)';
    return 'var(--low)';
  }
  function riskDot(lvl) { return h('span', { class: 'dot ' + levelClass(lvl) }); }

  function logRow(l) {
    var lvl = l.riskLevel || '低';
    var sevText = l.severity ? (' · ' + l.severity + '/10') : '';
    return h('div', { class: 'list-item' },
      riskDot(lvl),
      h('div', { class: 'main' },
        h('div', { class: 'title', text: l.symptom }),
        h('div', { class: 'muted small', text: fmtDate(l.date) + ' · ' + memberName(l.member) + sevText + (l.duration ? ' · 持续' + l.duration : '') + (l.trend ? ' · ' + l.trend : '') })
      ),
      h('button', { class: 'small-btn secondary', onclick: function () { openAddWizard(l.id); }, text: '编辑' }),
      h('button', { class: 'small-btn danger', onclick: function () { if (confirm('确定删除这条记录？')) { state.logs = state.logs.filter(function (x) { return x.id !== l.id; }); save(); renderCurrent(); } }, text: '删' })
    );
  }

  /* ---------- 首页 ---------- */
  function renderHome() {
    var root = $('tab-home'); root.innerHTML = '';
    var now = new Date();
    var greeting = now.getHours() < 12 ? '早上好' : (now.getHours() < 18 ? '下午好' : '晚上好');
    var logs = state.logs;
    var last30 = logs.filter(function (l) { var d = E.parseDate(l.date); return d && (Date.now() - d.getTime()) <= 30 * 86400000; });
    var medsActive = state.meds.filter(function (m) { return m.status !== '已停用'; });
    var reminders = E.collectReminders(state.meds, state.plans, 14);
    var last = logs.slice().sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); })[0];
    root.appendChild(h('div', { class: 'card' },
      h('div', { text: greeting + '，欢迎回来 👋' }),
      h('div', { class: 'muted', text: '今天是 ' + fmtDate(todayISO()) + (last ? ' · 最近记录：' + fmtDate(last.date) : '') })
    ));
    root.appendChild(h('div', { class: 'grid grid-3' },
      h('div', { class: 'stat', onclick: function () { openAddWizard(); } }, h('div', { class: 'num', text: '＋' }), h('div', { class: 'lab', text: '录入症状' })),
      h('div', { class: 'stat', onclick: function () { showTab('analyze'); } }, h('div', { class: 'num', text: '🔍' }), h('div', { class: 'lab', text: '快速分析' })),
      h('div', { class: 'stat', onclick: function () { showTab('charts'); } }, h('div', { class: 'num', text: '📊' }), h('div', { class: 'lab', text: '图表总览' }))
    ));
    root.appendChild(h('div', { class: 'grid grid-2' },
      stat(logs.length, '总记录'), stat(last30.length, '近30天'),
      stat(medsActive.length, '进行中用药'), stat(reminders.length, '14天内提醒')
    ));
    root.appendChild(h('h2', { text: '最近记录' }));
    if (!logs.length) root.appendChild(h('div', { class: 'empty', text: '还没有记录，点上方「录入症状」开始吧' }));
    else {
      var recent = logs.slice().sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); }).slice(0, 5);
      var card = h('div', { class: 'card' });
      recent.forEach(function (l) { card.appendChild(logRow(l)); });
      root.appendChild(card);
    }
    root.appendChild(h('h2', { text: '提醒预览（14天内）' }));
    root.appendChild(remindersView(reminders));
    root.appendChild(disclaimer());
  }

  /* ---------- 记录列表 ---------- */
  function renderLogs() {
    var root = $('tab-logs'); root.innerHTML = '';
    root.appendChild(h('h1', { text: '健康记录' }));
    root.appendChild(h('button', { onclick: function () { openAddWizard(); }, text: '＋ 录入新症状' }));
    var filter = 'all';
    var wrap = h('div', {});
    function draw() {
      wrap.innerHTML = '';
      var items = state.logs;
      if (filter !== 'all') items = items.filter(function (l) { return (l.member || 'default') === filter; });
      items = items.slice().sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });
      if (!items.length) { wrap.appendChild(h('div', { class: 'empty', text: '暂无记录' })); return; }
      var card = h('div', { class: 'card' });
      items.forEach(function (l) { card.appendChild(logRow(l)); });
      wrap.appendChild(card);
      wrap.appendChild(h('div', { class: 'muted small', text: '共 ' + items.length + ' 条记录' }));
    }
    if (state.config.multiMember) {
      var sel = h('select', { onchange: function () { filter = this.value; draw(); } });
      sel.appendChild(h('option', { value: 'all', text: '全部成员' }));
      state.members.forEach(function (m) { sel.appendChild(h('option', { value: m.id, text: m.name })); });
      root.appendChild(h('div', { class: 'card', style: 'padding:10px' }, h('label', { class: 'field', text: '筛选成员' }), sel));
    }
    root.appendChild(wrap);
    draw();
  }

  /* ---------- 提醒视图 ---------- */
  function remindersView(reminders) {
    var card = h('div', { class: 'card' });
    if (!reminders.length) { card.appendChild(h('div', { class: 'empty', text: '暂无复诊 / 停药提醒' })); return card; }
    reminders.forEach(function (r) {
      var tag;
      if (r.left < 0) tag = '已逾期 ' + (-r.left) + ' 天';
      else if (r.left === 0) tag = '就是今天';
      else tag = '还有 ' + r.left + ' 天';
      var color = r.left < 0 ? 'danger' : (r.left <= 2 ? 'warn' : 'ok');
      card.appendChild(h('div', { class: 'list-item' },
        h('div', { class: 'main' },
          h('div', { class: 'title', text: '[' + r.kind + '] ' + (r.title || '') }),
          h('div', { class: 'muted small', text: memberName(r.member) + ' · ' + fmtDate(r.date) })
        ),
        h('span', { class: 'badge', style: 'background:' + (color === 'danger' ? '#fee2e2' : color === 'warn' ? '#fef3c7' : '#dcfce7') + ';color:' + (color === 'danger' ? '#991b1b' : color === 'warn' ? '#92400e' : '#166534'), text: tag })
      ));
    });
    return card;
  }

  /* ---------- 录入向导 ---------- */
  function openAddWizard(editId) {
    wizard = { step: 1, maxStep: 5, data: { id: editId || null, member: state.config.defaultMember || 'default', symptoms: [], custom: '', severity: null, date: todayISO(), duration: '', trend: '', followUps: {}, notes: '', analyzeAfter: false } };
    if (editId) {
      var rec = null;
      state.logs.forEach(function (l) { if (l.id === editId) rec = l; });
      if (rec) {
        var syms = [];
        if (rec.symptoms && rec.symptoms.length) syms = rec.symptoms.map(function (s) { return s.name; });
        else if (rec.symptom) syms = rec.symptom.split(/[、,，\/]+/);
        wizard.data.member = rec.member || 'default';
        wizard.data.symptoms = syms;
        wizard.data.severity = rec.severity || null;
        wizard.data.date = String(rec.date || todayISO()).slice(0, 10);
        wizard.data.duration = rec.duration || '';
        wizard.data.trend = rec.trend || '';
        wizard.data.notes = rec.notes || '';
      }
    }
    openModal(wizardNode());
    drawWizard();
  }
  function wizardNode() {
    var head = h('h3', { id: 'wizTitle', text: '录入症状' });
    var prog = h('div', { class: 'progress', id: 'wizProg' });
    var body = h('div', { id: 'wizBody' });
    var nav = h('div', { class: 'actions', id: 'wizNav' });
    return h('div', {}, head, prog, body, nav);
  }
  function drawWizard() {
    var d = wizard.data;
    var prog = $('wizProg'); prog.innerHTML = '';
    for (var i = 1; i <= wizard.maxStep; i++) prog.appendChild(h('div', { class: 'seg' + (i <= wizard.step ? ' done' : '') }));
    var body = $('wizBody'); body.innerHTML = '';
    var title = '录入症状';
    var node;
    if (wizard.step === 1) { title = d.id ? '编辑记录' : '① 选择档案'; node = wizStep1(); }
    else if (wizard.step === 2) { title = '② 填写症状'; node = wizStep2(); }
    else if (wizard.step === 3) { title = '③ 程度与时长'; node = wizStep3(); }
    else if (wizard.step === 4) { title = '④ 补充追问'; node = wizStep4(); }
    else { title = '⑤ 确认保存'; node = wizStep5(); }
    $('wizTitle').textContent = title;
    body.appendChild(node);
    var nav = $('wizNav'); nav.innerHTML = '';
    if (wizard.step > 1) nav.appendChild(h('button', { class: 'secondary', onclick: function () { wizard.step--; drawWizard(); }, text: '上一步' }));
    if (wizard.step < wizard.maxStep) {
      var canNext = true;
      if (wizard.step === 2 && !d.symptoms.length) canNext = false;
      nav.appendChild(h('button', { disabled: !canNext, onclick: function () { if (!canNext) return; if (wizard.step === 1 && state.config.multiMember && !d.member) { alert('请选择档案'); return; } wizard.step++; drawWizard(); }, text: '下一步' }));
    } else {
      nav.appendChild(h('button', { onclick: saveWizard, text: '💾 保存记录' }));
    }
  }
  function wizStep1() {
    var d = wizard.data;
    if (!state.config.multiMember) { d.member = 'default'; return h('div', {}, h('div', { class: 'banner info', text: '当前为「单人模式」，记录将保存到：' + memberName('default') })); }
    var wrap = h('div', {});
    wrap.appendChild(h('label', { class: 'field', text: '本次记录添加到哪个档案？' }));
    var chips = h('div', { class: 'chips' });
    state.members.forEach(function (m) {
      chips.appendChild(h('span', { class: 'chip' + (d.member === m.id ? ' on' : ''), onclick: function () { d.member = m.id; drawWizard(); }, text: m.name }));
    });
    chips.appendChild(h('span', { class: 'chip', onclick: function () { var n = prompt('新档案名字（如：爸爸）'); if (n && n.trim()) { var m = { id: uid(), name: n.trim().slice(0, 12), relation: '', note: '', createdAt: todayISO() }; state.members.push(m); d.member = m.id; save(); drawWizard(); } }, text: '＋ 新建档案' }));
    wrap.appendChild(chips);
    return wrap;
  }
  function knownSymptoms() { return Object.keys(D.symptom_disease_map || {}); }
  function popularSymptoms() {
    var all = knownSymptoms();
    var hot = ['头痛', '发热', '咳嗽', '乏力', '咽痛', '鼻塞', '流鼻涕', '腹痛', '腹泻', '便秘', '恶心', '呕吐', '头晕', '失眠', '胸痛', '胸闷', '心悸', '腰痛', '关节痛', '皮疹', '皮肤瘙痒', '食欲不振'];
    var out = [];
    hot.forEach(function (x) { if (all.indexOf(x) >= 0) out.push(x); });
    return out;
  }
  function wizStep2() {
    var d = wizard.data;
    var wrap = h('div', {});
    var input = h('input', { id: 'wizSymInput', placeholder: '输入症状（如：头痛、拉肚子、没力气）', list: 'wizSymList' });
    var dl = h('datalist', { id: 'wizSymList' });
    knownSymptoms().forEach(function (s) { dl.appendChild(h('option', { value: s })); });
    wrap.appendChild(h('label', { class: 'field', text: '本次症状（可多个）' }));
    wrap.appendChild(input);
    wrap.appendChild(dl);
    wrap.appendChild(h('button', { class: 'secondary', style: 'margin-top:8px', onclick: function () {
      var v = input.value.trim();
      if (!v) return;
      var matched = E.matchSymptoms(v);
      var add = matched.length ? matched : [v];
      add.forEach(function (s) { if (d.symptoms.indexOf(s) < 0) d.symptoms.push(s); });
      input.value = '';
      drawWizard();
    }, text: '添加' }));
    var selChips = h('div', { class: 'chips', style: 'margin-top:10px' });
    d.symptoms.forEach(function (s) {
      var isFlag = (D.red_flags['紧急症状'] || []).indexOf(s) >= 0 || (D.red_flags['警惕症状'] || []).indexOf(s) >= 0;
      selChips.appendChild(h('span', { class: 'chip on' + (isFlag ? ' hot' : ''), onclick: function () { d.symptoms = d.symptoms.filter(function (x) { return x !== s; }); drawWizard(); }, text: s + ' ✕' }));
    });
    if (d.symptoms.length) wrap.appendChild(selChips);
    wrap.appendChild(h('label', { class: 'field', text: '常见症状（点击选择）' }));
    var hotChips = h('div', { class: 'chips' });
    popularSymptoms().forEach(function (s) {
      hotChips.appendChild(h('span', { class: 'chip' + (d.symptoms.indexOf(s) >= 0 ? ' on' : ''), onclick: function () {
        var i = d.symptoms.indexOf(s);
        if (i >= 0) d.symptoms.splice(i, 1); else d.symptoms.push(s);
        drawWizard();
      }, text: s }));
    });
    wrap.appendChild(hotChips);
    return wrap;
  }
  function wizStep3() {
    var d = wizard.data;
    var wrap = h('div', {});
    var sevVal = h('span', { class: 'badge', style: 'font-size:15px', text: d.severity ? (d.severity + '/10') : '未填' });
    var range = h('input', { type: 'range', min: 0, max: 10, step: 1, value: d.severity || 0, oninput: function () { var v = parseInt(this.value, 10); d.severity = v > 0 ? v : null; sevVal.textContent = d.severity ? (d.severity + '/10') : '未填'; } });
    var verbal = h('div', { class: 'muted small', id: 'sevVerbal', text: severityVerbal(d.severity) });
    wrap.appendChild(h('label', { class: 'field', text: '严重程度（0=跳过）' }));
    wrap.appendChild(h('div', { class: 'two-col' }, h('div', {}, range, sevVal, verbal), h('div', {},
      h('label', { class: 'field', text: '发病日期' }),
      h('input', { type: 'date', value: d.date, onchange: function () { d.date = this.value; } }),
      h('label', { class: 'field', text: '持续时长（如：2天 / 1周 / 3个月）' }),
      h('input', { value: d.duration, placeholder: '可留空', oninput: function () { d.duration = this.value; } }),
      h('label', { class: 'field', text: '和之前比的变化趋势' }),
      h('select', { onchange: function () { d.trend = this.value; } },
        h('option', { value: '', text: '不选' }),
        ['好转', '平稳', '加重', '明显加重', '快速恶化'].map(function (t) { return h('option', { value: t, selected: d.trend === t, text: t }); })
      )
    )));
    return wrap;
  }
  function severityVerbal(sev) {
    var scale = (D.severity_scale || {}).verbal_scale || [];
    for (var i = 0; i < scale.length; i++) if (scale[i].score === sev) return scale[i].label;
    return '拖动滑块选择程度（0 表示不填写）';
  }
  function wizStep4() {
    var d = wizard.data;
    var wrap = h('div', {});
    var first = d.symptoms[0] || '';
    var qs = [];
    var fq = D.followup_questions || {};
    if (fq.symptoms && fq.symptoms[first]) qs = fq.symptoms[first];
    (fq.generic || []).forEach(function (g) { if (qs.length < 4) qs.push(g); });
    if (!qs.length) { wrap.appendChild(h('div', { class: 'banner info', text: '无针对性追问（可跳过）' })); return wrap; }
    wrap.appendChild(h('label', { class: 'field', text: '回答可帮助分析更准确（可跳过）' }));
    qs.forEach(function (q) {
      wrap.appendChild(h('label', { class: 'field', text: q }));
      wrap.appendChild(h('input', { value: d.followUps[q] || '', oninput: function () { d.followUps[q] = this.value; }, placeholder: '可留空' }));
    });
    return wrap;
  }
  function wizStep5() {
    var d = wizard.data;
    var wrap = h('div', {});
    var syms = E.normalizeSymptoms(d.symptoms);
    wrap.appendChild(h('div', { class: 'banner ok', text: '症状：' + (syms.join('、') || '（未填）') }));
    var lines = h('div', { class: 'muted small', style: 'margin:8px 0' });
    lines.appendChild(h('div', { text: '档案：' + memberName(d.member) }));
    lines.appendChild(h('div', { text: '严重程度：' + (d.severity ? d.severity + '/10' : '未填') }));
    lines.appendChild(h('div', { text: '发病日期：' + d.date }));
    lines.appendChild(h('div', { text: '持续时长：' + (d.duration || '未填') }));
    lines.appendChild(h('div', { text: '趋势：' + (d.trend || '未填') }));
    wrap.appendChild(lines);
    wrap.appendChild(h('label', { class: 'field', text: '备注（可选）' }));
    wrap.appendChild(h('textarea', { value: d.notes, oninput: function () { d.notes = this.value; }, placeholder: '如：昨晚受凉、吃了什么药等' }));
    var cb = h('label', { class: 'checklist' }, h('input', { type: 'checkbox', checked: d.analyzeAfter, onchange: function () { d.analyzeAfter = this.checked; } }), h('span', { text: '保存后立即进行分析' }));
    wrap.appendChild(cb);
    return wrap;
  }
  function saveWizard() {
    var d = wizard.data;
    var syms = E.normalizeSymptoms(d.symptoms);
    if (!syms.length) { alert('请至少填写一个症状'); return; }
    var sev = d.severity ? parseInt(d.severity, 10) : null;
    if (sev !== null && (sev < 1 || sev > 10)) sev = null;
    var member = d.member || 'default';
    var logs = logsOf(member);
    var res = E.analyze({ symptoms: syms, logs: logs, severity: sev, durationText: d.duration, trend: d.trend });
    var created = d.id ? (function () { var r = null; state.logs.forEach(function (l) { if (l.id === d.id) r = l; }); return r ? r.createdAt : new Date().toISOString(); })() : new Date().toISOString();
    var rec = {
      id: d.id || uid(), member: member, date: d.date || todayISO(), symptom: syms.join('、'),
      symptoms: syms.map(function (s) { return { name: s, severity: sev }; }),
      severity: sev, duration: d.duration || '', trend: d.trend || '', notes: d.notes || '',
      followUps: d.followUps || {}, riskLevel: res.risk.level, createdAt: created
    };
    if (d.id) { state.logs = state.logs.map(function (l) { return l.id === d.id ? rec : l; }); }
    else { state.logs.push(rec); }
    save();
    closeModal();
    renderCurrent();
    if (d.analyzeAfter) {
      aform.symptoms = syms; aform.severity = sev; aform.duration = d.duration; aform.trend = d.trend; aform.member = member; aform.useHistory = true;
      pendingAnalyze = { symptoms: syms, severity: sev, duration: d.duration, trend: d.trend, member: member };
      showTab('analyze');
    }
  }

  /* ---------- 分析页 ---------- */
  function renderAnalyze() {
    var root = $('tab-analyze'); root.innerHTML = '';
    root.appendChild(h('h1', { text: '病情分析' }));
    var form = h('div', { class: 'card' });
    var f = aform;
    if (state.config.multiMember) {
      var sel = h('select', { onchange: function () { f.member = this.value; } });
      sel.appendChild(h('option', { value: 'all', text: '全部成员（综合历史）' }));
      state.members.forEach(function (m) { sel.appendChild(h('option', { value: m.id, selected: f.member === m.id, text: m.name })); });
      form.appendChild(h('label', { class: 'field', text: '结合哪个档案的历史' })); form.appendChild(sel);
    } else { f.member = 'default'; }
    var symInput = h('input', { id: 'anSymInput', placeholder: '输入症状（如：头痛 发热）', list: 'anSymList' });
    var dl = h('datalist', { id: 'anSymList' });
    knownSymptoms().forEach(function (s) { dl.appendChild(h('option', { value: s })); });
    form.appendChild(h('label', { class: 'field', text: '症状（可多个）' })); form.appendChild(symInput); form.appendChild(dl);
    form.appendChild(h('button', { class: 'secondary', style: 'margin-top:8px', onclick: function () {
      var v = symInput.value.trim(); if (!v) return;
      var matched = E.matchSymptoms(v);
      var add = matched.length ? matched : [v];
      add.forEach(function (s) { if (f.symptoms.indexOf(s) < 0) f.symptoms.push(s); });
      symInput.value = ''; renderAnalyze();
    }, text: '添加' }));
    var chips = h('div', { class: 'chips', style: 'margin-top:8px' });
    f.symptoms.forEach(function (s) {
      chips.appendChild(h('span', { class: 'chip on', onclick: function () { f.symptoms = f.symptoms.filter(function (x) { return x !== s; }); renderAnalyze(); }, text: s + ' ✕' }));
    });
    if (f.symptoms.length) form.appendChild(chips);
    form.appendChild(h('div', { class: 'chips', style: 'margin-top:8px' }));
    var sevVal = h('span', { class: 'badge', style: 'font-size:15px', text: f.severity ? (f.severity + '/10') : '未填' });
    var range = h('input', { type: 'range', min: 0, max: 10, step: 1, value: f.severity || 0, oninput: function () { var v = parseInt(this.value, 10); f.severity = v > 0 ? v : null; sevVal.textContent = f.severity ? (f.severity + '/10') : '未填'; } });
    var verbal = h('div', { class: 'muted small', text: severityVerbal(f.severity) });
    form.appendChild(h('label', { class: 'field', text: '严重程度' })); form.appendChild(range); form.appendChild(h('div', { class: 'two-col' }, sevVal, verbal));
    var two = h('div', { class: 'two-col' });
    var durIn = h('input', { value: f.duration, placeholder: '持续时长，如 2天', oninput: function () { f.duration = this.value; } });
    var trSel = h('select', { onchange: function () { f.trend = this.value; } },
      h('option', { value: '', text: '趋势不选' }),
      ['好转', '平稳', '加重', '明显加重', '快速恶化'].map(function (t) { return h('option', { value: t, selected: f.trend === t, text: t }); })
    );
    two.appendChild(h('div', {}, h('label', { class: 'field', text: '持续时长' }), durIn));
    two.appendChild(h('div', {}, h('label', { class: 'field', text: '变化趋势' }), trSel));
    form.appendChild(two);
    var histCb = h('label', { class: 'checklist' }, h('input', { type: 'checkbox', checked: f.useHistory, onchange: function () { f.useHistory = this.checked; } }), h('span', { text: '结合历史记录共同分析' }));
    form.appendChild(histCb);
    var btnRow = h('div', { class: 'btn-row' });
    btnRow.appendChild(h('button', { onclick: function () { openQuiz('quick'); }, text: '📝 客观评估' }));
    btnRow.appendChild(h('button', { onclick: runAnalyze, text: '🔍 开始分析' }));
    form.appendChild(btnRow);
    root.appendChild(form);
    root.appendChild(h('div', { id: 'analyzeResult' }));
    if (pendingAnalyze) { var p = pendingAnalyze; pendingAnalyze = null; f.symptoms = p.symptoms; f.severity = p.severity; f.duration = p.duration; f.trend = p.trend; if (p.member && p.member !== 'all') f.member = p.member; runAnalyze(); }
  }
  function runAnalyze() {
    var f = aform;
    var syms = E.normalizeSymptoms(f.symptoms.slice());
    if (!syms.length) { alert('请选择或输入至少一个症状'); return; }
    var logs = (!f.useHistory) ? [] : ((f.member === 'all' || !f.member) ? state.logs : logsOf(f.member));
    var res = E.analyze({ symptoms: syms, logs: logs, severity: f.severity, durationText: f.duration, trend: f.trend });
    renderAnalyzeResult(res);
    var box = $('analyzeResult');
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function renderAnalyzeResult(res) {
    var box = $('analyzeResult'); if (!box) return;
    box.innerHTML = '';
    var risk = res.risk;
    var lvl = risk.level;
    var cls = lvl === '紧急' ? 'risk-critical' : (lvl === '中危' ? 'risk-urgent' : (lvl === '中' ? 'risk-mid' : 'risk-low'));
    box.appendChild(h('div', { class: 'risk-card ' + cls },
      h('div', { class: 'level', text: '风险等级：' + lvl }),
      h('div', { class: 'action', text: risk.action })
    ));
    var course = res.course || {};
    box.appendChild(h('div', { class: 'banner info', text: '病程判断：' + course.kind + (course.days ? '（' + course.days + ' 天）' : '') + (res.overdue && res.overdue.length ? ' · ⚠️ 已超过建议就诊时长：' + res.overdue.join('、') : '') }));
    if (risk.reasons && risk.reasons.length) {
      var rc = h('div', { class: 'card' });
      rc.appendChild(h('h3', { text: '判断依据' }));
      risk.reasons.forEach(function (r) { rc.appendChild(h('div', { text: '· ' + r })); });
      box.appendChild(rc);
    }
    box.appendChild(h('div', { class: 'banner ok', text: risk.calm }));
    // 疾病提示
    var tiers = res.tiers || {};
    var disCard = h('div', { class: 'card' });
    disCard.appendChild(h('h3', { text: '可能的疾病方向（仅供参考，非诊断）' }));
    var any = false;
    ['高度相关', '可能相关', '需注意（仅历史）'].forEach(function (tier) {
      var items = tiers[tier] || [];
      if (!items.length) return;
      any = true;
      disCard.appendChild(h('div', { class: 'muted', text: '【' + tier + '】' }));
      items.slice(0, 6).forEach(function (it) {
        disCard.appendChild(h('div', { class: 'list-item' },
          h('div', { class: 'main' },
            h('div', { class: 'title', text: it.disease }),
            h('div', { class: 'muted small', text: '相关症状：' + it.input.concat(it.history).join('、') + ' · 相关度' + (it.confidence === '高' ? '高' : it.confidence === '中' ? '中' : '低') })
          ),
          h('span', { class: 'tag', text: it.confidence })
        ));
      });
    });
    if (!any) disCard.appendChild(h('div', { class: 'empty', text: '暂未匹配到明确方向，建议继续观察或就诊' }));
    box.appendChild(disCard);
    // 科室
    var depts = Object.keys(res.departments || {}).sort(function (a, b) { return res.departments[b] - res.departments[a]; }).slice(0, 5);
    if (depts.length) {
      var dc = h('div', { class: 'card' });
      dc.appendChild(h('h3', { text: '建议就诊科室' }));
      dc.appendChild(h('div', { class: 'chips' }));
      depts.forEach(function (d) {
        dc.appendChild(h('span', { class: 'chip', style: 'background:var(--primary-light);border-color:var(--primary)', text: d }));
      });
      box.appendChild(dc);
    }
    // 国际就诊路径
    var path = E.carePathway(res);
    var pc = h('div', { class: 'card' });
    pc.appendChild(h('h3', { text: '国际权威就诊路径（NHS/Mayo/CDC/WHO）' }));
    pc.appendChild(h('div', { style: 'font-size:15px;font-weight:600', text: path.label + '（' + path.timeframe + '）' }));
    pc.appendChild(h('div', { class: 'muted', text: path.advice }));
    path.symptoms.forEach(function (it) {
      pc.appendChild(h('div', { style: 'margin-top:8px;padding:8px;background:var(--bg);border-radius:8px' },
        h('div', { style: 'font-weight:600', text: '【' + it.symptom + '】' }),
        it.current ? h('div', { text: '· 当前档（' + it.current.tier + '）：' + it.current.text }) : null,
        it.upgrade ? h('div', { text: '· 若出现以下情况升级到「' + it.upgrade.tier + '」：' + it.upgrade.text }) : null
      ));
    });
    if (path.sources && path.sources.length) pc.appendChild(h('div', { class: 'muted small', style: 'margin-top:8px', text: '依据：' + path.sources.slice(0, 3).map(function (s) { return s.org; }).join(' / ') }));
    box.appendChild(pc);
    // 医院推荐
    box.appendChild(hospitalCard(depts));
    box.appendChild(disclaimer());
  }
  function hospitalCard(depts) {
    var card = h('div', { class: 'card' });
    card.appendChild(h('h3', { text: '就诊医院推荐（全国十大）' }));
    var cityIn = h('input', { value: state.config.city || '', placeholder: '所在城市（如：杭州）' });
    var provIn = h('input', { value: state.config.province || '', placeholder: '所在省份（如：浙江，可自动推断）' });
    var out = h('div', { style: 'margin-top:8px' });
    card.appendChild(h('div', { class: 'two-col' }, h('div', {}, h('label', { class: 'field', text: '城市' }), cityIn), h('div', {}, h('label', { class: 'field', text: '省份' }), provIn)));
    card.appendChild(h('button', { class: 'secondary', style: 'margin-top:8px', onclick: function () {
      state.config.city = cityIn.value.trim(); state.config.province = provIn.value.trim(); save();
      renderHospitalAdvice(out, depts, state.config.city, state.config.province);
    }, text: '🏥 推荐医院与就诊方案' }));
    card.appendChild(out);
    return card;
  }
  function renderHospitalAdvice(container, depts, city, province) {
    container.innerHTML = '';
    if (!depts || !depts.length) { container.appendChild(h('div', { class: 'muted', text: '暂无科室建议，无法推荐医院' })); return; }
    var adv = E.hospitalAdvice(depts, city, province);
    adv.groups.forEach(function (g) {
      if (g.empty) { container.appendChild(h('div', { class: 'banner warn', text: '【' + g.department + '】暂无收录医院，建议先看当地三甲。' })); return; }
      var block = h('div', { style: 'margin-top:8px' });
      block.appendChild(h('div', { style: 'font-weight:600', text: '【' + g.department + '】全国十大医院' }));
      if (g.sameCity.length) {
        block.appendChild(h('div', { class: 'muted', text: '◆ 同城（最近、最方便）' }));
        g.sameCity.forEach(function (hsp, i) { block.appendChild(h('div', { class: 'small', text: (i + 1) + '. ' + hsp.name + '（' + hsp.city + '）' + (hsp.note ? ' —— ' + hsp.note : '') })); });
      }
      if (g.sameProv.length) {
        block.appendChild(h('div', { class: 'muted', text: '◆ 同省' }));
        g.sameProv.forEach(function (hsp, i) { block.appendChild(h('div', { class: 'small', text: (i + 1) + '. ' + hsp.name + '（' + hsp.city + '）' + (hsp.note ? ' —— ' + hsp.note : '') })); });
      }
      block.appendChild(h('div', { class: 'muted', text: '◆ 全国其他（疑难/顶尖专家）' }));
      g.others.forEach(function (hsp, i) { block.appendChild(h('div', { class: 'small', text: (i + 1) + '. ' + hsp.name + '（' + hsp.city + '）' + (hsp.note ? ' —— ' + hsp.note : '') })); });
      container.appendChild(block);
    });
    container.appendChild(h('div', { class: 'banner info', style: 'margin-top:8px', text: '性价比方案：先挂本地三甲普通门诊完成基础检查；确需专科再考虑同省省会或全国顶级医院。费用：普通门诊约 20-100 元、专家约 50-300 元、特需/国际部约 300-1500 元以上（检查治疗另计）。挂号优先医院官方公众号/APP，或省级统一平台（北京114、上海健康云、粤健通等）。异地就医先在国家医保服务平台备案。' }));
    container.appendChild(h('div', { class: 'muted small', text: '医院信息整理自公开资料，仅供挂号参考，请以官方渠道为准。' }));
  }
  /* ---------- 客观评估问卷 ---------- */
  function openQuiz(mode) {
    var dims = (D.severity_scale || {}).dimensions || {};
    var keys = mode === 'quick' ? ['疼痛不适强度', '睡眠影响', '工作学习影响'] : Object.keys(dims);
    var answers = {};
    var wrap = h('div', {});
    wrap.appendChild(h('h3', { text: mode === 'quick' ? '快速客观评估（3 题，可跳过）' : '完整客观评估（7 维，可跳过）' }));
    var fields = h('div', {});
    keys.forEach(function (k) {
      var dim = dims[k]; if (!dim) return;
      var f = h('div', { style: 'margin:10px 0' });
      f.appendChild(h('div', { text: dim.question }));
      if (dim.type === '0-10') {
        f.appendChild(h('input', { type: 'number', min: 0, max: 10, placeholder: '0-10', oninput: function () { answers[k] = this.value; } }));
      } else {
        var sel = h('select', { onchange: function () { answers[k] = this.value; } });
        sel.appendChild(h('option', { value: '', text: '（跳过）' }));
        Object.keys(dim.options || {}).forEach(function (o) { sel.appendChild(h('option', { value: o, text: o })); });
        f.appendChild(sel);
      }
      fields.appendChild(f);
    });
    wrap.appendChild(fields);
    var result = h('div', { style: 'margin-top:8px' });
    wrap.appendChild(result);
    var actions = h('div', { class: 'actions' });
    actions.appendChild(h('button', { class: 'secondary', onclick: closeModal, text: '取消' }));
    actions.appendChild(h('button', { onclick: function () {
      var q = E.severityScore(answers, mode);
      var sev = q.score !== null ? Math.round(q.score) : null;
      aform.severity = sev;
      var msg = '评估完成：' + (sev !== null ? sev + '/10' : '未填（可留空跳过）');
      if (q.red_flag) msg += ' · ⚠️ 命中紧急警示：' + (q.red_flag_hit || '');
      result.innerHTML = '';
      result.appendChild(h('div', { class: 'banner ' + (q.red_flag ? 'danger' : 'ok'), text: msg }));
      closeModal();
      renderAnalyze();
    }, text: '完成并用于分析' }));
    wrap.appendChild(actions);
    openModal(wrap);
  }

  /* ---------- 图表 ---------- */
  function renderCharts() {
    var root = $('tab-charts'); root.innerHTML = '';
    root.appendChild(h('h1', { text: '图表与热力图' }));
    var member = state.config.defaultMember || 'default';
    var sel = h('select', { onchange: function () { state.config.defaultMember = this.value; save(); renderCharts(); } });
    if (state.config.multiMember) {
      state.members.forEach(function (m) { sel.appendChild(h('option', { value: m.id, selected: m.id === member, text: m.name })); });
    } else {
      sel.appendChild(h('option', { value: 'default', text: state.members[0].name }));
    }
    root.appendChild(h('div', { class: 'card', style: 'padding:10px' }, h('label', { class: 'field', text: '成员' }), sel));
    var logs = logsOf(member);
    // 频次柱状图
    root.appendChild(h('h2', { text: '近 90 天症状频次' }));
    var c1 = h('canvas', { style: 'width:100%;height:220px' });
    root.appendChild(c1);
    var cutoff = Date.now() - 90 * 86400000;
    var counts = {};
    logs.forEach(function (l) { var d = E.parseDate(l.date); if (d && d.getTime() >= cutoff) { String(l.symptom || '').split(/[、,，\/]+/).forEach(function (s) { if (s) counts[s] = (counts[s] || 0) + 1; }); } });
    var items = Object.keys(counts).map(function (k) { return { label: k, value: counts[k] }; }).sort(function (a, b) { return b.value - a.value; }).slice(0, 8);
    drawBar(c1, items);
    // 严重程度趋势
    root.appendChild(h('h2', { text: '严重程度趋势（按时间）' }));
    var c2 = h('canvas', { style: 'width:100%;height:180px' });
    root.appendChild(c2);
    var pts = logs.slice().sort(function (a, b) { return String(a.date).localeCompare(String(b.date)); }).map(function (l) { return { label: fmtDate(l.date).slice(5), value: l.severity || 0 }; });
    drawLine(c2, pts);
    // 日历热力图
    root.appendChild(h('h2', { text: '日历热力图' }));
    var now = new Date();
    var yearIn = h('input', { type: 'number', value: now.getFullYear(), style: 'width:90px' });
    var monthSel = h('select', {});
    for (var mi = 1; mi <= 12; mi++) monthSel.appendChild(h('option', { value: mi, selected: mi === now.getMonth() + 1, text: mi + ' 月' }));
    var heat = h('div', { style: 'margin-top:8px' });
    function drawHeat() {
      heat.innerHTML = '';
      renderHeatmap(heat, parseInt(yearIn.value, 10) || now.getFullYear(), parseInt(monthSel.value, 10), member);
    }
    root.appendChild(h('div', { class: 'card', style: 'padding:10px' },
      h('div', { class: 'two-col' }, h('div', {}, h('label', { class: 'field', text: '年份' }), yearIn), h('div', {}, h('label', { class: 'field', text: '月份' }), monthSel)),
      h('button', { class: 'secondary', style: 'margin-top:8px', onclick: drawHeat, text: '生成热力图' })
    ));
    root.appendChild(heat);
    drawHeat();
    root.appendChild(h('div', { class: 'legend' },
      h('span', { class: 'it', text: '■ 无记录' }), h('span', { class: 'it', text: '■ 轻(1-4)' }), h('span', { class: 'it', text: '■ 中(5-6)' }), h('span', { class: 'it', text: '■ 重(7-8)' }), h('span', { class: 'it', text: '■ 极重(9-10)' })
    ));
    root.appendChild(disclaimer());
  }
  function drawBar(canvas, items) {
    var ctx = canvas.getContext('2d');
    var W = canvas.clientWidth || 300, H = canvas.clientHeight || 220;
    var dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr; canvas.height = H * dpr; ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);
    var padL = 26, padB = 24, padT = 14, padR = 6;
    if (!items.length) { ctx.fillStyle = '#9ca3af'; ctx.font = '13px sans-serif'; ctx.fillText('暂无数据', W / 2 - 26, H / 2); return; }
    var max = 1;
    items.forEach(function (it) { if (it.value > max) max = it.value; });
    var bw = (W - padL - padR) / items.length;
    ctx.font = '11px sans-serif';
    items.forEach(function (it, i) {
      var hgt = Math.max(2, (H - padT - padB) * (it.value / max));
      var x = padL + i * bw + bw * 0.2, y = H - padB - hgt, w = bw * 0.6;
      ctx.fillStyle = '#2f9e6e';
      ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, hgt, 4) : ctx.rect(x, y, w, hgt); ctx.fill();
      ctx.fillStyle = '#374151';
      var lab = it.label.length > 4 ? it.label.slice(0, 4) : it.label;
      ctx.fillText(lab, padL + i * bw + (bw - ctx.measureText(lab).width) / 2, H - padB + 14);
      ctx.fillStyle = '#6b7280';
      ctx.fillText(String(it.value), x + (w - ctx.measureText(String(it.value)).width) / 2, y - 3);
    });
    ctx.strokeStyle = '#d1d5db'; ctx.beginPath(); ctx.moveTo(padL, H - padB); ctx.lineTo(W - padR, H - padB); ctx.stroke();
  }
  function drawLine(canvas, pts) {
    var ctx = canvas.getContext('2d');
    var W = canvas.clientWidth || 300, H = canvas.clientHeight || 180;
    var dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr; canvas.height = H * dpr; ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);
    var padL = 26, padB = 20, padT = 10, padR = 8;
    if (pts.length < 2) { ctx.fillStyle = '#9ca3af'; ctx.font = '13px sans-serif'; ctx.fillText(pts.length === 1 ? '只有 1 条记录，暂无法画趋势' : '暂无数据', W / 2 - 80, H / 2); return; }
    var max = 10, min = 0;
    var n = pts.length;
    var innerW = W - padL - padR, innerH = H - padT - padB;
    function X(i) { return padL + (n === 1 ? innerW / 2 : i * innerW / (n - 1)); }
    function Y(v) { return padT + innerH * (1 - (v - min) / (max - min)); }
    // grid lines 0,5,10
    ctx.strokeStyle = '#e5e7eb'; ctx.font = '10px sans-serif'; ctx.fillStyle = '#9ca3af';
    [0, 5, 10].forEach(function (g) { ctx.beginPath(); ctx.moveTo(padL, Y(g)); ctx.lineTo(W - padR, Y(g)); ctx.stroke(); ctx.fillText(String(g), 2, Y(g) + 3); });
    ctx.strokeStyle = '#2f9e6e'; ctx.lineWidth = 2; ctx.beginPath();
    pts.forEach(function (p, i) { if (i === 0) ctx.moveTo(X(i), Y(p.value)); else ctx.lineTo(X(i), Y(p.value)); });
    ctx.stroke();
    ctx.fillStyle = '#dc2626'; ctx.lineWidth = 1;
    pts.forEach(function (p, i) { ctx.beginPath(); ctx.arc(X(i), Y(p.value), 2.5, 0, Math.PI * 2); ctx.fill(); });
    // labels: first, middle, last
    [0, Math.floor(n / 2), n - 1].forEach(function (i) { ctx.fillStyle = '#6b7280'; ctx.fillText(pts[i].label, X(i) - 14, H - 6); });
  }
  function renderHeatmap(container, year, month, member) {
    var logs = logsOf(member);
    var map = {};
    logs.forEach(function (l) {
      var d = E.parseDate(l.date);
      if (d && d.getFullYear() === year && d.getMonth() === month - 1) {
        var key = d.getDate();
        if (!map[key]) map[key] = [];
        map[key].push(l.severity || 0);
      }
    });
    var days = new Date(year, month, 0).getDate();
    var startDow = new Date(year, month - 1, 1).getDay();
    var grid = h('div', { class: 'heat' });
    ['日', '一', '二', '三', '四', '五', '六'].forEach(function (w) { grid.appendChild(h('div', { class: 'wd', text: w })); });
    for (var i = 0; i < startDow; i++) grid.appendChild(h('div', { class: 'cell', text: '' }));
    var now = new Date();
    for (var day = 1; day <= days; day++) {
      var sevs = map[day] || [];
      var avg = sevs.length ? sevs.reduce(function (a, b) { return a + b; }, 0) / sevs.length : 0;
      var bg = '#f3f4f6', fg = '#9ca3af';
      if (avg > 0) {
        if (avg <= 4) { bg = '#bbf7d0'; fg = '#14532d'; }
        else if (avg <= 6) { bg = '#fde68a'; fg = '#713f12'; }
        else if (avg <= 8) { bg = '#fdba74'; fg = '#7c2d12'; }
        else { bg = '#f87171'; fg = '#450a0a'; }
      }
      var isToday = now.getFullYear() === year && now.getMonth() === month - 1 && now.getDate() === day;
      grid.appendChild(h('div', { class: 'cell' + (isToday ? ' today' : ''), style: 'background:' + bg + ';color:' + fg, text: String(day) }));
    }
    container.appendChild(grid);
  }

  /* ---------- 档案页 ---------- */
  function renderProfile() {
    var root = $('tab-profile'); root.innerHTML = '';
    root.appendChild(h('h1', { text: '档案与健康管理' }));
    var sub = 'members';
    var tabs = h('div', { class: 'section-tabs' });
    var content = h('div', {});
    function drawSub() {
      content.innerHTML = '';
      if (sub === 'members') profileMembers(content);
      else if (sub === 'meds') profileMeds(content);
      else if (sub === 'plans') profilePlans(content);
      else if (sub === 'reminders') profileReminders(content);
    }
    [['members', '成员'], ['meds', '用药'], ['plans', '方案'], ['reminders', '提醒']].forEach(function (t) {
      tabs.appendChild(h('button', { class: sub === t[0] ? 'on' : '', onclick: function () { sub = t[0]; drawSub(); }, text: t[1] }));
    });
    root.appendChild(tabs);
    root.appendChild(content);
    drawSub();
  }
  function profileMembers(container) {
    var wrap = h('div', {});
    var multiCard = h('div', { class: 'card' });
    var cb = h('input', { type: 'checkbox', checked: state.config.multiMember, onchange: function () { state.config.multiMember = this.checked; save(); renderProfile(); } });
    multiCard.appendChild(h('div', { style: 'font-weight:600', text: '多家人档案' }));
    multiCard.appendChild(h('label', { class: 'checklist' }, cb, h('span', { text: '开启后可为每位家人单独记录、单独分析' })));
    wrap.appendChild(multiCard);
    var list = h('div', { class: 'card' });
    list.appendChild(h('h3', { text: '成员列表' }));
    state.members.forEach(function (m) {
      var cnt = logsOf(m.id).length;
      var medCnt = medsOf(m.id).length;
      var planCnt = plansOf(m.id).length;
      var row = h('div', { class: 'list-item' },
        h('div', { class: 'main' },
          h('div', { class: 'title', text: m.name + (m.id === state.config.defaultMember ? '（当前）' : '') }),
          h('div', { class: 'muted small', text: (m.relation || '未填') + ' · 记录 ' + cnt + ' · 用药 ' + medCnt + ' · 方案 ' + planCnt })
        )
      );
      if (state.config.multiMember && m.id !== 'default') {
        row.appendChild(h('button', { class: 'small-btn danger', onclick: function () { if (confirm('删除档案「' + m.name + '」？其记录仍会保留但不再关联。')) { state.members = state.members.filter(function (x) { return x.id !== m.id; }); if (state.config.defaultMember === m.id) state.config.defaultMember = 'default'; save(); renderProfile(); } }, text: '删' }));
      }
      list.appendChild(row);
    });
    wrap.appendChild(list);
    if (state.config.multiMember) {
      var addCard = h('div', { class: 'card' });
      addCard.appendChild(h('h3', { text: '新建档案' }));
      var nameIn = h('input', { placeholder: '名字（如：爸爸）' });
      var relIn = h('input', { placeholder: '关系（如：父亲）' });
      addCard.appendChild(h('label', { class: 'field', text: '名字' })); addCard.appendChild(nameIn);
      addCard.appendChild(h('label', { class: 'field', text: '关系' })); addCard.appendChild(relIn);
      addCard.appendChild(h('button', { style: 'margin-top:10px', onclick: function () {
        var n = nameIn.value.trim(); if (!n) { alert('请输入名字'); return; }
        state.members.push({ id: uid(), name: n.slice(0, 12), relation: relIn.value.trim(), note: '', createdAt: todayISO() });
        save(); renderProfile();
      }, text: '添加档案' }));
      wrap.appendChild(addCard);
    }
    container.appendChild(wrap);
  }
  function profileMeds(container) {
    var wrap = h('div', {});
    wrap.appendChild(h('button', { onclick: function () { medForm(null); }, text: '＋ 添加用药' }));
    var list = h('div', { class: 'card' });
    var items = state.meds.slice().sort(function (a, b) { return String(a.end_date || '').localeCompare(String(b.end_date || '')); });
    if (!items.length) list.appendChild(h('div', { class: 'empty', text: '暂无用药记录' }));
    items.forEach(function (m) {
      var active = m.status !== '已停用';
      list.appendChild(h('div', { class: 'list-item' },
        h('span', { class: 'dot ' + (active ? 'mid' : 'low') }),
        h('div', { class: 'main' },
          h('div', { class: 'title', text: m.name + (m.dosage ? ' ' + m.dosage : '') }),
          h('div', { class: 'muted small', text: memberName(m.member) + ' · ' + (m.frequency || '') + (m.start_date ? ' · ' + m.start_date : '') + (m.end_date ? ' 至 ' + m.end_date : '') + (m.status ? ' · ' + m.status : '') })
        ),
        h('button', { class: 'small-btn secondary', onclick: function () { medForm(m.id); }, text: '编辑' }),
        h('button', { class: 'small-btn danger', onclick: function () { if (confirm('删除该用药？')) { state.meds = state.meds.filter(function (x) { return x.id !== m.id; }); save(); renderProfile(); } }, text: '删' })
      ));
    });
    wrap.appendChild(list);
    container.appendChild(wrap);
  }
  function medForm(id) {
    var rec = null;
    state.meds.forEach(function (m) { if (m.id === id) rec = m; });
    var d = rec ? {
      member: rec.member || 'default', name: rec.name || '', dosage: rec.dosage || '', frequency: rec.frequency || '',
      start_date: rec.start_date || '', end_date: rec.end_date || '', status: rec.status || '服用中', note: rec.note || ''
    } : { member: state.config.defaultMember || 'default', name: '', dosage: '', frequency: '', start_date: '', end_date: '', status: '服用中', note: '' };
    var wrap = h('div', {});
    wrap.appendChild(h('h3', { text: id ? '编辑用药' : '添加用药' }));
    var fields = h('div', {});
    if (state.config.multiMember) {
      var sel = h('select', { onchange: function () { d.member = this.value; } });
      state.members.forEach(function (m) { sel.appendChild(h('option', { value: m.id, selected: m.id === d.member, text: m.name })); });
      fields.appendChild(h('label', { class: 'field', text: '成员' })); fields.appendChild(sel);
    }
    function inp(key, ph, type) { var i = h('input', { type: type || 'text', value: d[key], placeholder: ph, oninput: function () { d[key] = this.value; } }); fields.appendChild(h('label', { class: 'field', text: ph })); fields.appendChild(i); return i; }
    inp('name', '药名（如：布洛芬）');
    inp('dosage', '剂量（如：400mg）');
    inp('frequency', '频次（如：每日2次）');
    inp('start_date', '开始日期', 'date');
    inp('end_date', '结束日期（用于停药提醒）', 'date');
    var stSel = h('select', { onchange: function () { d.status = this.value; } },
      ['服用中', '已停用'].map(function (s) { return h('option', { value: s, selected: d.status === s, text: s }); })
    );
    fields.appendChild(h('label', { class: 'field', text: '状态' })); fields.appendChild(stSel);
    wrap.appendChild(fields);
    var actions = h('div', { class: 'actions' });
    actions.appendChild(h('button', { class: 'secondary', onclick: closeModal, text: '取消' }));
    actions.appendChild(h('button', { onclick: function () {
      if (!d.name.trim()) { alert('请填写药名'); return; }
      var obj = { id: id || uid(), member: d.member, name: d.name.trim(), dosage: d.dosage, frequency: d.frequency, start_date: d.start_date, end_date: d.end_date, status: d.status, note: d.note, createdAt: rec ? rec.createdAt : new Date().toISOString() };
      if (id) state.meds = state.meds.map(function (m) { return m.id === id ? obj : m; });
      else state.meds.push(obj);
      save(); closeModal(); renderProfile();
    }, text: '保存' }));
    wrap.appendChild(actions);
    openModal(wrap);
  }
  function profilePlans(container) {
    var wrap = h('div', {});
    wrap.appendChild(h('button', { onclick: function () { planForm(null); }, text: '＋ 添加治疗方案' }));
    var list = h('div', { class: 'card' });
    var items = state.plans.slice().sort(function (a, b) { return String(a.follow_up_date || '').localeCompare(String(b.follow_up_date || '')); });
    if (!items.length) list.appendChild(h('div', { class: 'empty', text: '暂无治疗方案' }));
    items.forEach(function (p) {
      list.appendChild(h('div', { class: 'list-item' },
        h('span', { class: 'dot ' + (p.status === '已执行' ? 'low' : 'urgent') }),
        h('div', { class: 'main' },
          h('div', { class: 'title', text: p.diagnosis || '未命名' }),
          h('div', { class: 'muted small', text: memberName(p.member) + (p.advice ? ' · ' + p.advice : '') + (p.follow_up_date ? ' · 复诊 ' + p.follow_up_date : '') + (p.status ? ' · ' + p.status : '') })
        ),
        h('button', { class: 'small-btn secondary', onclick: function () { planForm(p.id); }, text: '编辑' }),
        h('button', { class: 'small-btn danger', onclick: function () { if (confirm('删除该方案？')) { state.plans = state.plans.filter(function (x) { return x.id !== p.id; }); save(); renderProfile(); } }, text: '删' })
      ));
    });
    wrap.appendChild(list);
    container.appendChild(wrap);
  }
  function planForm(id) {
    var rec = null;
    state.plans.forEach(function (p) { if (p.id === id) rec = p; });
    var d = rec ? { member: rec.member || 'default', diagnosis: rec.diagnosis || '', advice: rec.advice || '', follow_up_date: rec.follow_up_date || '', status: rec.status || '进行中', note: rec.note || '' }
                : { member: state.config.defaultMember || 'default', diagnosis: '', advice: '', follow_up_date: '', status: '进行中', note: '' };
    var wrap = h('div', {});
    wrap.appendChild(h('h3', { text: id ? '编辑方案' : '添加方案' }));
    var fields = h('div', {});
    if (state.config.multiMember) {
      var sel = h('select', { onchange: function () { d.member = this.value; } });
      state.members.forEach(function (m) { sel.appendChild(h('option', { value: m.id, selected: m.id === d.member, text: m.name })); });
      fields.appendChild(h('label', { class: 'field', text: '成员' })); fields.appendChild(sel);
    }
    function inp(key, ph, type) { var i = h('input', { type: type || 'text', value: d[key], placeholder: ph, oninput: function () { d[key] = this.value; } }); fields.appendChild(h('label', { class: 'field', text: ph })); fields.appendChild(i); return i; }
    inp('diagnosis', '诊断 / 名称（如：高血压）');
    inp('advice', '建议（如：按时服药、低盐饮食）');
    inp('follow_up_date', '复诊日期（用于复诊提醒）', 'date');
    var stSel = h('select', { onchange: function () { d.status = this.value; } },
      ['进行中', '已执行'].map(function (s) { return h('option', { value: s, selected: d.status === s, text: s }); })
    );
    fields.appendChild(h('label', { class: 'field', text: '状态' })); fields.appendChild(stSel);
    wrap.appendChild(fields);
    var actions = h('div', { class: 'actions' });
    actions.appendChild(h('button', { class: 'secondary', onclick: closeModal, text: '取消' }));
    actions.appendChild(h('button', { onclick: function () {
      if (!d.diagnosis.trim()) { alert('请填写诊断/名称'); return; }
      var obj = { id: id || uid(), member: d.member, diagnosis: d.diagnosis.trim(), advice: d.advice, follow_up_date: d.follow_up_date, status: d.status, note: d.note, createdAt: rec ? rec.createdAt : new Date().toISOString() };
      if (id) state.plans = state.plans.map(function (p) { return p.id === id ? obj : p; });
      else state.plans.push(obj);
      save(); closeModal(); renderProfile();
    }, text: '保存' }));
    wrap.appendChild(actions);
    openModal(wrap);
  }
  function profileReminders(container) {
    var wrap = h('div', {});
    var days = 14;
    var sel = h('select', { onchange: function () { days = parseInt(this.value, 10); draw(); } },
      [7, 14, 30].map(function (n) { return h('option', { value: n, selected: n === days, text: n + ' 天' }); })
    );
    var box = h('div', {});
    function draw() {
      box.innerHTML = '';
      var rem = E.collectReminders(state.meds, state.plans, days);
      box.appendChild(h('div', { class: 'muted', text: '未来 ' + days + ' 天内（含已逾期）共 ' + rem.length + ' 条' }));
      box.appendChild(remindersView(rem));
    }
    wrap.appendChild(h('div', { class: 'card', style: 'padding:10px' }, h('label', { class: 'field', text: '提醒范围' }), sel));
    wrap.appendChild(box);
    draw();
    wrap.appendChild(disclaimer());
    container.appendChild(wrap);
  }

  /* ---------- 设置页 ---------- */
  function renderSettings() {
    var root = $('tab-settings'); root.innerHTML = '';
    root.appendChild(h('h1', { text: '设置' }));
    var cfg = h('div', { class: 'card' });
    cfg.appendChild(h('h3', { text: '常用就诊位置' }));
    var cityIn = h('input', { value: state.config.city || '', placeholder: '城市（如：杭州）', oninput: function () { state.config.city = this.value; save(); } });
    var provIn = h('input', { value: state.config.province || '', placeholder: '省份（如：浙江）', oninput: function () { state.config.province = this.value; save(); } });
    cfg.appendChild(h('div', { class: 'two-col' }, h('div', {}, h('label', { class: 'field', text: '城市' }), cityIn), h('div', {}, h('label', { class: 'field', text: '省份' }), provIn)));
    root.appendChild(cfg);
    var dataCard = h('div', { class: 'card' });
    dataCard.appendChild(h('h3', { text: '数据备份' }));
    dataCard.appendChild(h('div', { class: 'muted', text: '数据仅保存在本浏览器中，请定期导出备份。' }));
    var btnRow = h('div', { class: 'btn-row' });
    btnRow.appendChild(h('button', { onclick: exportData, text: '⬇ 导出备份' }));
    btnRow.appendChild(h('button', { class: 'secondary', onclick: function () { $('importFile').click(); }, text: '⬆ 导入备份' }));
    dataCard.appendChild(btnRow);
    dataCard.appendChild(h('input', { id: 'importFile', type: 'file', accept: '.json', class: 'hidden', onchange: importData }));
    dataCard.appendChild(h('button', { class: 'danger', style: 'margin-top:10px', onclick: function () {
      if (confirm('确定清空全部数据？此操作不可恢复！')) {
        if (confirm('再次确认：真的要清空所有记录、用药和方案吗？')) {
          state = defaultState(); save(); renderCurrent();
        }
      }
    }, text: '🗑 清空全部数据' }));
    root.appendChild(dataCard);
    var about = h('div', { class: 'card' });
    about.appendChild(h('h3', { text: '关于' }));
    about.appendChild(h('div', { text: '🩺 健康管理（Health Condition Tracker）网页版' }));
    about.appendChild(h('div', { class: 'muted', text: '功能：病情记录、风险分级、国际就诊路径、科室/医院推荐、图表热力图、用药与复诊提醒、多家人档案、数据导入导出。' }));
    about.appendChild(h('div', { class: 'muted', style: 'margin-top:6px', text: '风险分级算法与桌面版 skill 一致（100+16 组回归测试通过）。' }));
    about.appendChild(h('div', { class: 'muted', style: 'margin-top:6px' }, '指令选择器（桌面 Codex 版）：', h('a', { href: 'selector.html', text: '打开' })));
    root.appendChild(about);
    root.appendChild(disclaimer());
  }
  function exportData() {
    var payload = { version: 1, exportedAt: new Date().toISOString(), data: state };
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'health-backup-' + todayISO() + '.json';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
  }
  function importData(ev) {
    var file = ev.target.files && ev.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var obj = JSON.parse(reader.result);
        var incoming = obj && obj.data && obj.data.config ? obj.data : obj;
        if (!incoming.config || !Array.isArray(incoming.members)) { alert('文件格式不正确'); return; }
        state = incoming; save(); renderCurrent();
        alert('导入成功：' + state.logs.length + ' 条记录、' + state.meds.length + ' 条用药、' + state.plans.length + ' 条方案。');
      } catch (e) { alert('导入失败：' + e.message); }
    };
    reader.readAsText(file);
    ev.target.value = '';
  }

  /* ---------- 初始化 ---------- */
  function init() {
    if (!$('modalMask')) return;
    showTab('home');
  }
  document.addEventListener('DOMContentLoaded', init);
  return { init: init, showTab: showTab };
})();
