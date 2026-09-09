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
  const recurveGraph = document.getElementById('recurveGraph');
  const recurveReadout = document.getElementById('recurveReadout');
  let lastTable = null;
  let engineRequest = null;
  let generationRequest = null;
  let engineRevision = 0;
  let generationRevision = 0;

  const numericFields = [
    'displacement_cc','peak_hp','peak_hp_rpm','peak_torque_lbft','peak_torque_rpm','redline_rpm',
    'cranking_rpm','cranking_timing','base_timing','mech_timing_at_peak_torque',
    'recurve_rpm_1','recurve_timing_1','recurve_rpm_2','recurve_timing_2','recurve_rpm_3','recurve_timing_3',
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

  function n(name, fallback=0) {
    const el = form.elements[name];
    const value = el ? Number(el.value) : NaN;
    return Number.isFinite(value) ? value : fallback;
  }

  function idlePocketLowerRpm() {
    const idle = n('idle_rpm',750);
    const width = Math.max(0,n('idle_pocket_width',100));
    const lower = Math.max(0,n('idle_pocket_lower_share',.25));
    const upper = Math.max(0,n('idle_pocket_upper_share',.75));
    const total = lower + upper;
    const lowerShare = total > 0 ? lower / total : .25;
    return Math.max(n('cranking_rpm',500), idle - width * lowerShare);
  }

  function svgEl(tag, attrs={}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
    return el;
  }

  function addText(svg, x, y, text, cls='curve-label', anchor='middle') {
    const el = svgEl('text', {x, y, class:cls, 'text-anchor':anchor});
    el.textContent = text;
    svg.appendChild(el);
    return el;
  }

  function pchipSlopes(xs, ys) {
    const count = xs.length;
    if (count === 2) {
      const slope = (ys[1]-ys[0])/(xs[1]-xs[0]);
      return [slope, slope];
    }
    const h = [], delta = [], d = new Array(count).fill(0);
    for (let i=0;i<count-1;i++) {
      h.push(xs[i+1]-xs[i]);
      delta.push((ys[i+1]-ys[i])/h[i]);
    }
    for (let i=1;i<count-1;i++) {
      if (delta[i-1] === 0 || delta[i] === 0 || delta[i-1]*delta[i] <= 0) d[i] = 0;
      else {
        const w1 = 2*h[i] + h[i-1];
        const w2 = h[i] + 2*h[i-1];
        d[i] = (w1+w2)/(w1/delta[i-1] + w2/delta[i]);
      }
    }
    let d0 = ((2*h[0]+h[1])*delta[0]-h[0]*delta[1])/(h[0]+h[1]);
    if (d0*delta[0] <= 0) d0 = 0;
    else if (delta[0]*delta[1] < 0 && Math.abs(d0) > Math.abs(3*delta[0])) d0 = 3*delta[0];
    d[0] = d0;
    let dn = ((2*h.at(-1)+h.at(-2))*delta.at(-1)-h.at(-1)*delta.at(-2))/(h.at(-1)+h.at(-2));
    if (dn*delta.at(-1) <= 0) dn = 0;
    else if (delta.at(-1)*delta.at(-2) < 0 && Math.abs(dn) > Math.abs(3*delta.at(-1))) dn = 3*delta.at(-1);
    d[count-1] = dn;
    return d;
  }

  function pchipValue(x, xs, ys, slopes) {
    if (x <= xs[0]) return ys[0];
    if (x >= xs.at(-1)) return ys.at(-1);
    let i = 0;
    while (i+1 < xs.length && x > xs[i+1]) i++;
    const h = xs[i+1]-xs[i];
    const t = (x-xs[i])/h;
    const h00 = 2*t*t*t - 3*t*t + 1;
    const h10 = t*t*t - 2*t*t + t;
    const h01 = -2*t*t*t + 3*t*t;
    const h11 = t*t*t - t*t;
    return h00*ys[i] + h10*h*slopes[i] + h01*ys[i+1] + h11*h*slopes[i+1];
  }

  function graphScales(xMin, xMax, yMin, yMax) {
    const left=62, right=24, top=20, bottom=42, width=900, height=260;
    return {
      x:v => left + (v-xMin)/Math.max(1,xMax-xMin)*(width-left-right),
      y:v => top + (yMax-v)/Math.max(1,yMax-yMin)*(height-top-bottom),
      invX:px => xMin + (px-left)/(width-left-right)*(xMax-xMin),
      invY:py => yMax - (py-top)/(height-top-bottom)*(yMax-yMin),
      left,right,top,bottom,width,height
    };
  }

  function drawGrid(svg, scales, xMin, xMax, yMin, yMax, xLabel) {
    for (let i=0;i<=5;i++) {
      const xValue = xMin + (xMax-xMin)*i/5;
      const x = scales.x(xValue);
      svg.appendChild(svgEl('line',{x1:x,y1:scales.top,x2:x,y2:scales.height-scales.bottom,class:'curve-grid'}));
      addText(svg,x,scales.height-18,Math.round(xValue).toString());
    }
    for (let i=0;i<=4;i++) {
      const yValue = yMin + (yMax-yMin)*i/4;
      const y = scales.y(yValue);
      svg.appendChild(svgEl('line',{x1:scales.left,y1:y,x2:scales.width-scales.right,y2:y,class:'curve-grid'}));
      addText(svg,scales.left-10,y+4,`${Math.round(yValue)}°`,'curve-label','end');
    }
    svg.appendChild(svgEl('line',{x1:scales.left,y1:scales.top,x2:scales.left,y2:scales.height-scales.bottom,class:'curve-axis'}));
    svg.appendChild(svgEl('line',{x1:scales.left,y1:scales.height-scales.bottom,x2:scales.width-scales.right,y2:scales.height-scales.bottom,class:'curve-axis'}));
    addText(svg,(scales.left+scales.width-scales.right)/2,scales.height-3,xLabel);
    addText(svg,16,(scales.top+scales.height-scales.bottom)/2,'Timing', 'curve-label');
  }

  function renderRecurveGraph() {
    if (!recurveGraph) return;
    const idle = n('idle_rpm',750);
    const pocketLo = idlePocketLowerRpm();
    const peak = n('peak_torque_rpm',3500);
    const base = n('base_timing',15);
    const full = n('mech_timing_at_peak_torque',36);
    const p1 = [n('recurve_rpm_1',idle+(peak-idle)*.25),n('recurve_timing_1',base+(full-base)*.25),1];
    const p2 = [n('recurve_rpm_2',idle+(peak-idle)*.5),n('recurve_timing_2',base+(full-base)*.5),2];
    const p3 = [n('recurve_rpm_3',idle+(peak-idle)*.75),n('recurve_timing_3',base+(full-base)*.75),3];
    const controlPoints = [p1,p2,p3];
    const curvePoints = p1[0] <= idle
      ? [p1,p2,p3,[peak,full,'fixed']]
      : [[idle,base,'fixed'],p1,p2,p3,[peak,full,'fixed']];
    const displayPoints = [[idle,base,'base'],...controlPoints,[peak,full,'fixed']];
    const ys = displayPoints.map(p=>p[1]);
    let yMin = Math.min(...ys)-4, yMax=Math.max(...ys)+4;
    if (yMax-yMin < 16) { const mid=(yMax+yMin)/2; yMin=mid-8; yMax=mid+8; }
    const scales = graphScales(pocketLo,peak,yMin,yMax);
    recurveGraph.replaceChildren();
    drawGrid(recurveGraph,scales,pocketLo,peak,yMin,yMax,'RPM');

    const xs=curvePoints.map(p=>p[0]), values=curvePoints.map(p=>p[1]), slopes=pchipSlopes(xs,values);
    let d='';
    for (let i=0;i<=100;i++) {
      const rpm=idle+(peak-idle)*i/100;
      const timing=pchipValue(rpm,xs,values,slopes);
      d += `${i?'L':'M'} ${scales.x(rpm).toFixed(1)} ${scales.y(timing).toFixed(1)} `;
    }
    recurveGraph.appendChild(svgEl('path',{d,class:'curve-line'}));

    displayPoints.forEach(([rpm,timing,index]) => {
      const x=scales.x(rpm), y=scales.y(timing);
      const fixed = index === 'fixed' || index === 'base';
      const circle=svgEl('circle',{cx:x,cy:y,r:fixed?6:8,class:fixed?'curve-point-fixed':'curve-point'});
      recurveGraph.appendChild(circle);
      const label = index === 'base'
        ? `Base ${Math.round(rpm)} / ${timing.toFixed(1)}°`
        : index === 'fixed'
          ? `${Math.round(rpm)} / ${timing.toFixed(1)}°`
          : `P${index} ${Math.round(rpm)} / ${timing.toFixed(1)}°`;
      addText(recurveGraph,x,y-13,label,'curve-value');
      if (!fixed) bindRecurveDrag(circle,index,scales,yMin,yMax);
    });
    recurveReadout.textContent = `Idle pocket lower edge: ${Math.round(pocketLo)} RPM. P1 may sit at idle (${Math.round(idle)} RPM); protected pocket cells still override the recurve.`;
  }

  function bindRecurveDrag(circle,index,scales,yMin,yMax) {
    circle.addEventListener('pointerdown', event => {
      event.preventDefault();
      circle.setPointerCapture(event.pointerId);
      const move = e => {
        const rect=recurveGraph.getBoundingClientRect();
        const px=(e.clientX-rect.left)*900/rect.width;
        const py=(e.clientY-rect.top)*260/rect.height;
        const idle=n('idle_rpm',750), peak=n('peak_torque_rpm',3500);
        const previous=index===1?idle:n(`recurve_rpm_${index-1}`,idle);
        const next=index===3?peak:n(`recurve_rpm_${index+1}`,peak);
        let rpm=Math.round(scales.invX(px)/10)*10;
        const minRpm=index===1?previous:previous+10;
        rpm=Math.max(minRpm,Math.min(next-10,rpm));
        let timing=Math.round(scales.invY(py)*10)/10;
        timing=Math.max(yMin,Math.min(yMax,timing));
        form.elements[`recurve_rpm_${index}`].value=rpm;
        form.elements[`recurve_timing_${index}`].value=timing.toFixed(1);
        renderRecurveGraph();
      };
      const up = e => {
        circle.releasePointerCapture?.(e.pointerId);
        window.removeEventListener('pointermove',move);
        window.removeEventListener('pointerup',up);
      };
      window.addEventListener('pointermove',move);
      window.addEventListener('pointerup',up,{once:true});
    });
  }

  function renderCurveEditors() {
    renderRecurveGraph();
  }

  function fillSpec(spec) {
    numericFields.forEach(name => {
      const el = form.elements[name];
      if (el && spec[name] !== undefined && spec[name] !== null) el.value = spec[name];
    });
    renderCurveEditors();
  }

  function clearGeneratedTable() {
    lastTable = null;
    tableWrap.replaceChildren();
    tableMeta.textContent = 'No generated table';
  }

  async function loadEngine(name) {
    const revision = ++engineRevision;

    if (engineRequest) engineRequest.abort();
    if (generationRequest) {
      generationRequest.abort();
      generationRequest = null;
      generationRevision += 1;
    }

    engineRequest = new AbortController();
    clearGeneratedTable();
    generateButton.disabled = true;
    setStatus('LOADING', 'busy');
    message.textContent = 'Loading engine defaults…';

    try {
      const response = await fetch(`/api/engine/${encodeURIComponent(name)}`, {
        cache:'no-store',
        signal:engineRequest.signal
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to load engine');
      if (revision !== engineRevision || name !== engineSelect.value) return;

      fillSpec(data);
      message.textContent = `${data.name}: ${data.description}`;
      setStatus('READY', 'ready');
    } catch (error) {
      if (error.name === 'AbortError') return;
      if (revision !== engineRevision) return;
      message.textContent = error.message;
      setStatus('ERROR', 'error');
    } finally {
      if (revision === engineRevision) {
        engineRequest = null;
        generateButton.disabled = false;
      }
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

    if (t < .08) return 'var(--cell0)';
    if (t < .17) return 'var(--cell1)';
    if (t < .26) return 'var(--cell2)';
    if (t < .35) return 'var(--cell3)';
    if (t < .44) return 'var(--cell4)';
    if (t < .54) return 'var(--cell5)';
    if (t < .64) return 'var(--cell6)';
    if (t < .74) return 'var(--cell7)';
    if (t < .84) return 'var(--cell8)';
    if (t < .93) return 'var(--cell9)';
    return 'var(--cell10)';
  }

  function timingCell(data, rpmIndex, loadIndex, min, max) {
    const value = data.timing[rpmIndex][loadIndex];
    const td = document.createElement('td');
    td.className = 'timing' + (Math.abs(data.load_kpa[loadIndex] - 100) < .51 ? ' atm' : '');
    td.textContent = value;
    td.style.background = cellColor(value, min, max);
    const inhg = Array.isArray(data.load_inhg_gauge) ? data.load_inhg_gauge[loadIndex] : null;
    const alphaNote = inhg === null ? '' : ` / ${inhg} inHg gauge`;
    td.title = `${data.rpm[rpmIndex]} RPM / ${data.load_kpa[loadIndex]} kPa abs${alphaNote} = ${value}° BTDC`;
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
    first.textContent = 'RPM/inHg';
    hr.appendChild(first);

    const alphaLoad = Array.isArray(data.load_inhg_gauge) ? data.load_inhg_gauge : data.load_kpa;
    alphaLoad.forEach((load, loadIndex) => {
      const th = document.createElement('th');
      th.textContent = Number(load).toFixed(2).replace(/\.00$/, '');
      if (Math.abs(data.load_kpa[loadIndex] - 100) < .51) th.classList.add('atm-head');
      th.title = `${data.load_kpa[loadIndex]} kPa absolute`;
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
    if (!data || !Array.isArray(data.timing) || !data.timing.length) return;
    const values = data.timing.flat();
    if (!values.length) return;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const mode = viewMode.value || 'default';
    const table = mode === 'alpha' ? renderAlpha(data, min, max) : renderDefault(data, min, max);
    tableWrap.replaceChildren(table);
    const loadUnit = mode === 'alpha' ? 'inHg gauge' : 'kPa abs';
    tableMeta.textContent = `${data.engine} · ${data.load_kpa.length} load × ${data.rpm.length} RPM · ${min}°…${max}° BTDC · view=${mode} (${loadUnit}) · export=${exportMode.value}`;
  }

  async function generate(event) {
    event.preventDefault();
    if (engineRequest) return;

    const revision = ++generationRevision;
    const engineAtStart = engineSelect.value;
    if (generationRequest) generationRequest.abort();
    generationRequest = new AbortController();

    generateButton.disabled = true;
    engineSelect.disabled = true;
    setStatus('GENERATING', 'busy');
    message.textContent = 'Generating ignition surface…';

    try {
      const response = await fetch('/api/generate', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(buildPayload()),
        signal:generationRequest.signal
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Generation failed');
      if (revision !== generationRevision || engineAtStart !== engineSelect.value) return;

      lastTable = data;
      renderTable(data);
      const recurve = Array.isArray(data.recurve)
        ? ` Recurve: ${data.recurve.map(p => `${p.rpm}@${p.timing}°`).join(', ')}.`
        : '';
      message.textContent = `Generated ${data.schema}. 100 kPa / 0 inHg crossover is outlined in cyan.${recurve}`;
      setStatus('GENERATED', 'ready');
    } catch (error) {
      if (error.name === 'AbortError') return;
      if (revision !== generationRevision) return;
      message.textContent = error.message;
      setStatus('ERROR', 'error');
    } finally {
      if (revision === generationRevision) {
        generationRequest = null;
        generateButton.disabled = false;
        engineSelect.disabled = false;
      }
    }
  }

  async function init() {
    form.addEventListener('submit', generate);
    form.addEventListener('input', event => {
      if (event.target instanceof HTMLInputElement && numericFields.includes(event.target.name)) renderCurveEditors();
    });
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