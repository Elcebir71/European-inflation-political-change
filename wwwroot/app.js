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

const modelDescriptions = {
  V1: "Inflation only",
  V2: "Inflation + unemployment + GDP growth",
  V3: "V2 + asylum + Ukraine temporary protection",
  V4: "Inflation + migration-pressure index + controls"
};

function fmtFeature(name) {
  return name.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}
function fmtNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

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

async function loadCountry(code) {
  try {
    const [series, risk] = await Promise.all([
      getJson(`/api/inflation/${code}`),
      getJson(`/api/risk/${code}`)
    ]);
    drawChart(series);
    $("countryMeta").textContent = `Latest election observation: ${risk.election} · Latest inflation data: ${series.at(-1)?.month ?? "—"} (${series.at(-1)?.inflationYoy?.toFixed(2) ?? "—"}%)`;

    $("probabilities").innerHTML = risk.estimatedProbabilities.map(p => {
      const pct = Math.max(0, Math.min(100, Number(p.probability) * 100));
      return `<div class="prob-row">
        <div class="prob-top"><strong>${p.model}</strong><span>${pct.toFixed(1)}%</span></div>
        <div class="bar"><span style="width:${pct}%"></span></div>
      </div>`;
    }).join("");

    const entries = Object.entries(risk.features).sort((a,b) => a[0].localeCompare(b[0]));
    $("features").innerHTML = entries.map(([name,value]) =>
      `<div class="feature"><small>${fmtFeature(name)}</small><strong>${fmtNumber(value)}</strong></div>`
    ).join("");
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

    await loadCountry(countrySelect.value);
  } catch (error) {
    document.body.innerHTML += `<div class="shell"><p class="error">Dashboard initialization failed: ${error.message}</p></div>`;
  }
}
init();
