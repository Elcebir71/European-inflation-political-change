const $ = (id) => document.getElementById(id);
const countrySelect = $("countrySelect");

const countryNames = {
  AT: "Austria", BE: "Belgium", BG: "Bulgaria", HR: "Croatia",
  CY: "Cyprus", CZ: "Czechia", DK: "Denmark", EE: "Estonia",
  FI: "Finland", FR: "France", DE: "Germany", GR: "Greece",
  HU: "Hungary", IE: "Ireland", IT: "Italy", LV: "Latvia",
  LT: "Lithuania", LU: "Luxembourg", MT: "Malta", NL: "Netherlands",
  PL: "Poland", PT: "Portugal", RO: "Romania", SK: "Slovakia",
  SI: "Slovenia", ES: "Spain", SE: "Sweden", GB: "United Kingdom"
};

// Approximate capital coordinates, used only to place dots on a schematic
// (non-geographic-projection) map. Not survey-accurate.
const countryCoords = {
  AT: [16.37, 48.20], BE: [4.35, 50.85], BG: [23.32, 42.70], HR: [15.98, 45.80],
  CY: [33.36, 35.17], CZ: [14.44, 50.08], DK: [12.57, 55.68], EE: [24.75, 59.44],
  FI: [24.94, 60.17], FR: [2.35, 48.85], DE: [13.40, 52.52], GR: [23.73, 37.98],
  HU: [19.04, 47.50], IE: [-6.26, 53.35], IT: [12.50, 41.90], LV: [24.11, 56.95],
  LT: [25.28, 54.69], LU: [6.13, 49.61], MT: [14.51, 35.90], NL: [4.90, 52.37],
  PL: [21.01, 52.23], PT: [-9.14, 38.72], RO: [26.10, 44.43], SK: [17.11, 48.15],
  SI: [14.51, 46.06], ES: [-3.70, 40.42], SE: [18.07, 59.33], GB: [-0.13, 51.51]
};

const latestElectionInAnalysisWindow = {
  AT: "2024-09-29", BE: "2024-06-09", BG: "2024-10-27", HR: "2024-04-17",
  CY: "2021-05-30", CZ: "2021-10-09", DK: "2022-11-01", EE: "2023-03-05",
  FI: "2023-04-02", FR: "2024-07-07", DE: "2021-09-26", GR: "2023-06-25",
  HU: "2022-04-03", IE: "2024-11-29", IT: "2022-09-25", LV: "2022-10-01",
  LT: "2024-10-27", LU: "2023-10-08", MT: "2022-03-26", NL: "2023-11-22",
  PL: "2023-10-15", PT: "2024-03-10", RO: "2024-12-01", SK: "2023-09-30",
  SI: "2022-04-24", ES: "2023-07-23", SE: "2022-09-11", GB: "2024-07-04"
};

const modelDescriptions = {
  V1: "Inflation only",
  V2: "Inflation + unemployment + GDP growth",
  V3: "V2 + asylum + Ukraine temporary protection",
  V4: "Inflation + migration-pressure index + controls"
};

const FEATURE_LABELS = {
  inflation_12m_avg: "Inflation (12m avg)",
  unemployment_rate: "Unemployment rate",
  gdp_growth: "GDP growth",
  asylum_per_100k: "Asylum per 100k",
  ukraine_tp_per_100k: "Ukraine temp. protection per 100k",
  migration_pressure_index: "Migration-pressure index"
};

const MODEL_COLORS = { V1: "#22d3ee", V2: "#8b5cf6", V3: "#34d399", V4: "#fbbf24" };

function fmtFeature(name) {
  return FEATURE_LABELS[name] ?? name.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}
function fmtNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

