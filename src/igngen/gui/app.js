(() => {
  const form = document.getElementById('configForm');
  const engineSelect = document.getElementById('engine');
  const viewMode = document.getElementById('viewMode');
  const exportMode = document.getElementById('exportMode');
  const tableWrap = document.getElementById('tableWrap');
  const tableMeta = document.getElementById('tableMeta');
  const statusPill = document.getElementById('statusPill');
  const message = document.getElementById('message');
  const generateButton = form.querySelector('.generate');
  let lastTable = null;

  const numericFields = [
    'displacement_cc','peak_hp','peak_hp_rpm','peak_torque_lbft','peak_torque_rpm','redline_rpm',
    'cranking_rpm','cranking_timing','base_timing','mech_timing_at_peak_torque',
    'vacuum_full_map_kpa','vacuum_total_timing','boost_psi','boost_timing_limit','boost_retard_gain',
    'idle_rpm','idle_pocket_width','idle_pocket_lower_share','idle_pocket_upper_share',
    'idle_timing_target','idle_timing_delta','idle_map_lo','idle_map_hi',
    'soft_limit_rpm_before_redline','soft_limit_retard','overspeed_rpm_after_redline'
  ];

  function setStatus(text, kind='ready') {
    statusPill.textContent = text;
    statusPill.style.color = kind === 'error' ? 'var(--danger)' : kind === 'busy' ? 'var(--amber)' : 'var(--green)';
    message.className = 'message' + (kind === 'error' ? ' error' : kind === 'ready' ? ' ok' : '');
  }

  function fillSpec(spec) {
    numericFields.forEach(name => {
      const el = form.elements[name];
      if (el && spec[name] !== undefined && spec[name] !== null) el.value = spec[name];
    });
  }

  async function loadEngine(name) {
    setStatus('LOADING', 'busy');
    message.textContent = 'Loading engine defaults…';
    try {
      const response = await fetch(`/api/engine/${encodeURIComponent(name)}`, {cache:'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to load engine');
      fillSpec(data);
      message.textContent = `${data.name}: ${data.description}`;
      setStatus('READY', 'ready');
    } catch (error) {
      message.textContent = error.message;
      setStatus('ERROR', 'error');
    }
  }

  function buildPayload() {
    const data = new FormData(form);
    const payload = {engine: engineSelect.value, view: viewMode.value, export: exportMode.value};
    for (const [key, value] of data.entries()) {
      if (key === 'engine' || key === 'view' || key === 'export') continue;
      if (value !== '') payload[key] = Number(value);
    }
    return payload;
  }

  function cellColor(value, min, max) {
    const span = Math.max(1, max - min);
    const t = Math.max(0, Math.min(1, (value - min) / span));
    if (t < .14) return 'var(--cell0)';
    if (t < .30) return 'var(--cell1)';
    if (t < .47) return 'var(--cell2)';
    if (t < .64) return 'var(--cell3)';
    if (t < .80) return 'var(--cell4)';
    if (t < .92) return 'var(--cell5)';
    return 'var(--cell6)';
  }

  function timingCell(data, rpmIndex, loadIndex, min, max) {
    const value = data.timing[rpmIndex][loadIndex];
    const td = document.createElement('td');
    td.className = 'timing' + (Math.abs(data.load_kpa[loadIndex] - 100) < .51 ? ' atm' : '');
    td.textContent = value;
    td.style.background = cellColor(value, min, max);
    td.title = `${data.rpm[rpmIndex]} RPM / ${data.load_kpa[loadIndex]} kPa = ${value}° BTDC`;
    return td;
  }

  function renderDefault(data, min, max) {
    const table = document.createElement('table');
    table.className = 'default-view';
    const tbody = document.createElement('tbody');
    const loadOrder = [...data.load_kpa.keys()].reverse();

    loadOrder.forEach(loadIndex => {
      const tr = document.createElement('tr');
      const loadCell = document.createElement('td');
      loadCell.className = 'load';
      loadCell.textContent = data.load_kpa[loadIndex];
      tr.appendChild(loadCell);
      data.rpm.forEach((_, rpmIndex) => tr.appendChild(timingCell(data, rpmIndex, loadIndex, min, max)));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    const tfoot = document.createElement('tfoot');
    const hr = document.createElement('tr');
    const first = document.createElement('th');
    first.className = 'load-head';
    first.textContent = 'kPa/RPM';
    hr.appendChild(first);
    data.rpm.forEach(rpm => {
      const th = document.createElement('th');
      th.textContent = rpm;
      hr.appendChild(th);
    });
    tfoot.appendChild(hr);
    table.appendChild(tfoot);
    return table;
  }

  function renderAlpha(data, min, max) {
    const table = document.createElement('table');
    table.className = 'alpha-view';
    const thead = document.createElement('thead');
    const hr = document.createElement('tr');
    const first = document.createElement('th');
    first.className = 'load-head';
    first.textContent = 'RPM/kPa';
    hr.appendChild(first);
    data.load_kpa.forEach(load => {
      const th = document.createElement('th');
      th.textContent = load;
      if (Math.abs(load - 100) < .51) th.classList.add('atm-head');
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    data.rpm.forEach((rpm, rpmIndex) => {
      const tr = document.createElement('tr');
      const rpmCell = document.createElement('td');
      rpmCell.className = 'load';
      rpmCell.textContent = rpm;
      tr.appendChild(rpmCell);
      data.load_kpa.forEach((_, loadIndex) => tr.appendChild(timingCell(data, rpmIndex, loadIndex, min, max)));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  function renderTable(data) {
    const values = data.timing.flat();
    const min = Math.min(...values);
    const max = Math.max(...values);
    const mode = viewMode.value || 'default';
    const table = mode === 'alpha' ? renderAlpha(data, min, max) : renderDefault(data, min, max);
    tableWrap.replaceChildren(table);
    tableMeta.textContent = `${data.engine} · ${data.load_kpa.length} load × ${data.rpm.length} RPM · ${min}°…${max}° BTDC · view=${mode} · export=${exportMode.value}`;
  }

  async function generate(event) {
    event.preventDefault();
    generateButton.disabled = true;
    setStatus('GENERATING', 'busy');
    message.textContent = 'Generating V2 ignition surface…';
    try {
      const response = await fetch('/api/generate', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(buildPayload())
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Generation failed');
      lastTable = data;
      renderTable(data);
      message.textContent = `Generated ${data.schema}. 100 kPa crossover is outlined in cyan.`;
      setStatus('GENERATED', 'ready');
    } catch (error) {
      message.textContent = error.message;
      setStatus('ERROR', 'error');
    } finally {
      generateButton.disabled = false;
    }
  }

  async function init() {
    form.addEventListener('submit', generate);
    engineSelect.addEventListener('change', () => loadEngine(engineSelect.value));
    viewMode.addEventListener('change', () => { if (lastTable) renderTable(lastTable); });
    exportMode.addEventListener('change', () => { if (lastTable) renderTable(lastTable); });
    try {
      const response = await fetch('/api/engines', {cache:'no-store'});
      const data = await response.json();
      engineSelect.replaceChildren();
      data.engines.forEach((engine, index) => {
        const option = document.createElement('option');
        option.value = engine.id;
        option.textContent = `${engine.name} — ${engine.description}`;
        if (engine.id.toLowerCase() === 'd16z6' || index === 0) option.selected = true;
        engineSelect.appendChild(option);
      });
      const custom = document.createElement('option');
      custom.value = 'other';
      custom.textContent = 'Custom / Other';
      engineSelect.appendChild(custom);
      await loadEngine(engineSelect.value || 'other');
    } catch (error) {
      message.textContent = error.message;
      setStatus('ERROR', 'error');
    }
  }

  init();
})();