// ---------------------------------------------------------------------------
// Extra styles injected at runtime, so this file is a drop-in addition and
// does not require editing the existing stylesheet.
// ---------------------------------------------------------------------------
(function injectStyles() {
  const style = document.createElement("style");
  style.textContent = `
    .map-card, .coef-card { margin-top: 20px; }
    #europeMap { width: 100%; height: auto; display: block; }
    .risk-dot { cursor: pointer; stroke: rgba(255,255,255,.35); stroke-width: 1;
      transition: r .25s ease, opacity .25s ease, stroke .25s ease; }
    .risk-dot:hover { opacity: .85; }
    .risk-dot.selected { stroke: #ffffff; stroke-width: 2.5; }
    .risk-dot-anim { animation: dotIn .4s ease both; }
    @keyframes dotIn { from { r: 0; opacity: 0; } to { opacity: 1; } }
    .map-legend { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; color: var(--muted, #8a9bb8); }
    .map-legend .grad { flex: 1; height: 8px; border-radius: 999px;
      background: linear-gradient(90deg, #34d399, #fbbf24, #f87171); max-width: 220px; }
    .map-toggle { display: flex; gap: 6px; margin: 10px 0; }
    .map-toggle-btn { background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.12);
      color: var(--muted, #8a9bb8); padding: 5px 12px; border-radius: 999px; font-size: 12px;
      cursor: pointer; transition: background .2s, color .2s, border-color .2s; }
    .map-toggle-btn:hover { border-color: rgba(255,255,255,.3); }
    .map-toggle-btn.active { background: #22d3ee; border-color: #22d3ee; color: #0b1220; font-weight: 600; }
    .coef-row { display: grid; grid-template-columns: 190px 1fr; align-items: center; gap: 10px; margin: 10px 0; }
    .coef-row .label { font-size: 13px; color: var(--muted, #8a9bb8); }
    .coef-bars { position: relative; height: 26px; background: rgba(255,255,255,.05); border-radius: 6px; }
    .coef-bars .zero { position: absolute; top: 0; bottom: 0; width: 1px; background: rgba(255,255,255,.25); }
    .coef-bar { position: absolute; top: 3px; height: 4px; border-radius: 3px;
      transform-origin: left center; transform: scaleX(0); animation: growBar .5s ease forwards; }
    @keyframes growBar { to { transform: scaleX(1); } }
    .coef-legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; }
    .coef-legend span { display: inline-flex; align-items: center; gap: 6px; color: var(--muted, #8a9bb8); }
    .coef-legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
    .chart-line, .chart-area { transition: d .5s ease; }
    .prob-row .bar span { transition: width .6s ease; }
  `;
  document.head.appendChild(style);
})();

function drawChart(points) {
  const svg = $("inflationChart");
  const width = 900, height = 330;
  const pad = { left: 48, right: 18, top: 18, bottom: 42 };
  const values = points.map(p => Number(p.inflationYoy));
  const min = Math.min(0, ...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const x = i => pad.left + i * (width - pad.left - pad.right) / Math.max(points.length - 1, 1);
  const y = v => pad.top + (max - v) * (height - pad.top - pad.bottom) / range;
  const line = points.map((p,i) => `${x(i)},${y(Number(p.inflationYoy))}`).join(" ");
  const area = `${pad.left},${height-pad.bottom} ${line} ${x(points.length-1)},${height-pad.bottom}`;
  const ticks = 5;
  let markup = "";
  for (let i=0; i<ticks; i++) {
    const v = min + (max-min) * i/(ticks-1);
    const yy = y(v);
    markup += `<line class="chart-grid" x1="${pad.left}" x2="${width-pad.right}" y1="${yy}" y2="${yy}"></line>`;
    markup += `<text class="chart-axis" x="8" y="${yy+4}">${v.toFixed(1)}%</text>`;
  }
  const labels = [0, Math.floor(points.length/2), points.length-1];
  labels.forEach(i => {
    if (points[i]) markup += `<text class="chart-axis" text-anchor="middle" x="${x(i)}" y="${height-12}">${points[i].month}</text>`;
  });
  markup += `<polygon class="chart-area" points="${area}"></polygon><polyline class="chart-line" points="${line}"></polyline>`;
  svg.innerHTML = markup;
}

// ---------------------------------------------------------------------------
// Europe risk map
// ---------------------------------------------------------------------------
const MAP_W = 820, MAP_H = 620;
const LON_MIN = -13, LON_MAX = 33, LAT_MIN = 33, LAT_MAX = 71;

function project([lon, lat]) {
  const x = 20 + (lon - LON_MIN) / (LON_MAX - LON_MIN) * (MAP_W - 40);
  const y = MAP_H - 20 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN) * (MAP_H - 40);
  return [x, y];
}

// Green (low) -> amber -> red (high), for a 0..1 probability.

function riskColor(p) {
  if (p === null || Number.isNaN(p)) return "#475569"; // unknown -> grey
  const stops = [[52, 211, 153], [251, 191, 36], [248, 113, 113]]; // green -> amber -> red, all 0-255
  const t = Math.max(0, Math.min(1, p)) * 2;
  const [c0, c1] = t <= 1 ? [stops[0], stops[1]] : [stops[1], stops[2]];
  const f = t <= 1 ? t : t - 1;
  const mix = (a, b) => Math.round(a + (b - a) * f);
  return `rgb(${mix(c0[0], c1[0])},${mix(c0[1], c1[1])},${mix(c0[2], c1[2])})`;
}
let riskCache = []; // [{code, probsByModel: {V1: 0.5, V2: ...}}]
let currentMapModel = "V1";

function renderMapToggle(models) {
  const box = $("mapModelToggle");
  if (!box) return;
  box.innerHTML = models.map(m =>
    `<button type="button" class="map-toggle-btn${m.name === currentMapModel ? " active" : ""}" data-model="${m.name}">${m.name}</button>`
  ).join("");
  box.querySelectorAll(".map-toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentMapModel = btn.getAttribute("data-model");
      box.querySelectorAll(".map-toggle-btn").forEach(b => b.classList.toggle("active", b === btn));
      $("mapModelLabel").textContent = currentMapModel;
      paintMap(countrySelect.value);
    });
  });
}
async function loadRiskMap(selectedCode) {
  const svg = $("europeMap");
  if (!svg) return;
  const codes = Object.keys(countryCoords);
  const settled = await Promise.allSettled(codes.map(code => getJson(`/api/risk/${code}`)));

  riskCache = codes.map((code, i) => {
    const result = settled[i];
    const probsByModel = {};
    if (result.status === "fulfilled") {
      (result.value.estimatedProbabilities || []).forEach(p => {
        if (p.probability !== null && p.probability !== undefined) probsByModel[p.model] = Number(p.probability);
      });
    }
    return { code, probsByModel };
  });

  paintMap(selectedCode);
}

function paintMap(selectedCode) {
  const svg = $("europeMap");
  if (!svg) return;
  let markup = "";
  riskCache.forEach((entry, i) => {
    const coord = countryCoords[entry.code];
    if (!coord) return;
    const [x, y] = project(coord);
    const prob = entry.probsByModel[currentMapModel] ?? null;
    const color = riskColor(prob);
    const label = prob === null ? "no estimate" : `${(prob*100).toFixed(0)}% estimated probability (${currentMapModel})`;
    const selected = entry.code === selectedCode ? " selected" : "";
    markup += `<circle class="risk-dot risk-dot-anim${selected}" data-code="${entry.code}"
        cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="10" fill="${color}"
        style="animation-delay:${(i*15)}ms">
        <title>${countryNames[entry.code] ?? entry.code}: ${label}</title>
      </circle>`;
    markup += `<text x="${x.toFixed(1)}" y="${(y-14).toFixed(1)}" class="chart-axis" text-anchor="middle" pointer-events="none">${entry.code}</text>`;
  });
  svg.innerHTML = markup;

  svg.querySelectorAll(".risk-dot").forEach(dot => {
    dot.addEventListener("click", () => {
      const code = dot.getAttribute("data-code");
      countrySelect.value = code;
      loadCountry(code);
      svg.querySelectorAll(".risk-dot").forEach(d => d.classList.remove("selected"));
      dot.classList.add("selected");
    });
  });
}

// ---------------------------------------------------------------------------
// Model coefficient chart
// ---------------------------------------------------------------------------
function drawCoefficients(models) {
  const box = $("coefficients");
  if (!box) return; // section not present in index.html yet

  const order = Object.keys(FEATURE_LABELS);
  const variables = [...new Set(models.flatMap(m => Object.keys(m.coefficients || {})))]
    .sort((a, b) => (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) - (order.indexOf(b) === -1 ? 99 : order.indexOf(b)));

  const maxAbs = Math.max(0.01, ...models.flatMap(m => Object.values(m.coefficients || {}).map(v => Math.abs(v))));

  let rows = "";
  variables.forEach(v => {
    let bars = `<div class="zero" style="left:50%"></div>`;
    models.forEach((m, mi) => {
      const val = m.coefficients?.[v];
      if (val === undefined) return;
      const pct = (Math.abs(val) / maxAbs) * 48; // percent of half-width
      const left = val >= 0 ? 50 : 50 - pct;
      const top = 3 + mi * 5;
      bars += `<div class="coef-bar" title="${m.name}: ${val.toFixed(4)}"
        style="left:${left}%; width:${pct}%; top:${top}px; background:${MODEL_COLORS[m.name] ?? '#94a3b8'};
        animation-delay:${mi*80}ms"></div>`;
    });
    rows += `<div class="coef-row"><div class="label">${fmtFeature(v)}</div>
      <div class="coef-bars" style="height:${8 + models.length*5}px">${bars}</div></div>`;
  });

  const legend = models.map(m =>
    `<span><i style="background:${MODEL_COLORS[m.name] ?? '#94a3b8'}"></i>${m.name}</span>`).join("");

  box.innerHTML = `<p class="muted">Logistic-regression coefficients (log-odds per +1 unit). Bars extend right for a positive association, left for negative.</p>
    ${rows}<div class="coef-legend">${legend}</div>`;
}

async function loadCountry(code) {
  try {
    const [series, risk] = await Promise.all([
      getJson(`/api/inflation/${code}`),
      getJson(`/api/risk/${code}`)
    ]);
    drawChart(series);
    const latestElection = latestElectionInAnalysisWindow[code] ?? risk.election;
    const modelObservation = risk.election;
    $("countryMeta").textContent = `Latest election in analysis window: ${latestElection} · Model observation: ${modelObservation} · Latest inflation data: ${series.at(-1)?.month ?? "—"} (${series.at(-1)?.inflationYoy?.toFixed(2) ?? "—"}%)`;

    $("probabilities").innerHTML = risk.estimatedProbabilities.map(p => {
      const pct = Math.max(0, Math.min(100, Number(p.probability) * 100));
      return `<div class="prob-row">
        <div class="prob-top"><strong>${p.model}</strong><span>${pct.toFixed(1)}%</span></div>
        <div class="bar"><span style="width:0%" data-target="${pct}"></span></div>
      </div>`;
    }).join("");
    // animate bars in after paint
    requestAnimationFrame(() => {
      $("probabilities").querySelectorAll(".bar span").forEach(el => {
        el.style.width = el.getAttribute("data-target") + "%";
      });
    });

    const entries = Object.entries(risk.features).sort((a,b) => a[0].localeCompare(b[0]));
    $("features").innerHTML = entries.map(([name,value]) =>
      `<div class="feature"><small>${fmtFeature(name)}</small><strong>${fmtNumber(value)}</strong></div>`
    ).join("");

    document.querySelectorAll("#europeMap .risk-dot").forEach(d =>
      d.classList.toggle("selected", d.getAttribute("data-code") === code));
  } catch (error) {
    $("countryMeta").innerHTML = `<span class="error">${error.message}</span>`;
  }
}

async function init() {
  try {
    const [health, models, countries] = await Promise.all([
      getJson("/api/health"),
      getJson("/api/models"),
      getJson("/api/countries")
    ]);
    if (health.placeholderWarning) console.warn("Model placeholder warning reported by API.");

    countrySelect.innerHTML = countries.map(c => `<option value="${c.code}">${countryNames[c.code] ?? c.name} (${c.code})</option>`).join("");
    countrySelect.addEventListener("change", () => loadCountry(countrySelect.value));

    $("models").innerHTML = models.map(m => {
      const description = modelDescriptions[m.name] ?? "Logistic-regression specification";
      return `<article class="model"><strong>${m.name}</strong><p>${description}</p><p class="aic">AIC ${Number(m.aic).toFixed(2)}</p></article>`;
    }).join("");

    drawCoefficients(models);
    renderMapToggle(models);
    await loadCountry(countrySelect.value);
    loadRiskMap(countrySelect.value); // fires ~28 requests; runs after first paint, not awaited
  } catch (error) {
    document.body.innerHTML += `<div class="shell"><p class="error">Dashboard initialization failed: ${error.message}</p></div>`;
  }
}
init();
