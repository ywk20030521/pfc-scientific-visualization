(function () {
  "use strict";

  const DATA = window.PFC_VIEWER_DATA = window.PFC_VIEWER_DATA || {
    catalog: null,
    static: null,
    caseMeta: Object.create(null),
    caseCharts: Object.create(null),
    globalCharts: null,
    pendingChunks: Object.create(null),
    pendingHistories: Object.create(null),
    registerCatalog(value) { this.catalog = value; },
    registerStatic(value) { this.static = value; },
    registerCaseMeta(caseId, value) { this.caseMeta[caseId] = value; },
    registerCharts(caseId, value) { this.caseCharts[caseId] = value; },
    registerGlobalCharts(value) { this.globalCharts = value; },
    registerChunk(caseId, chunkIndex, value) {
      const byCase = this.pendingChunks[caseId] || (this.pendingChunks[caseId] = Object.create(null));
      byCase[chunkIndex] = value;
    },
    registerHistory(caseId, bucket, value) {
      const byCase = this.pendingHistories[caseId] || (this.pendingHistories[caseId] = Object.create(null));
      byCase[bucket] = value;
    }
  };

  const byId = (id) => document.getElementById(id);
  const body = document.body;

  document.documentElement.setAttribute("data-theme", "light");
  document.body.setAttribute("data-theme", "light");

  const errorBox = byId("errorBox");
  const loading = byId("loading");
  const visualSemantics = window.PFC_VISUAL_SEMANTICS || {};
  const documentTheme = "light";
  const themes = visualSemantics.themes || {};
  const theme = themes[documentTheme] || {};
  const legacyColors = visualSemantics.colors || {};
  const themeColor = (key, fallback) => theme[key] || legacyColors[key] || fallback;
  const COLORS = Object.freeze({
    theme: documentTheme,
    primary: themeColor("primary", "#3C5488"),
    wallSurface: themeColor("wall_surface", "#2F6FD0"),
    wallEdge: themeColor("wall_edge", "#2F6FD0"),
    fracture: themeColor("fracture", "#E64B35"),
    slate: themeColor("slate", "#8491B4"),
    tan: themeColor("tan", "#B09C85"),
    accent: themeColor("accent", "#F39B7F"),
    low: themeColor("particle_low", "#B8CCE4"),
    high: themeColor("particle_high", "#3C5488"),
    ramp: theme.particle_ramp || legacyColors.particle_ramp || null,
    missing: themeColor("missing", "#A8ADB7"),
    ink: themeColor("ink", "#171717"),
    muted: themeColor("muted", "#6F7074"),
    grid: themeColor("grid", "#E6E7E4"),
    axis: themeColor("axis", "#3d3d3d"),
    axisTick: themeColor("axis_tick", "#8a8a86"),
    heatmapLow: themeColor("heatmap_low", "#eef1f5"),
    heatmapMid: themeColor("heatmap_mid", "#aab6ca"),
    sceneBackground: themeColor("scene_background", "#f7f9fb"),
    chartBackground: themeColor("chart_background", "#ffffff"),
    tooltipBackground: themeColor("tooltip_background", "rgba(255,255,255,0.96)"),
    tooltipBorder: themeColor("tooltip_border", "#d9d9d5"),
    exportBackground: themeColor("export_background", "#ffffff")
  });

  function showError(code, error) {
    const details = error && error.stack ? error.stack : String(error);
    body.dataset.error = "1";
    body.dataset.errorCode = code;
    window.__PFC_VIEWER_ERROR__ = { code, message: details };
    errorBox.hidden = false;
    errorBox.textContent = code + "\n\n" + details;
    loading.hidden = true;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[ch]));
  }

  function finiteNumber(value) {
    if (value == null || value === "") return null;
    if (typeof value !== "number" && typeof value !== "string") return null;
    if (typeof value === "string" && value.trim() === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function formatNumber(value, digits = 3) {
    const number = finiteNumber(value);
    if (number === null) return "—";
    const abs = Math.abs(number);
    if (abs !== 0 && (abs < 1e-3 || abs >= 1e5)) {
      const rendered = number.toExponential(Math.max(1, Math.min(8, digits)));
      const parts = rendered.split("e");
      const superscript = String(Number(parts[1])).replace(/-/g, "⁻").replace(/[0-9]/g, (digit) => (
        "⁰¹²³⁴⁵⁶⁷⁸⁹"[Number(digit)]
      ));
      return parts[0].replace(/\.?0+$/, "") + " × 10" + superscript;
    }
    return number.toLocaleString("en-US", {
      maximumFractionDigits: digits,
      minimumFractionDigits: 0
    });
  }

  function formatMetric(value, unit, digits = 4) {
    return finiteNumber(value) === null
      ? "未采集"
      : formatNumber(value, digits) + (unit ? " " + unit : "");
  }

  function formatAxisValue(value, formatting) {
    const settings = formatting || {};
    const number = finiteNumber(value);
    if (number === null) return "—";
    if (
      settings.axis_notation === "SCIENTIFIC_SHARED_EXPONENT" &&
      finiteNumber(settings.axis_scale) !== null
    ) {
      const scaled = number / Number(settings.axis_scale);
      const digits = Number(
        settings.decimals != null
          ? settings.decimals
          : Math.max(1, Number(settings.significant_digits || 4) - 1)
      );
      return scaled.toLocaleString("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: 0
      });
    }
    const digits = settings.scientific
      ? Math.max(1, Number(settings.significant_digits || 4) - 1)
      : Number(settings.decimals != null ? settings.decimals : settings.significant_digits || 4);
    return formatNumber(number, digits);
  }

  function formatTooltipValue(value, formatting) {
    const settings = formatting || {};
    return formatNumber(value, Number(settings.tooltip_digits || 8));
  }

  function axisUnit(unit) {
    if (!unit || unit === "1") return "";
    return " (" + unit + ")";
  }

  function axisDisplayName(name, unit, formatting) {
    const settings = formatting || {};
    return name + axisUnit(unit) +
      (settings.axis_scale_label ? " [" + settings.axis_scale_label + "]" : "");
  }

  function decodeU32(base64) {
    if (!base64) return new Uint32Array(0);
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const view = new DataView(bytes.buffer);
    const out = new Uint32Array(bytes.length / 4);
    for (let index = 0; index < out.length; index += 1) out[index] = view.getUint32(index * 4, true);
    return out;
  }

  function decodeF32(base64) {
    if (!base64) return new Float32Array(0);
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const view = new DataView(bytes.buffer);
    const out = new Float32Array(bytes.length / 4);
    for (let index = 0; index < out.length; index += 1) out[index] = view.getFloat32(index * 4, true);
    return out;
  }

  function decodeHistoryRows(base64) {
    const flat = decodeF32(base64);
    const stride = 8;
    const rows = [];
    for (let offset = 0; offset + stride <= flat.length; offset += stride) {
      rows.push({
        sourceFrameIndex: flat[offset],
        viewerFrameIndex: flat[offset + 1],
        x: flat[offset + 2],
        y: flat[offset + 3],
        z: flat[offset + 4],
        displacement: flat[offset + 5],
        speed: flat[offset + 6],
        acceleration: flat[offset + 7]
      });
    }
    return rows;
  }

  function nearestIndex(values, target) {
    if (!Array.isArray(values) || values.length === 0) return -1;
    const numberTarget = finiteNumber(target);
    if (numberTarget === null) return -1;
    let bestIndex = -1;
    let bestDistance = Infinity;
    for (let index = 0; index < values.length; index += 1) {
      const number = finiteNumber(values[index]);
      if (number === null) continue;
      const distance = Math.abs(number - numberTarget);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    }
    return bestIndex;
  }

  function createStore(initial) {
    let state = Object.freeze({ ...initial });
    const listeners = new Set();
    return {
      get() { return state; },
      subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      set(patch, reason) {
        const next = Object.freeze({ ...state, ...patch });
        const previous = state;
        state = next;
        listeners.forEach((listener) => listener(next, previous, reason || "update"));
        return next;
      }
    };
  }

  const store = createStore({
    currentCase: null,
    currentFrame: 0,
    currentCycle: null,
    currentTime: null,
    selectedBallIds: [],
    selectedMetric: "displacement",
    selectedRange: null,
    colorMetric: "displacement"
  });
  let metricUserSet = false;
  try {
    const requestedMetric = new URLSearchParams(window.location.search).get("metric");
    if (["displacement", "speed", "acceleration", "contactForce"].includes(requestedMetric)) {
      store.set({ colorMetric: requestedMetric, selectedMetric: requestedMetric });
      metricUserSet = true;
    }
  } catch (ignored) {}

  const runtime = {
    caseToken: 0,
    frameToken: 0,
    current: null,
    caseRuntimes: new Map(),
    globalChartsLoaded: false,
    charts: [],
    currentCharts: Object.create(null),
    historyChart: null,
    currentHistories: Object.create(null),
    selectedHistories: new Map(),
    loadedScripts: new Set(),
    trajectories: [],
    playing: false,
    playAccumulator: 0,
    ready: false
  };
  runtime.lastHistogramUpdate = 0;

  let activePalette = "nature";
  const CONTRAST_RAMP = [
    { at: 0, color: "#27356b" },
    { at: 0.2, color: "#3b82b8" },
    { at: 0.45, color: "#4bb3a6" },
    { at: 0.7, color: "#d8c85a" },
    { at: 1, color: "#d96a3a" }
  ];
  const CONTRAST_CSS = "linear-gradient(90deg, #27356b, #3b82b8, #4bb3a6, #d8c85a, #d96a3a)";

  function buildColorRamp() {
    const sourceRamp = activePalette === "contrast" ? CONTRAST_RAMP : COLORS.ramp;
    const stops = Array.isArray(sourceRamp) && sourceRamp.length >= 2
      ? sourceRamp.map((item) => ({
          at: Math.max(0, Math.min(1, Number(item.at) || 0)),
          color: new THREE.Color(item.color)
        })).sort((a, b) => a.at - b.at)
      : [
          { at: 0, color: new THREE.Color(COLORS.low) },
          { at: 1, color: new THREE.Color(COLORS.high) }
        ];
    return Array.from({ length: 256 }, (_, index) => {
      const t = index / 255;
      let left = stops[0];
      let right = stops[stops.length - 1];
      for (let i = 0; i < stops.length - 1; i += 1) {
        if (t >= stops[i].at && t <= stops[i + 1].at) {
          left = stops[i]; right = stops[i + 1]; break;
        }
      }
      const span = right.at - left.at;
      const f = span > 0 ? (t - left.at) / span : 0;
      return [
        left.color.r + (right.color.r - left.color.r) * f,
        left.color.g + (right.color.g - left.color.g) * f,
        left.color.b + (right.color.b - left.color.b) * f
      ];
    });
  }
  let colorRamp = buildColorRamp();
  function setPalette(name) {
    activePalette = name === "contrast" ? "contrast" : "nature";
    colorRamp = buildColorRamp();
    const root = document.documentElement;
    if (activePalette === "contrast") root.style.setProperty("--particle-ramp", CONTRAST_CSS);
    else root.style.removeProperty("--particle-ramp");
  }
  const missingColor = new THREE.Color(COLORS.missing);
  runtime.colorRange = null;

  function loadScriptOnce(key, path) {
    if (runtime.loadedScripts.has(key)) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = path;
      script.async = true;
      script.onload = () => {
        runtime.loadedScripts.add(key);
        script.remove();
        resolve();
      };
      script.onerror = () => {
        script.remove();
        reject(new Error("无法加载本地数据脚本: " + path));
      };
      document.head.appendChild(script);
    });
  }

  async function loadCaseMeta(caseId) {
    if (DATA.caseMeta[caseId]) return DATA.caseMeta[caseId];
    const summary = DATA.catalog.cases.find((item) => item.id === caseId);
    if (!summary) throw new Error("Case 不存在: " + caseId);
    await loadScriptOnce("meta:" + caseId, summary.metaPath);
    if (!DATA.caseMeta[caseId]) throw new Error("Case 元数据未注册: " + caseId);
    return DATA.caseMeta[caseId];
  }

  async function loadCaseCharts(caseId) {
    if (!DATA.caseCharts[caseId]) {
      const summary = DATA.catalog.cases.find((item) => item.id === caseId);
      await loadScriptOnce("charts:" + caseId, summary.chartsPath);
    }
    if (!runtime.globalChartsLoaded && DATA.catalog.meta.globalChartsPath) {
      await loadScriptOnce("charts:global", DATA.catalog.meta.globalChartsPath);
      runtime.globalChartsLoaded = true;
    }
    return (DATA.caseCharts[caseId] || []).concat(DATA.globalCharts || []);
  }

  function syncCaseVisualCapabilities(meta) {
    const metricStatus = meta.metricStatus || {};
    const metricLabels = {
      displacement: "累计位移", speed: "速度", acceleration: "加速度", contactForce: "接触力"
    };
    const supportedMetrics = ["displacement", "speed", "acceleration", "contactForce"].filter(
      (metric) => metricStatus[metric] === "SUPPORTED"
    );
    const preferred = !metricUserSet && supportedMetrics.includes("contactForce")
      ? "contactForce" : store.get().colorMetric;
    const chosenMetric = supportedMetrics.includes(preferred)
      ? preferred
      : (supportedMetrics[0] || "displacement");
    Array.from(byId("colorMetric").options).forEach((option) => {
      const supported = metricStatus[option.value] === "SUPPORTED";
      option.disabled = !supported;
      option.textContent = supported
        ? metricLabels[option.value]
        : (metricLabels[option.value] + "（未采集）");
    });
    byId("colorMetric").disabled = supportedMetrics.length === 0;
    byId("colorMetric").value = chosenMetric;
    store.set(
      { colorMetric: chosenMetric, selectedMetric: chosenMetric },
      "case-capabilities"
    );
    const entityStatus = meta.entityStatus || {};
    const contact = byId("contactLayerControl");
    contact.hidden = entityStatus.contact !== "SUPPORTED";
    byId("showContacts").disabled = entityStatus.contact !== "SUPPORTED";
    contact.title = entityStatus.contact === "SUPPORTED"
      ? "按当前真实帧显示带端点 ID 的接触网络；线色表示接触力大小。"
      : "当前实验未采集接触端点与接触力。";
    const bond = byId("bondLayerControl");
    bond.hidden = entityStatus.bond !== "SUPPORTED";
    byId("showBonds").disabled = entityStatus.bond !== "SUPPORTED";
    bond.title = entityStatus.bond === "SUPPORTED"
      ? "按当前真实帧显示带端点 ID 的 Bond 网络；线色表示 Bond 力大小。"
      : "当前实验未采集 Bond 端点与 Bond 力。";
    body.dataset.particleMetricCapabilities = JSON.stringify(metricStatus);
    body.dataset.entityCapabilities = JSON.stringify(entityStatus);
  }

  function caseRuntime(caseId) {
    let item = runtime.caseRuntimes.get(caseId);
    if (!item) {
      item = {
        caseId,
        chunkCache: new Map(),
        chunkPromises: new Map(),
        historyCache: new Map(),
        historyPromises: new Map()
      };
      runtime.caseRuntimes.set(caseId, item);
    }
    return item;
  }

  async function ensureChunk(caseId, chunkIndex) {
    const item = caseRuntime(caseId);
    if (item.chunkCache.has(chunkIndex)) {
      const value = item.chunkCache.get(chunkIndex);
      item.chunkCache.delete(chunkIndex);
      item.chunkCache.set(chunkIndex, value);
      return value;
    }
    if (item.chunkPromises.has(chunkIndex)) return item.chunkPromises.get(chunkIndex);
    const summary = DATA.catalog.cases.find((entry) => entry.id === caseId);
    const path = summary.chunkPattern.replace("{chunk:03d}", String(chunkIndex).padStart(3, "0"));
    const key = "chunk:" + caseId + ":" + chunkIndex;
    const promise = loadScriptOnce(key, path).then(() => {
      const registered = DATA.pendingChunks[caseId] && DATA.pendingChunks[caseId][chunkIndex];
      if (!registered) throw new Error("帧块未注册: Case " + caseId + " / " + chunkIndex);
      delete DATA.pendingChunks[caseId][chunkIndex];
      item.chunkCache.set(chunkIndex, registered);
      while (item.chunkCache.size > 5) {
        const oldest = item.chunkCache.keys().next().value;
        item.chunkCache.delete(oldest);
        runtime.loadedScripts.delete("chunk:" + caseId + ":" + oldest);
      }
      return registered;
    }).finally(() => item.chunkPromises.delete(chunkIndex));
    item.chunkPromises.set(chunkIndex, promise);
    return promise;
  }

  async function ensureHistoryBucket(caseId, ballId) {
    const item = caseRuntime(caseId);
    const bucketCount = DATA.caseMeta[caseId].historyBucketCount;
    const bucket = ballId % bucketCount;
    if (item.historyCache.has(bucket)) return item.historyCache.get(bucket);
    if (item.historyPromises.has(bucket)) return item.historyPromises.get(bucket);
    const summary = DATA.catalog.cases.find((entry) => entry.id === caseId);
    const path = summary.historyPattern.replace("{bucket:03d}", String(bucket).padStart(3, "0"));
    const key = "history:" + caseId + ":" + bucket;
    const promise = loadScriptOnce(key, path).then(() => {
      const registered = DATA.pendingHistories[caseId] && DATA.pendingHistories[caseId][bucket];
      if (!registered) throw new Error("颗粒历史桶未注册: Case " + caseId + " / " + bucket);
      delete DATA.pendingHistories[caseId][bucket];
      item.historyCache.set(bucket, registered);
      while (item.historyCache.size > 6) {
        const oldest = item.historyCache.keys().next().value;
        item.historyCache.delete(oldest);
        runtime.loadedScripts.delete("history:" + caseId + ":" + oldest);
      }
      return registered;
    }).finally(() => item.historyPromises.delete(bucket));
    item.historyPromises.set(bucket, promise);
    return promise;
  }

  const viewerStarted = performance.now();
  let renderer;
  let scene;
  let camera;
  let controls;
  let staticBalls;
  let staticCases;
  let staticById;
  let particles;
  let particleMaterial;
  let particleDummy;
  let highlightMesh;
  let highlightGeometry;
  let colorBuffer;
  let visibleIds = [];
  let currentFrameData = null;
  let crackTension;
  let crackShear;
  let wallLines;
  let wallPoints;
  let wallSolids;
  let wallSolidDummy;
  let wallFaces;
  let wallEdgeLines;
  let contactLines;
  let bondLines;
  let highlightGroup;
  let axesHelper;
  let domainBox;
  let grid;
  let clippingPlane;
  let dmin;
  let dmax;
  let center;
  let span;
  let focusCenter;
  let focusSpan;
  let keyLight;
  let currentViewPreset = "fit";
  let is2D;
  let perspectiveCamera;
  let orthographicCamera;
  let orthoExtent;
  let pointerDown = null;
  let stateRenderQueued = false;
  let pendingState = null;
  let pendingReason = "update";
  let lastRenderedState = null;

  function ballFocusBounds(balls) {
    const lo = new THREE.Vector3(Infinity, Infinity, Infinity);
    const hi = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
    (balls || []).forEach((ball) => {
      const radius = Math.max(0, Number(ball[4]) || 0);
      lo.min(new THREE.Vector3(ball[1] - radius, ball[2] - radius, ball[3] - radius));
      hi.max(new THREE.Vector3(ball[1] + radius, ball[2] + radius, ball[3] + radius));
    });
    if (!Number.isFinite(lo.x) || !Number.isFinite(hi.x)) {
      return { center: new THREE.Vector3(), span: 1 };
    }
    return {
      center: lo.clone().add(hi).multiplyScalar(0.5),
      span: Math.max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z, 1.0e-6)
    };
  }

  function webglProbe() {
    const canvas = document.createElement("canvas");
    for (const name of ["webgl2", "webgl", "experimental-webgl"]) {
      try {
        const context = canvas.getContext(name);
        if (context) return { available: true, context: name };
      } catch (ignored) {}
    }
    return { available: false, context: null };
  }

  function createScene() {
    staticCases = DATA.static.cases || {};
    const defaultCase = DATA.catalog.meta.defaultCase;
    if (!Object.keys(staticCases).length) {
      staticCases[String(defaultCase)] = DATA.static;
    }
    staticBalls = (staticCases[String(defaultCase)] || DATA.static).balls;
    staticById = new Map();
    const radii = new Float32Array(staticBalls.length);
    const initialXYZ = new Float32Array(staticBalls.length * 3);
    staticBalls.forEach((ball, index) => {
      staticById.set(ball[0], { index, radius: ball[4] });
      radii[index] = ball[4];
      initialXYZ[index * 3] = ball[1];
      initialXYZ[index * 3 + 1] = ball[2];
      initialXYZ[index * 3 + 2] = ball[3];
    });

    const domain = DATA.catalog.meta.domain;
    dmin = new THREE.Vector3().fromArray(domain.min);
    dmax = new THREE.Vector3().fromArray(domain.max);
    center = dmin.clone().add(dmax).multiplyScalar(0.5);
    span = Math.max(dmax.x - dmin.x, dmax.y - dmin.y, dmax.z - dmin.z, 1e-6);
    const focus = ballFocusBounds(staticBalls);
    focusCenter = focus.center;
    focusSpan = focus.span;
    is2D = Number(DATA.catalog.meta.dimension) === 2;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(COLORS.sceneBackground);
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
      preserveDrawingBuffer: false
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    if ("outputColorSpace" in renderer && THREE.SRGBColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace;
    else if (THREE.sRGBEncoding != null) renderer.outputEncoding = THREE.sRGBEncoding;
    const legacyToneMapping = THREE.NoToneMapping; // retained baseline constant for contract checks
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.06;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.localClippingEnabled = true;
    byId("scene").appendChild(renderer.domElement);

    renderer.domElement.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      body.dataset.webglStatus = "context_lost";
      showError(
        "WEBGL_CONTEXT_LOST",
        new Error(
          "WebGL 上下文已丢失，渲染暂停。数据未改变；请刷新页面重新初始化，或在上下文自动恢复后继续。"
        )
      );
    }, false);
    renderer.domElement.addEventListener("webglcontextrestored", () => {
      body.dataset.webglStatus = "restored";
      body.dataset.error = "0";
      delete body.dataset.errorCode;
      errorBox.hidden = true;
      if (renderer && scene && camera) {
        try {
          renderer.render(scene, camera);
        } catch (ignored) {}
      }
    }, false);

    perspectiveCamera = new THREE.PerspectiveCamera(40, 1, span * 0.001, span * 100);
    perspectiveCamera.position.copy(center).add(new THREE.Vector3(span * 1.18, -span * 1.48, span * 0.72));
    orthoExtent = span * 0.72;
    orthographicCamera = new THREE.OrthographicCamera(
      -orthoExtent, orthoExtent, orthoExtent, -orthoExtent, span * 0.001, span * 100
    );
    orthographicCamera.position.copy(center).add(new THREE.Vector3(0, 0, span * 2.2));
    camera = is2D ? orthographicCamera : perspectiveCamera;
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.copy(center);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    const hemisphere = new THREE.HemisphereLight(0xffffff, 0xdce6f2, 1.0);
    scene.add(hemisphere);
    keyLight = new THREE.DirectionalLight(0xffffff, 1.45);
    keyLight.position.copy(focusCenter).add(new THREE.Vector3(focusSpan, -focusSpan * 0.75, focusSpan * 1.4));
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.camera.near = focusSpan * 0.001;
    keyLight.shadow.camera.far = focusSpan * 6;
    keyLight.shadow.camera.left = -focusSpan;
    keyLight.shadow.camera.right = focusSpan;
    keyLight.shadow.camera.top = focusSpan;
    keyLight.shadow.camera.bottom = -focusSpan;
    keyLight.shadow.bias = -0.00015;
    keyLight.shadow.normalBias = focusSpan * 0.002;
    keyLight.shadow.camera.updateProjectionMatrix();
    keyLight.target.position.copy(focusCenter);
    scene.add(keyLight, keyLight.target);
    const fill = new THREE.DirectionalLight(0xffffff, 0.45);
    fill.position.copy(center).add(new THREE.Vector3(-span, span * 0.35, span * 0.4));
    scene.add(fill);
    const rimLight = new THREE.DirectionalLight(0xbcd4f2, 0.6);
    rimLight.position.copy(focusCenter).add(new THREE.Vector3(-focusSpan, focusSpan * 0.5, -focusSpan));
    scene.add(rimLight);
    const envCanvas = document.createElement("canvas");
    envCanvas.width = 32;
    envCanvas.height = 128;
    const envCtx = envCanvas.getContext("2d");
    const envGrad = envCtx.createLinearGradient(0, 0, 0, 128);
    envGrad.addColorStop(0, "#ffffff");
    envGrad.addColorStop(0.48, "#f2f6fb");
    envGrad.addColorStop(0.52, "#e3ebf4");
    envGrad.addColorStop(1, "#cfdae6");
    envCtx.fillStyle = envGrad;
    envCtx.fillRect(0, 0, 32, 128);
    const envTexture = new THREE.CanvasTexture(envCanvas);
    envTexture.mapping = THREE.EquirectangularReflectionMapping;
    scene.environment = envTexture;

    grid = new THREE.GridHelper(span * 1.6, 16, 0xd5d8de, 0xebeef0);
    if (is2D) {
      grid.rotation.x = Math.PI / 2;
      grid.position.set(center.x, center.y, dmin.z - span * 0.006);
    } else {
      grid.position.set(center.x, dmin.y - span * 0.006, center.z);
    }
    grid.material.transparent = true;
    grid.material.opacity = 0.65;
    grid.visible = is2D && byId("showAxes").checked;
    scene.add(grid);
    const axesPositions = [];
    const axesColors = [];
    const axisDefinitions = [
      { end: [span * 0.28, 0, 0], color: COLORS.primary },
      { end: [0, span * 0.28, 0], color: COLORS.slate },
    ];
    if (!is2D) {
      axisDefinitions.push({ end: [0, 0, span * 0.28], color: COLORS.tan });
    }
    axisDefinitions.forEach(({ end, color }) => {
      const parsed = new THREE.Color(color);
      axesPositions.push(0, 0, 0, end[0], end[1], end[2]);
      axesColors.push(parsed.r, parsed.g, parsed.b, parsed.r, parsed.g, parsed.b);
    });
    const axesGeometry = new THREE.BufferGeometry();
    axesGeometry.setAttribute("position", new THREE.Float32BufferAttribute(axesPositions, 3));
    axesGeometry.setAttribute("color", new THREE.Float32BufferAttribute(axesColors, 3));
    axesHelper = new THREE.LineSegments(
      axesGeometry,
      new THREE.LineBasicMaterial({ vertexColors: true })
    );
    axesHelper.position.copy(dmin);
    scene.add(axesHelper);
    domainBox = new THREE.Box3Helper(new THREE.Box3(dmin.clone(), dmax.clone()), 0xb4bac6);
    domainBox.material.transparent = true;
    domainBox.material.opacity = 0.3;
    domainBox.visible = byId("showBounds").checked;
    scene.add(domainBox);
    clippingPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), dmax.z);

    particleMaterial = new THREE.MeshPhysicalMaterial({
      roughness: is2D ? 0.74 : 0.3,
      metalness: 0.0,
      clearcoat: is2D ? 0 : 0.34,
      clearcoatRoughness: 0.2,
      envMapIntensity: 1.4,
      side: is2D ? THREE.DoubleSide : THREE.FrontSide,
      toneMapped: false,
      clippingPlanes: []
    });
    const maxStaticBalls = Math.max(
      1,
      ...Object.values(staticCases).map((item) => item.balls.length),
      staticBalls.length
    );
    const sphereSegments = maxStaticBalls > 8000 ? [10, 7]
      : (maxStaticBalls > 1500 ? [12, 8] : [18, 12]);
    const sphereGeometry = sphereSegments[0] === 18 && sphereSegments[1] === 12
      ? new THREE.SphereGeometry(1, 18, 12)
      : new THREE.SphereGeometry(1, sphereSegments[0], sphereSegments[1]);
    particles = new THREE.InstancedMesh(
      is2D ? new THREE.CircleGeometry(1, 32) : sphereGeometry,
      particleMaterial,
      maxStaticBalls
    );
    particles.frustumCulled = false;
    particles.castShadow = !is2D;
    particles.receiveShadow = !is2D;
    particles.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    particles.instanceColor = new THREE.InstancedBufferAttribute(
      new Float32Array(maxStaticBalls * 3), 3
    );
    particles.instanceColor.setUsage(THREE.DynamicDrawUsage);
    particles.count = 0;
    scene.add(particles);
    particleDummy = new THREE.Object3D();
    colorBuffer = particles.instanceColor.array;

    highlightGroup = new THREE.Group();
    scene.add(highlightGroup);
    highlightGeometry = is2D
      ? new THREE.RingGeometry(0.92, 1.12, 40)
      : new THREE.SphereGeometry(1.04, 18, 12);
    highlightMesh = new THREE.InstancedMesh(
      highlightGeometry,
      new THREE.MeshBasicMaterial({
        color: COLORS.accent,
        wireframe: !is2D,
        transparent: true,
        opacity: is2D ? 0.95 : 0.8,
        depthTest: false,
        side: THREE.DoubleSide
      }),
      maxStaticBalls
    );
    highlightMesh.count = 0;
    highlightMesh.frustumCulled = false;
    highlightMesh.renderOrder = 30;
    highlightMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    highlightGroup.add(highlightMesh);
    wallLines = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: COLORS.primary, transparent: true, opacity: 0.95 })
    );
    wallLines.frustumCulled = false;
    wallLines.visible = false;
    scene.add(wallLines);
    wallPoints = new THREE.Points(
      new THREE.BufferGeometry(),
      new THREE.PointsMaterial({ color: COLORS.primary, size: Math.max(span * 0.012, 0.012), transparent: true, opacity: 0.9 })
    );
    wallPoints.frustumCulled = false;
    wallPoints.visible = false;
    scene.add(wallPoints);
    wallSolidDummy = new THREE.Object3D();
    wallSolids = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(1, 1, 1, 8, 1, false),
      new THREE.MeshPhysicalMaterial({
        color: COLORS.primary, roughness: 0.45, metalness: 0.05,
        transparent: true, opacity: 0.65, depthWrite: false
      }),
      512
    );
    wallSolids.count = 0;
    wallSolids.frustumCulled = false;
    wallSolids.visible = false;
    scene.add(wallSolids);
    // Real wall platen: a CLOSED thin slab rebuilt every frame from the PFC
    // wall vertex coordinates. Its thickness equals the existing wall-rod
    // diameter, so it reads as the same physical wall rather than an enormous
    // filled plane. Translucent blue with depthWrite off keeps every grain and
    // contact visible through it; no geometry is scaled or invented.
    wallFaces = new THREE.Mesh(
      new THREE.BufferGeometry(),
      new THREE.MeshPhysicalMaterial({
        color: COLORS.wallSurface, roughness: 0.36, metalness: 0.02,
        transparent: true, opacity: 0.12, side: THREE.DoubleSide,
        depthWrite: false
      })
    );
    wallFaces.frustumCulled = false;
    wallFaces.visible = false;
    scene.add(wallFaces);
    // A saturated edge outline makes the thin blue plate legible without
    // increasing the fill opacity. Its endpoints are the same real facet
    // boundary vertices used by the shell, rebuilt on every frame.
    wallEdgeLines = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({
        color: COLORS.wallEdge, transparent: true, opacity: 0.45,
        depthWrite: false
      })
    );
    wallEdgeLines.frustumCulled = false;
    wallEdgeLines.visible = false;
    scene.add(wallEdgeLines);
    const makeNetworkLayer = () => {
      const geometry = new THREE.BufferGeometry();
      const positions = new THREE.BufferAttribute(new Float32Array(0), 3);
      const colors = new THREE.BufferAttribute(new Float32Array(0), 3);
      positions.setUsage(THREE.DynamicDrawUsage);
      colors.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute("position", positions);
      geometry.setAttribute("color", colors);
      geometry.setDrawRange(0, 0);
      const layer = new THREE.LineSegments(
        geometry,
        new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: 0.9,
          clippingPlanes: []
        })
      );
      layer.frustumCulled = false;
      layer.visible = false;
      scene.add(layer);
      return layer;
    };
    contactLines = makeNetworkLayer();
    bondLines = makeNetworkLayer();
    buildCrackLayers([]);

    renderer.domElement.addEventListener("pointerdown", (event) => {
      pointerDown = { x: event.clientX, y: event.clientY };
    });
    renderer.domElement.addEventListener("pointerup", handleSceneClick);
    window.addEventListener("resize", resize);
  }

  function buildCrackLayers(records) {
    if (crackTension) {
      scene.remove(crackTension);
      crackTension.geometry.dispose();
      crackTension.material.dispose();
    }
    if (crackShear) {
      scene.remove(crackShear);
      crackShear.geometry.dispose();
      crackShear.material.dispose();
    }
    const make = (rows, color) => {
      // Keep the buffer a whole number of vec3 vertices.  A length of 2
      // (from max(2, 0)) is not divisible by 3 and makes THREE compute a
      // NaN bounding sphere for the empty crack layer.
      const positions = new Float32Array(Math.max(6, rows.length * 6));
      const geometry = new THREE.BufferGeometry();
      const attribute = new THREE.BufferAttribute(positions, 3);
      attribute.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute("position", attribute);
      geometry.setDrawRange(0, 0);
      const line = new THREE.LineSegments(
        geometry,
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.92, clippingPlanes: [] })
      );
      line.frustumCulled = false;
      line.userData.rows = rows;
      scene.add(line);
      return line;
    };
    crackTension = make(records.filter((row) => row[7] === 0), COLORS.primary);
    crackShear = make(records.filter((row) => row[7] === 1), COLORS.fracture);
    updateCracks(0);
  }

  function updateCracks(cycle) {
    if (!runtime.current) return;
    const rows = runtime.current.meta.cracks || [];
    const visible = rows.filter((row) => row[6] <= cycle);
    const tension = visible.filter((row) => row[7] === 0);
    const shear = visible.filter((row) => row[7] === 1);
    // Dynamic cracks: rows with two endpoint Ball IDs (row[9]/row[10]) are
    // re-anchored to the current frame's ball positions.  The break direction
    // and length are preserved; only the break midpoint follows the two balls,
    // so cracks translate/rotate with particle motion instead of staying fixed
    // at the capture-time coordinates.  Rows without IDs stay static (real
    // PFC captures that only store fracture_position).
    let positionById = null;
    if (currentFrameData && currentFrameData.ids && currentFrameData.xyz) {
      const ids = decodeU32(currentFrameData.ids);
      const xyz = decodeF32(currentFrameData.xyz);
      positionById = new Map();
      for (let index = 0; index < ids.length; index += 1) {
        positionById.set(ids[index], [xyz[index * 3], xyz[index * 3 + 1], xyz[index * 3 + 2]]);
      }
    }
    const write = (line, selected) => {
      const attribute = line.geometry.getAttribute("position");
      const array = attribute.array;
      array.fill(0);
      selected.forEach((row, index) => {
        let ax = row[0], ay = row[1], az = row[2];
        let bx = row[3], by = row[4], bz = row[5];
        const idA = row[9], idB = row[10];
        if (positionById && Number.isFinite(idA) && Number.isFinite(idB) && idA > 0 && idB > 0) {
          const pa = positionById.get(idA);
          const pb = positionById.get(idB);
          if (pa && pb) {
            const breakMid = [(ax + bx) / 2, (ay + by) / 2, (az + bz) / 2];
            const nowMid = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, (pa[2] + pb[2]) / 2];
            const dx = nowMid[0] - breakMid[0];
            const dy = nowMid[1] - breakMid[1];
            const dz = nowMid[2] - breakMid[2];
            ax += dx; ay += dy; az += dz;
            bx += dx; by += dy; bz += dz;
          }
        }
        const offset = index * 6;
        array[offset] = ax;
        array[offset + 1] = ay;
        array[offset + 2] = az;
        array[offset + 3] = bx;
        array[offset + 4] = by;
        array[offset + 5] = bz;
      });
      attribute.needsUpdate = true;
      line.geometry.setDrawRange(0, selected.length * 2);
    };
    write(crackTension, tension);
    write(crackShear, shear);
    const show = byId("showCracks").checked;
    crackTension.visible = show && tension.length > 0;
    crackShear.visible = show && shear.length > 0;
    body.dataset.cracksVisible = String(visible.length);
    body.dataset.tensionVisible = String(tension.length);
    body.dataset.shearVisible = String(shear.length);
  }


  function srgbByte(linear) {
    const v = Math.max(0, Math.min(1, linear));
    return Math.round(255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055));
  }

  function drawMiniView(canvas, ids, xyz, radii, values, low, high, axes, filter) {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.floor(rect.width || canvas.width));
    const h = Math.max(1, Math.floor(rect.height || canvas.height));
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = COLORS.chartBackground;
    ctx.fillRect(0, 0, w, h);
    const a0 = axes[0], a1 = axes[1];
    const min0 = dmin.getComponent(a0), max0 = dmax.getComponent(a0);
    const min1 = dmin.getComponent(a1), max1 = dmax.getComponent(a1);
    const pad = 5;
    const scale = Math.min((w - 2 * pad) / Math.max(max0 - min0, 1e-9),
      (h - 2 * pad) / Math.max(max1 - min1, 1e-9));
    const ox = pad + ((w - 2 * pad) - (max0 - min0) * scale) / 2;
    const oy = pad + ((h - 2 * pad) - (max1 - min1) * scale) / 2;
    for (let i = 0; i < ids.length; i += 1) {
      if (filter && !filter(i)) continue;
      const value = values[i];
      const t = Number.isFinite(value) && high > low
        ? Math.max(0, Math.min(255, Math.round(((value - low) / (high - low)) * 255)))
        : 0;
      const c = colorRamp[t];
      const px = ox + (xyz[i * 3 + a0] - min0) * scale;
      const py = h - (oy + (xyz[i * 3 + a1] - min1) * scale);
      const pr = Math.max(0.8, Number.isFinite(radii[i]) ? radii[i] * scale : 1.2);
      ctx.fillStyle = "rgb(" + srgbByte(c[0]) + "," + srgbByte(c[1]) + "," + srgbByte(c[2]) + ")";
      ctx.beginPath();
      ctx.arc(px, py, pr, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
  }

  function drawInsets(ids, xyz, radii, values, low, high) {
    const topFigure = byId("topInset");
    const sectionFigure = byId("sectionInset");
    if (!topFigure || !sectionFigure) return;
    const toggle = byId("showInsets");
    const dimension = Number(DATA.catalog.meta.dimension) === 2 ? 2 : 3;
    if (dimension === 2) {
      // Planar case: no section/top inset and no clipping controls.
      topFigure.hidden = true;
      sectionFigure.hidden = true;
      body.dataset.insets = "0";
      body.dataset.insetChoice = "none";
      return;
    }
    const enabled = !toggle || toggle.checked;
    const caseId = DATA.catalog.meta.defaultCase;
    const specs = DATA.caseCharts[caseId] || [];
    const hasSpatial = specs.some((spec) =>
      (spec.type === "scatter" || spec.type === "heatmap") &&
      /x|y|空间|分布/i.test((spec.title || "") + (spec.x && spec.x.name || ""))
    );
    const spans = [dmax.x - dmin.x, dmax.y - dmin.y, dmax.z - dmin.z];
    let viewAxis = 0;
    for (let i = 1; i < spans.length; i += 1) if (spans[i] < spans[viewAxis]) viewAxis = i;
    const topAxes = [0, 1, 2].filter((axis) => axis !== viewAxis).slice(0, 2);
    const sectionNormal = dimension === 3 ? (viewAxis === 2 ? 1 : 2) : viewAxis;
    const sectionAxes = [0, 1, 2].filter((axis) => axis !== sectionNormal).slice(0, 2);
    let choice = "top";
    if (dimension === 3 && window.innerHeight >= 700) choice = hasSpatial ? "section" : "both";
    body.dataset.insets = enabled ? "1" : "0";
    body.dataset.insetChoice = choice;
    topFigure.hidden = !enabled || choice === "section";
    sectionFigure.hidden = !enabled || choice === "top";
    if (!enabled) return;
    if (choice !== "section") {
      drawMiniView(byId("topInsetCanvas"), ids, xyz, radii, values, low, high, topAxes, null);
    }
    if (choice === "both" || choice === "section") {
      const cut = dmin.getComponent(sectionNormal) +
        (dmax.getComponent(sectionNormal) - dmin.getComponent(sectionNormal)) * 0.5;
      const thickness = Math.max(spans[sectionNormal] * 0.18, 1e-6);
      let sliceCount = 0;
      for (let i = 0; i < ids.length; i += 1) {
        if (Math.abs(xyz[i * 3 + sectionNormal] - cut) <= thickness) sliceCount += 1;
      }
      const names = ["X", "Y", "Z"];
      const caption = byId("sectionInsetCaption");
      if (sliceCount >= Math.max(6, ids.length * 0.02)) {
        drawMiniView(byId("sectionInsetCanvas"), ids, xyz, radii, values, low, high, sectionAxes,
          (i) => Math.abs(xyz[i * 3 + sectionNormal] - cut) <= thickness);
        if (caption) caption.textContent = "剖面 " + names[sectionAxes[0]] + "–" + names[sectionAxes[1]] + " · 当前帧";
      } else {
        drawMiniView(byId("sectionInsetCanvas"), ids, xyz, radii, values, low, high, sectionAxes, null);
        if (caption) caption.textContent = "投影 " + names[sectionAxes[0]] + "–" + names[sectionAxes[1]] + " · 当前帧";
      }
    }
  }

  function updateParticles(frame, highlightIds) {
    const ids = decodeU32(frame.ids);
    const xyz = decodeF32(frame.xyz);
    const displacement = decodeF32(frame.displacement);
    const speed = decodeF32(frame.speed);
    const acceleration = decodeF32(frame.acceleration);
    const contactForce = frame.contactForce ? decodeF32(frame.contactForce) : null;
    const radii = decodeF32(frame.radius);
    const colorMetric = store.get().colorMetric;
    const metricValues = colorMetric === "speed"
      ? speed
      : (colorMetric === "acceleration"
        ? acceleration
        : (colorMetric === "contactForce" && contactForce ? contactForce : displacement));
    const finiteValues = [];
    for (let index = 0; index < metricValues.length; index += 1) {
      if (Number.isFinite(metricValues[index])) finiteValues.push(metricValues[index]);
    }
    finiteValues.sort((left, right) => left - right);
    const fallbackMax = colorMetric === "speed"
      ? runtime.current.summary.maxSpeed
      : (colorMetric === "acceleration"
        ? runtime.current.summary.maxAcceleration
        : (colorMetric === "contactForce"
          ? runtime.current.summary.maxContactForce
          : runtime.current.summary.maxDisplacement));
    const low = finiteValues.length ? finiteValues[Math.floor((finiteValues.length - 1) * 0.05)] : 0;
    const high = finiteValues.length ? finiteValues[Math.floor((finiteValues.length - 1) * 0.95)] : fallbackMax;
    const colorLow = Number.isFinite(low) ? low : 0;
    const colorHigh = Number.isFinite(high) && high > colorLow ? high : Math.max(fallbackMax, colorLow, 1e-12);
    runtime.colorRange = { metric: colorMetric, low: colorLow, high: colorHigh, method: "P05_P95" };
    const selected = new Set(highlightIds);
    const staticIds = new Set(staticBalls.map((ball) => ball[0]));
    const currentIds = new Set(ids);
    let dynamicAddedCount = 0;
    for (const ballId of ids) {
      if (!staticIds.has(ballId)) dynamicAddedCount += 1;
    }
    let removedFromStaticCount = 0;
    for (const ballId of staticIds) {
      if (!currentIds.has(ballId)) removedFromStaticCount += 1;
    }
    visibleIds = Array.from(ids);
    particles.count = ids.length;
    let selectedInstanceCount = 0;
    for (let index = 0; index < ids.length; index += 1) {
      const ballId = ids[index];
      const staticBall = staticById.get(ballId);
      const fallbackRadius = staticBall ? staticBall.radius : 0;
      const radius = Number.isFinite(radii[index]) && radii[index] > 0 ? radii[index] : fallbackRadius;
      particleDummy.position.set(xyz[index * 3], xyz[index * 3 + 1], xyz[index * 3 + 2]);
      particleDummy.scale.setScalar(radius);
      particleDummy.updateMatrix();
      particles.setMatrixAt(index, particleDummy.matrix);
      const value = colorMetric === "speed"
        ? speed[index]
        : (colorMetric === "acceleration"
          ? acceleration[index]
          : (colorMetric === "contactForce" && contactForce ? contactForce[index] : displacement[index]));
      let color;
      if (!Number.isFinite(value)) color = missingColor;
      else color = colorRamp[Math.max(0, Math.min(255, Math.round(
        ((value - colorLow) / (colorHigh - colorLow)) * 255
      )))];
      const glint = 1.0 + ((index * 37) % 13) / 100;
      colorBuffer[index * 3] = (color.r != null ? color.r : color[0]) * glint;
      colorBuffer[index * 3 + 1] = (color.g != null ? color.g : color[1]) * glint;
      colorBuffer[index * 3 + 2] = (color.b != null ? color.b : color[2]) * glint;
      if (selected.has(ballId)) {
        particleDummy.scale.setScalar(radius * 1.045);
        particleDummy.updateMatrix();
        highlightMesh.setMatrixAt(selectedInstanceCount, particleDummy.matrix);
        selectedInstanceCount += 1;
      }
    }
    highlightMesh.count = selectedInstanceCount;
    particles.instanceMatrix.needsUpdate = true;
    particles.instanceColor.needsUpdate = true;
    drawInsets(ids, xyz, radii, metricValues, colorLow, colorHigh);
    highlightMesh.instanceMatrix.needsUpdate = true;
    body.dataset.frameBallCount = String(ids.length);
    body.dataset.missingBallCount = String(removedFromStaticCount);
    body.dataset.dynamicAddedBallCount = String(dynamicAddedCount);
    body.dataset.highlightCount = String(selected.size);
    body.dataset.highlightOverlayCount = String(selectedInstanceCount);
    body.dataset.highlightPreservesPhysicalColor = "true";
    body.dataset.colorLow = String(colorLow);
    body.dataset.colorHigh = String(colorHigh);
    body.dataset.colorScaleMethod = runtime.colorRange.method;
    updateWalls(frame);
    updateNetworkLayers(frame, ids, xyz);
    updateTrajectories();
  }


  function ensureWallSolidCapacity(count) {
    if (wallSolids && wallSolids.instanceMatrix.count >= count) return;
    if (wallSolids) {
      scene.remove(wallSolids);
      wallSolids.geometry.dispose();
      wallSolids.material.dispose();
    }
    wallSolids = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(1, 1, 1, 8, 1, false),
      new THREE.MeshPhysicalMaterial({
        color: COLORS.primary, roughness: 0.45, metalness: 0.05,
        transparent: true, opacity: 0.65, depthWrite: false
      }),
      Math.max(512, count)
    );
    wallSolids.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    wallSolids.frustumCulled = false;
    scene.add(wallSolids);
  }

  function updateWallSolids(segments) {
    ensureWallSolidCapacity(segments.length);
    const radius = Math.max(span * 0.006, 0.006);
    const up = new THREE.Vector3(0, 1, 0);
    const direction = new THREE.Vector3();
    const midpoint = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    for (let i = 0; i < segments.length; i += 1) {
      const s = segments[i];
      direction.set(s[3] - s[0], s[4] - s[1], s[5] - s[2]);
      const length = direction.length();
      if (length < 1e-9) {
        wallSolidDummy.position.set(0, 0, 0);
        wallSolidDummy.quaternion.identity();
        wallSolidDummy.scale.setScalar(0);
      } else {
        direction.normalize();
        quaternion.setFromUnitVectors(up, direction);
        midpoint.set((s[0] + s[3]) / 2, (s[1] + s[4]) / 2, (s[2] + s[5]) / 2);
        wallSolidDummy.position.copy(midpoint);
        wallSolidDummy.quaternion.copy(quaternion);
        wallSolidDummy.scale.set(radius, length, radius);
      }
      wallSolidDummy.updateMatrix();
      wallSolids.setMatrixAt(i, wallSolidDummy.matrix);
    }
    wallSolids.count = segments.length;
    wallSolids.instanceMatrix.needsUpdate = true;
    wallSolids.visible = byId("showWalls").checked && segments.length > 0;
  }

  function safeComputeBoundingSphere(geometry) {
    const attr = geometry.getAttribute("position");
    if (!attr || attr.count === 0) return;
    // Avoid THREE console errors when a wall frame carries no finite vertices.
    for (let i = 0; i < attr.array.length; i += 1) {
      if (!Number.isFinite(attr.array[i])) return;
    }
    geometry.computeBoundingSphere();
  }

  // Rebuild a CLOSED thin wall shell from the PFC wall point coordinates.
  // PFC gives wall vertices, not a ready-made mesh: we order those real corner
  // points into a closed loop (using the captured facet edge topology when
  // available), then extrude the loop by the wall-rod diameter along the real
  // facet normal. Every corner comes from THIS frame's captured wall vertices,
  // so the platen follows compression without any scaling or fabrication.
  // Falls back to the rod/line rendering when facet topology is absent
  // (PFC2D or old deliveries).
  function updateWallFaces(wallIds, vertexIds, xyz) {
    const caseStatic = staticCases[String(runtime.caseId)] || DATA.static;
    const walls = caseStatic.walls || [];
    if (!wallFaces || !wallEdgeLines || !wallIds || !vertexIds || !xyz || !walls.length) {
      if (wallFaces) wallFaces.visible = false;
      if (wallEdgeLines) wallEdgeLines.visible = false;
      document.body.dataset.wallFaces = "0";
      return;
    }
    const idToVertex = new Map();
    for (let i = 0; i < vertexIds.length; i += 1) {
      const p = [xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]];
      if (p.every(Number.isFinite)) idToVertex.set(vertexIds[i], p);
    }
    // Group this frame's vertices by wall (captured contiguously).
    const groups = [];
    for (let i = 0; i < wallIds.length; i += 1) {
      const last = groups[groups.length - 1];
      if (!last || last.id !== wallIds[i]) groups.push({ id: wallIds[i], ids: [vertexIds[i]] });
      else last.ids.push(vertexIds[i]);
    }
    const half = Math.max(span * 0.006, 0.006); // same radius as the wall rod
    const positions = [];
    const normals = [];
    const edges = [];
    const pushSeg = (a, b) => edges.push(a[0], a[1], a[2], b[0], b[1], b[2]);
    const pushTri = (a, b, c, n) => {
      positions.push(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]);
      for (let k = 0; k < 3; k += 1) normals.push(n[0], n[1], n[2]);
    };
    for (const group of groups) {
      const wall = walls.find((w) => w.id === group.id);
      const facets = (wall && wall.facets) || [];
      if (!facets.length || group.ids.length < 3) continue;
      // Boundary edges appear once in the facet list; interior diagonals
      // appear twice. Chaining the boundary edges gives the ordered loop.
      const edgeKey = (a, b) => (a < b ? a + ":" + b : b + ":" + a);
      const counts = new Map();
      for (const facet of facets) {
        const ids = facet.vertex_ids || [];
        for (let k = 0; k < ids.length; k += 1) {
          const key = edgeKey(ids[k], ids[(k + 1) % ids.length]);
          counts.set(key, (counts.get(key) || 0) + 1);
        }
      }
      const boundary = [];
      for (const [key, count] of counts) {
        if (count === 1) boundary.push(key.split(":").map(Number));
      }
      const loop = [];
      if (boundary.length) {
        loop.push(boundary[0][0], boundary[0][1]);
        for (let guard = 0; guard < boundary.length + 2; guard += 1) {
          const cur = loop[loop.length - 1];
          if (cur === loop[0]) break;
          const next = boundary.find(([a, b]) =>
            (a === cur && loop.indexOf(b) === -1) || (b === cur && loop.indexOf(a) === -1));
          if (!next) break;
          loop.push(next[0] === cur ? next[1] : next[0]);
        }
        if (loop.length > 1 && loop[loop.length - 1] === loop[0]) loop.pop();
      }
      const pts = loop.map((vid) => idToVertex.get(vid));
      if (pts.length < 3 || pts.some((p) => !p)) continue;
      let n = facets[0].normal;
      if (!n || n.length < 3 || !n.every(Number.isFinite)) {
        const u = [pts[1][0] - pts[0][0], pts[1][1] - pts[0][1], pts[1][2] - pts[0][2]];
        const v = [pts[2][0] - pts[0][0], pts[2][1] - pts[0][1], pts[2][2] - pts[0][2]];
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
        const len = Math.hypot(n[0], n[1], n[2]) || 1;
        n = [n[0] / len, n[1] / len, n[2] / len];
      }
      const plus = pts.map((p) => [p[0] + n[0] * half, p[1] + n[1] * half, p[2] + n[2] * half]);
      const minus = pts.map((p) => [p[0] - n[0] * half, p[1] - n[1] * half, p[2] - n[2] * half]);
      for (let k = 0; k < pts.length; k += 1) {
        const j = (k + 1) % pts.length;
        pushSeg(plus[k], plus[j]);
        pushSeg(minus[k], minus[j]);
        pushSeg(plus[k], minus[k]);
      }
      for (let k = 1; k + 1 < pts.length; k += 1) {
        pushTri(plus[0], plus[k], plus[k + 1], n);
        pushTri(minus[0], minus[k + 1], minus[k], n);
      }
      for (let k = 0; k < pts.length; k += 1) {
        const j = (k + 1) % pts.length;
        pushTri(plus[k], minus[k], minus[j], n);
        pushTri(plus[k], minus[j], plus[j], n);
      }
    }
    if (!positions.length) {
      wallFaces.visible = false;
      if (wallEdgeLines) wallEdgeLines.visible = false;
      document.body.dataset.wallFaces = "0";
      return;
    }
    const geo = wallFaces.geometry;
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
    safeComputeBoundingSphere(geo);
    const edgeGeo = wallEdgeLines.geometry;
    edgeGeo.setAttribute("position", new THREE.Float32BufferAttribute(edges, 3));
    safeComputeBoundingSphere(edgeGeo);
    wallFaces.visible = byId("showWalls").checked;
    wallEdgeLines.visible = wallFaces.visible;
    // The slab IS the wall now; hide the degenerate rod/line representation
    // so the two never overlay. Rods remain correct for 2D / old data.
    if (wallSolids) wallSolids.visible = false;
    if (wallLines) wallLines.visible = false;
    if (wallPoints) wallPoints.visible = false;
    document.body.dataset.wallFaces = String(positions.length / 9);
  }

  function updateWalls(frame) {
    if (!frame.wallIds) {
      wallLines.visible = false;
      if (wallPoints) wallPoints.visible = false;
      if (wallSolids) wallSolids.visible = false;
      if (wallFaces) wallFaces.visible = false;
      if (wallEdgeLines) wallEdgeLines.visible = false;
      document.body.dataset.wallFaces = "0";
      return;
    }
    const wallIds = decodeU32(frame.wallIds);
    const vertexIds = decodeU32(frame.wallVertexIds);
    const xyz = decodeF32(frame.wallXyz);
    const positions = [];
    const segments = [];
    for (let index = 1; index < wallIds.length; index += 1) {
      if (wallIds[index] !== wallIds[index - 1]) continue;
      if (vertexIds[index] !== vertexIds[index - 1] + 1) continue;
      const ax = xyz[(index - 1) * 3], ay = xyz[(index - 1) * 3 + 1], az = xyz[(index - 1) * 3 + 2];
      const bx = xyz[index * 3], by = xyz[index * 3 + 1], bz = xyz[index * 3 + 2];
      positions.push(ax, ay, az, bx, by, bz);
      segments.push([ax, ay, az, bx, by, bz]);
    }
    // Reuse the wall line geometry instead of disposing/recreating it every
    // frame (a documented anti-pattern in viewer-state-and-performance.md).
    const attr = wallLines.geometry.getAttribute("position");
    if (!attr || attr.count < positions.length / 3) {
      wallLines.geometry.setAttribute(
        "position", new THREE.Float32BufferAttribute(positions, 3)
      );
    } else {
      for (let i = 0; i < positions.length; i += 1) attr.array[i] = positions[i];
      attr.needsUpdate = true;
      wallLines.geometry.setDrawRange(0, positions.length / 3);
    }
    safeComputeBoundingSphere(wallLines.geometry);
    wallLines.visible = byId("showWalls").checked && positions.length > 0;
    updateWallSolids(segments);
    if (wallPoints) {
      const pointPositions = [];
      for (let i = 0; i < xyz.length; i += 3) {
        pointPositions.push(xyz[i], xyz[i + 1], xyz[i + 2]);
      }
      const pAttr = wallPoints.geometry.getAttribute("position");
      if (!pAttr || pAttr.count < pointPositions.length / 3) {
        wallPoints.geometry.setAttribute("position", new THREE.Float32BufferAttribute(pointPositions, 3));
      } else {
        for (let i = 0; i < pointPositions.length; i += 1) pAttr.array[i] = pointPositions[i];
        pAttr.needsUpdate = true;
        wallPoints.geometry.setDrawRange(0, pointPositions.length / 3);
      }
      safeComputeBoundingSphere(wallPoints.geometry);
      wallPoints.visible = wallLines.visible;
    }
    updateWallFaces(wallIds, vertexIds, xyz);
  }

  function updateNetworkLayers(frame, ids, xyz) {
    const positionsById = new Map();
    for (let index = 0; index < ids.length; index += 1) {
      positionsById.set(
        ids[index],
        [xyz[index * 3], xyz[index * 3 + 1], xyz[index * 3 + 2]]
      );
    }
    const write = (layer, payload, enabled, lowColor, highColor) => {
      if (!layer) return;
      if (!payload || !enabled) {
        layer.visible = false;
        layer.geometry.setDrawRange(0, 0);
        body.dataset[layer === contactLines ? "contactSegments" : "bondSegments"] = "0";
        return;
      }
      const a = decodeU32(payload.a);
      const b = decodeU32(payload.b);
      const force = decodeF32(payload.force);
      const finiteForce = Array.from(force).filter(Number.isFinite);
      const low = finiteForce.length ? Math.min(...finiteForce) : 0;
      const high = finiteForce.length ? Math.max(...finiteForce) : low;
      const lowRgb = new THREE.Color(lowColor);
      const highRgb = new THREE.Color(highColor);
      const positions = [];
      const colors = [];
      for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
        const left = positionsById.get(a[index]);
        const right = positionsById.get(b[index]);
        if (!left || !right) continue;
        positions.push(left[0], left[1], left[2], right[0], right[1], right[2]);
        const t = Number.isFinite(force[index]) && high > low
          ? Math.max(0, Math.min(1, (force[index] - low) / (high - low)))
          : 0;
        const color = lowRgb.clone().lerp(highRgb, t);
        colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      }
      layer.geometry.dispose();
      const geometry = new THREE.BufferGeometry();
      const positionAttribute = new THREE.Float32BufferAttribute(positions, 3);
      positionAttribute.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute("position", positionAttribute);
      geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      geometry.setDrawRange(0, positions.length / 3);
      layer.geometry = geometry;
      layer.visible = positions.length > 0;
      body.dataset[layer === contactLines ? "contactSegments" : "bondSegments"] =
        String(positions.length / 6);
    };
    write(
      contactLines,
      frame.contacts,
      byId("showContacts").checked,
      COLORS.tan,
      COLORS.fracture
    );
    write(
      bondLines,
      frame.bonds,
      byId("showBonds").checked,
      COLORS.primary,
      COLORS.fracture
    );
  }

  function highlightIdsForState() {
    const state = store.get();
    const selected = new Set(state.selectedBallIds);
    if (state.selectedRange && currentFrameData) {
      const values = decodeF32(
        state.selectedMetric === "speed"
          ? currentFrameData.speed
          : (state.selectedMetric === "acceleration"
            ? currentFrameData.acceleration
            : currentFrameData.displacement)
      );
      const ids = decodeU32(currentFrameData.ids);
      const range = state.selectedRange;
      for (let index = 0; index < ids.length; index += 1) {
        if (Number.isFinite(values[index]) && values[index] >= range[0] && values[index] <= range[1]) {
          selected.add(ids[index]);
        }
      }
    }
    return Array.from(selected);
  }

  function updateSelectionVisuals() {
    if (!currentFrameData || !particles) return;
    const highlightIds = highlightIdsForState();
    updateParticles(currentFrameData, highlightIds);
    updateSelectionSummary(highlightIds);
  }

  function updateSelectionSummary(highlightIds) {
    const state = store.get();
    const summary = byId("selectionSummary");
    const span = summary.querySelector("span");
    const detail = summary.querySelector("small");
    if (state.selectedRange) {
      const metric = state.selectedMetric === "speed"
        ? "速度"
        : (state.selectedMetric === "acceleration" ? "加速度" : "累计位移");
      span.textContent = metric + " ∈ [" + formatNumber(state.selectedRange[0], 4) + ", " +
        formatNumber(state.selectedRange[1], 4) + "]";
      detail.textContent = "当前帧高亮 " + highlightIds.length + " 个颗粒；区间只作用于当前真实采样帧";
    } else if (state.selectedBallIds.length) {
      span.textContent = "Ball ID: " + state.selectedBallIds.slice(0, 8).join(", ") +
        (state.selectedBallIds.length > 8 ? " …" : "");
      detail.textContent = "Shift/Ctrl 点击可多选；历史曲线仅连接实测观测";
    } else {
      span.textContent = "未选择颗粒";
      detail.textContent = "点击三维颗粒，或拖动当前分布图选择区间";
    }
  }

  function handleSceneClick(event) {
    if (!pointerDown || !currentFrameData) return;
    const moved = Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y);
    pointerDown = null;
    if (moved > 4) return;
    const rect = renderer.domElement.getBoundingClientRect();
    const pointer = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1
    );
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: span * 0.01 };
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObject(particles, false);
    if (!hits.length || hits[0].instanceId == null) return;
    const ballId = visibleIds[hits[0].instanceId];
    if (ballId == null) return;
    actions.selectBalls([ballId], {
      additive: event.shiftKey || event.ctrlKey || event.metaKey,
      focus: event.altKey,
      source: "scene"
    });
  }

  function clearTrajectories() {
    runtime.trajectories.forEach((line) => {
      scene.remove(line);
      line.geometry.dispose();
      line.material.dispose();
    });
    runtime.trajectories = [];
  }

  function updateTrajectories() {
    clearTrajectories();
    if (!byId("showTrajectory").checked || !runtime.current) return;
    const palette = [COLORS.accent, COLORS.primary, COLORS.fracture, COLORS.tan, COLORS.slate];
    const ids = store.get().selectedBallIds;
    ids.slice(0, 8).forEach((ballId, index) => {
      const rows = runtime.selectedHistories.get(ballId);
      if (!rows || rows.length < 2) return;
      const points = rows.map((row) => new THREE.Vector3(row.x, row.y, row.z));
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({
          color: palette[index % palette.length],
          transparent: true,
          opacity: 0.92,
          depthTest: false
        })
      );
      line.renderOrder = 25;
      line.frustumCulled = false;
      scene.add(line);
      runtime.trajectories.push(line);
    });
  }

  function focusBall(ballId) {
    if (!currentFrameData) return;
    const ids = decodeU32(currentFrameData.ids);
    const xyz = decodeF32(currentFrameData.xyz);
    const index = Array.prototype.indexOf.call(ids, ballId);
    if (index < 0) {
      byId("ballInput").setCustomValidity("当前真实帧不包含该 Ball ID。");
      byId("ballInput").reportValidity();
      return false;
    }
    byId("ballInput").setCustomValidity("");
    const point = new THREE.Vector3(xyz[index * 3], xyz[index * 3 + 1], xyz[index * 3 + 2]);
    const direction = camera.position.clone().sub(controls.target).normalize();
    controls.target.copy(point);
    camera.position.copy(point).add(direction.multiplyScalar(Math.max(span * 0.26, 1e-9)));
    camera.lookAt(point);
    controls.update();
    return true;
  }

  function createChartPanel(title, status, wide) {
    const section = document.createElement("section");
    section.className = "chart-panel" + (wide ? " wide" : "");
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    heading.textContent = title;
    const note = document.createElement("span");
    note.textContent = status || "";
    const div = document.createElement("div");
    div.className = "chart";
    header.append(heading, note);
    section.append(header, div);
    return { section, div, title: heading, status: note };
  }

  function chartColors() {
    return [
      COLORS.primary, COLORS.fracture, COLORS.slate, COLORS.tan, COLORS.accent
    ];
  }

  function axisStyle(name, unit, formatting, axisContract) {
    return {
      type: "value",
      name: axisDisplayName(name, unit, formatting),
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: { color: COLORS.muted, fontSize: 9 },
      scale: Boolean(axisContract && axisContract.include_zero === false),
      axisLine: { lineStyle: { color: COLORS.axis, width: 0.8 } },
      axisTick: { lineStyle: { color: COLORS.axisTick, width: 0.6 } },
      axisLabel: {
        color: COLORS.muted,
        fontSize: 9,
        hideOverlap: true,
        formatter: (value) => formatAxisValue(value, formatting)
      },
      splitLine: { show: false }
    };
  }

  function categoryStyle(name, unit, data, formatting) {
    return {
      type: "category",
      name: axisDisplayName(name, unit, formatting),
      data,
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: { color: COLORS.muted, fontSize: 9 },
      boundaryGap: false,
      axisLine: { lineStyle: { color: COLORS.axis, width: 0.8 } },
      axisTick: { show: false },
      axisLabel: {
        color: COLORS.muted,
        fontSize: 9,
        hideOverlap: true,
        formatter: (value) => (
          finiteNumber(value) === null
            ? String(value)
            : formatAxisValue(value, formatting)
        )
      },
      splitLine: { show: false }
    };
  }

  function baseOption(spec) {
    return {
      animation: false,
      textStyle: { fontFamily: "Arial, Helvetica, PingFang SC, Microsoft YaHei, sans-serif" },
      title: {
        show: false,
        text: spec && spec.title ? spec.title : "",
        left: 12,
        top: 8,
        textStyle: {
          color: COLORS.ink,
          fontSize: 12,
          fontWeight: 600,
          fontFamily: "Arial, Helvetica, PingFang SC, Microsoft YaHei, sans-serif"
        }
      },
      grid: { left: 68, right: 32, top: 58, bottom: 64, containLabel: true },
      tooltip: {
        trigger: "axis",
        confine: true,
        backgroundColor: COLORS.tooltipBackground,
        borderColor: COLORS.tooltipBorder,
        textStyle: { color: COLORS.ink, fontSize: 10 },
        axisPointer: { type: "cross", lineStyle: { color: COLORS.slate, width: 0.7 } },
        formatter: (input) => {
          const rows = Array.isArray(input) ? input : [input];
          if (!rows.length) return "";
          const firstValue = rows[0].value;
          const heading = Array.isArray(firstValue)
            ? ((spec && spec.x && spec.x.name) || "x") + ": " +
              formatTooltipValue(firstValue[0], spec && spec.display && spec.display.x && spec.display.x.formatting)
            : (rows[0].axisValueLabel ?? rows[0].name ?? "");
          const seen = new Set();
          const body = rows.filter((row) => {
            const raw = Array.isArray(row.value) ? row.value[row.value.length - 1] : row.value;
            const key = String(row.seriesIndex) + ":" + String(row.seriesName) + ":" + String(raw);
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          }).map((row) => {
            const raw = Array.isArray(row.value) ? row.value[row.value.length - 1] : row.value;
            const seriesFormatting = spec && spec.display && Array.isArray(spec.display.series)
              ? spec.display.series[row.seriesIndex || 0]
              : null;
            const valueFormatting = Array.isArray(row.value) && row.value.length === 3
              ? (spec && spec.display && spec.display.z)
              : (seriesFormatting || (spec && spec.display && spec.display.y));
            return (row.marker || "") + row.seriesName + ": " +
              formatTooltipValue(raw, valueFormatting && valueFormatting.formatting);
          });
          return [heading].concat(body).filter(Boolean).join("<br>");
        }
      },
      legend: {
        right: 10,
        top: 20,
        itemWidth: 13,
        itemHeight: 2,
        textStyle: { color: COLORS.muted, fontSize: 9 },
        selectedMode: false
      }
    };
  }

  function lineSeries(name, data, color, axisIndex) {
    return {
      name,
      type: "line",
      data,
      yAxisIndex: axisIndex || 0,
      showSymbol: false,
      connectNulls: false,
      smooth: false,
      lineStyle: { width: 1.35, color },
      itemStyle: { color },
      emphasis: { focus: "series" }
    };
  }

  function histogramOption(spec) {
    const option = baseOption(spec);
    const centers = [];
    for (let index = 0; index < spec.edges.length - 1; index += 1) {
      centers.push((spec.edges[index] + spec.edges[index + 1]) / 2);
    }
    const labels = Array.isArray(spec.bin_labels) &&
      spec.bin_labels.length === spec.counts.length
      ? spec.bin_labels
      : centers;
    option.grid = { left: 60, right: 24, top: 58, bottom: 74, containLabel: true };
    option.xAxis = categoryStyle(
      spec.value_name || "分箱中心",
      spec.unit || "",
      labels,
      spec.display && spec.display.x && spec.display.x.formatting
    );
    option.xAxis.boundaryGap = true;
    option.yAxis = axisStyle(
      "颗粒数",
      "count",
      spec.display && spec.display.y && spec.display.y.formatting,
      spec.axis_contract && spec.axis_contract.y
    );
    option.series = [{
      type: "bar",
      data: spec.counts,
      barCategoryGap: "2%",
      itemStyle: { color: spec.color || COLORS.slate, opacity: 0.86 }
    }];
    return option;
  }

  function heatmapOption(spec) {
    const option = baseOption(spec);
    const xCenters = spec.x.slice(0, -1).map((value, index) => (value + spec.x[index + 1]) / 2);
    const yCenters = spec.y.slice(0, -1).map((value, index) => (value + spec.y[index + 1]) / 2);
    const points = [];
    let maximum = 0;
    spec.z.forEach((row, xIndex) => row.forEach((value, yIndex) => {
      const number = finiteNumber(value);
      if (number !== null) maximum = Math.max(maximum, number);
      points.push([xIndex, yIndex, number]);
    }));
    option.grid = { left: 84, right: 68, top: 60, bottom: 80, containLabel: true };
    option.tooltip = { ...option.tooltip, trigger: "item" };
    option.xAxis = categoryStyle(
      spec.x_name || "x 分箱中心",
      "m",
      xCenters,
      spec.display && spec.display.x && spec.display.x.formatting
    );
    option.yAxis = categoryStyle(
      spec.y_name || "y 分箱中心",
      "m",
      yCenters,
      spec.display && spec.display.y && spec.display.y.formatting
    );
    option.xAxis.boundaryGap = false;
    option.yAxis.boundaryGap = false;
    option.xAxis.axisLabel.interval = Math.max(0, Math.floor(xCenters.length / 6));
    option.yAxis.axisLabel.interval = Math.max(0, Math.floor(yCenters.length / 7));
    option.visualMap = {
      min: 0,
      max: Math.max(1, maximum),
      calculable: false,
      orient: "vertical",
      right: 5,
      top: "middle",
      itemWidth: 8,
      itemHeight: 86,
      text: spec.value_name ? [spec.value_name + "（高）", spec.unit || ""] : ["颗粒数（高）", "0"],
      textStyle: { color: COLORS.muted, fontSize: 8.5 },
      inRange: { color: [COLORS.heatmapLow, COLORS.heatmapMid, COLORS.primary] }
    };
    option.series = [{
      type: "heatmap",
      data: points,
      itemStyle: { borderWidth: 0, borderRadius: 1, opacity: 0.96 },
      emphasis: { itemStyle: { borderColor: COLORS.ink, borderWidth: 0.6 } }
    }];
    return option;
  }

  function correlationOption(spec) {
    const option = heatmapOption({
      x: spec.labels,
      y: spec.labels,
      z: spec.values,
      unit: ""
    });
    const values = [];
    spec.values.forEach((row, xIndex) => row.forEach((value, yIndex) => values.push([xIndex, yIndex, value])));
    option.grid = { left: 100, right: 76, top: 58, bottom: 96, containLabel: true };
    option.xAxis = {
      type: "category", data: spec.labels, axisLabel: { color: COLORS.muted, fontSize: 9, interval: 0, rotate: 18 }
    };
    option.yAxis = {
      type: "category", data: spec.labels, axisLabel: { color: COLORS.muted, fontSize: 9, interval: 0 }
    };
    option.visualMap = {
      min: -1, max: 1, calculable: false, orient: "vertical", right: 6, top: "middle",
      itemWidth: 8, itemHeight: 86, text: ["Pearson r +1", "Pearson r −1"],
      textStyle: { color: COLORS.muted, fontSize: 8.5 },
      inRange: { color: [COLORS.fracture, COLORS.chartBackground, COLORS.primary] }
    };
    option.series = [{ type: "heatmap", data: values, itemStyle: { borderWidth: 0.5, borderColor: COLORS.chartBackground } }];
    return option;
  }

  function roseOption(spec) {
    let bins, labels;
    if (Array.isArray(spec.sector_counts) && spec.sector_counts.length) {
      bins = spec.sector_counts.map((value) => finiteNumber(value) ?? 0);
      const edges = spec.sector_edges_deg || [];
      labels = bins.map((_, index) => (
        edges.length > index + 1
          ? String(edges[index]) + "–" + String(edges[index + 1])
          : String(index * 22.5)
      ));
    } else {
      bins = new Array(16).fill(0);
      (spec.angles || []).forEach((angle) => {
        const number = finiteNumber(angle);
        if (number === null) return;
        const index = Math.max(0, Math.min(15, Math.floor((number % 360) / 22.5)));
        bins[index] += 1;
      });
      labels = bins.map((_, index) => String(index * 22.5));
    }
    const option = baseOption(spec);
    option.tooltip.trigger = "item";
    option.grid = null;
    option.legend = { show: false };
    option.polar = { radius: "68%" };
    option.angleAxis = {
      type: "category", data: labels, boundaryGap: true,
      axisLine: { lineStyle: { color: "#3d3d3d", width: 0.8 } },
      axisLabel: { color: COLORS.muted, fontSize: 8 },
      splitLine: { show: false }
    };
    option.radiusAxis = {
      type: "value",
      axisLabel: { color: COLORS.muted, fontSize: 8 },
      splitLine: { lineStyle: { color: COLORS.grid, width: 0.6 } }
    };
    option.series = [{
      type: "bar", coordinateSystem: "polar", data: bins,
      itemStyle: { color: spec.color || COLORS.fracture, opacity: 0.84 }
    }];
    return option;
  }

  function radarOption(spec) {
    const option = baseOption(spec);
    option.grid = null;
    option.radar = {
      indicator: spec.indicators,
      radius: "62%",
      splitLine: { lineStyle: { color: COLORS.grid } },
      axisLine: { lineStyle: { color: COLORS.grid } },
      axisName: { color: COLORS.muted, fontSize: 8 }
    };
    option.series = [{
      type: "radar",
      data: spec.series.map((item, index) => ({
        ...item,
        lineStyle: { color: chartColors()[index % 5], width: 1.2 },
        itemStyle: { color: chartColors()[index % 5] }
      }))
    }];
    return option;
  }

  function caseCompareOption(spec) {
    const option = baseOption(spec);
    const missingIds = new Set((spec.missing_case_ids || []).map(Number));
    const seriesColor = spec.color || COLORS.primary;
    option.xAxis = {
      type: "category",
      data: spec.data.map((row) => "C" + row.case_id),
      axisLine: { lineStyle: { color: "#3d3d3d", width: 0.8 } },
      axisTick: { show: false },
      axisLabel: {
        color: COLORS.muted,
        fontSize: 8.5,
        interval: 0,
        formatter: (value, index) => (
          missingIds.has(Number(spec.data[index] && spec.data[index].case_id))
            ? "{missing|" + value + "}"
            : value
        ),
        rich: {
          missing: { color: COLORS.missing, fontSize: 8.5 }
        }
      }
    };
    option.yAxis = axisStyle(
      spec.metric_name || "值",
      spec.metric_unit || "",
      spec.display && spec.display.values && spec.display.values.formatting,
      spec.axis_contract && spec.axis_contract.y
    );
    option.series = [{
      name: spec.metric_name || "多 Case 比较",
      type: "bar",
      data: spec.data.map((row) => {
        const raw = finiteNumber(row[spec.metric_key]);
        return {
          value: raw === null ? null : raw * (spec.scale || 1),
          itemStyle: { color: seriesColor }
        };
      }),
      barMaxWidth: 22
    }];
    option.legend = { show: false };
    option.tooltip = {
      ...option.tooltip,
      trigger: "item",
      formatter: (params) => {
        const row = spec.data[params.dataIndex];
        if (!row) return "";
        const caseId = "C" + row.case_id;
        const raw = finiteNumber(row[spec.metric_key]);
        if (raw === null) {
          const availability = (spec.case_availability || []).find(
            (item) => Number(item.case_id) === Number(row.case_id)
          );
          return caseId + "<br>" + (spec.metric_name || "值") + ": 未采集" +
            "<br>原因: " + escapeHtml((availability && availability.reason) || "NOT_CAPTURED");
        }
        const formatting = spec.display && spec.display.values &&
          spec.display.values.formatting;
        return caseId + "<br>" + params.marker + (spec.metric_name || "值") + ": " +
          formatTooltipValue(raw * (spec.scale || 1), formatting) +
          (spec.metric_unit && spec.metric_unit !== "1" ? " " + spec.metric_unit : "");
      }
    };
    return option;
  }

  function buildChartOption(spec) {
    if (!spec) return null;
    if (spec.type === "histogram") return histogramOption(spec);
    if (spec.type === "heatmap") return heatmapOption(spec);
    if (spec.type === "correlation") return correlationOption(spec);
    if (spec.type === "rose") return roseOption(spec);
    if (spec.type === "polar") {
      return Array.isArray(spec.angles) && spec.angles.length
        ? roseOption(spec)
        : null;
    }
    if (spec.type === "radar") return radarOption(spec);
    if (spec.type === "case-compare") return caseCompareOption(spec);
    if (!["line", "scatter", "area", "dual-line", "bar", "grouped-bar", "stacked-bar", "boxplot"].includes(spec.type)) {
      return null;
    }
    const option = baseOption(spec);
    if (spec.type === "dual-line") {
      option.yAxis = [
        axisStyle(
          spec.series[0].name,
          spec.series[0].unit,
          spec.display && spec.display.series && spec.display.series[0] && spec.display.series[0].formatting,
          spec.axis_contract && spec.axis_contract.series && spec.axis_contract.series[0]
        ),
        axisStyle(
          spec.series[1].name,
          spec.series[1].unit,
          spec.display && spec.display.series && spec.display.series[1] && spec.display.series[1].formatting,
          spec.axis_contract && spec.axis_contract.series && spec.axis_contract.series[1]
        )
      ];
      option.yAxis[1].splitLine = { show: false };
      option.series = spec.series.map((item, index) => lineSeries(
        item.name, item.data, item.color || chartColors()[index], item.axis || index
      ));
      option.xAxis = categoryStyle(
        spec.x.name || "Cycle",
        spec.x.unit || "",
        spec.x.data,
        spec.display && spec.display.x && spec.display.x.formatting
      );
    } else {
      option.tooltip.trigger = "item";
      option.xAxis = axisStyle(
        (spec.x && spec.x.name) || "x",
        (spec.x && spec.x.unit) || "",
        spec.display && spec.display.x && spec.display.x.formatting,
        spec.axis_contract && spec.axis_contract.x
      );
      option.xAxis.data = spec.x ? spec.x.data : null;
      option.xAxis.type = "value";
      option.yAxis = axisStyle(
        (spec.y && spec.y.name) || "y",
        (spec.y && spec.y.unit) || "",
        spec.display && spec.display.y && spec.display.y.formatting,
        spec.axis_contract && spec.axis_contract.y
      );
      if (spec.type === "bar" || spec.type === "grouped-bar" || spec.type === "stacked-bar") {
        const categories = spec.x && spec.x.data ? spec.x.data : [];
        option.xAxis = {
          ...categoryStyle(
            (spec.x && spec.x.name) || "category",
            (spec.x && spec.x.unit) || "",
            categories,
            spec.display && spec.display.x && spec.display.x.formatting
          ),
          boundaryGap: true
        };
        const series = spec.series || [{ name: spec.y && spec.y.name, data: spec.y && spec.y.data, color: spec.color }];
        option.series = series.map((item, index) => ({
          name: item.name, type: "bar", stack: spec.type === "stacked-bar" ? "total" : undefined,
          data: item.data, barMaxWidth: 24,
          itemStyle: { color: item.color || chartColors()[index] }
        }));
      } else if (spec.type === "boxplot") {
        option.xAxis = categoryStyle(
          "分组",
          "",
          spec.labels || [],
          spec.display && spec.display.x && spec.display.x.formatting
        );
        option.series = [{ type: "boxplot", data: spec.data, itemStyle: { color: spec.color || COLORS.slate } }];
      } else {
        const xyData = spec.x && Array.isArray(spec.x.data) && spec.y && Array.isArray(spec.y.data)
          ? spec.y.data.map((value, index) => {
            const xValue = finiteNumber(spec.x.data[index]);
            const yValue = finiteNumber(value);
            return xValue === null || yValue === null ? [null, null] : [xValue, yValue];
          })
          : (spec.y ? spec.y.data : []);
        const userOptions = spec.options || {};
        const seriesColor = userOptions.color || spec.color || COLORS.primary;
        option.series = [{
          name: (spec.y && spec.y.name) || spec.title,
          type: spec.type === "area" ? "line" : (spec.type === "scatter" ? "scatter" : "line"),
          data: xyData,
          showSymbol: userOptions.show_symbol != null ? !!userOptions.show_symbol : spec.type === "scatter",
          symbolSize: userOptions.symbol_size || (spec.type === "scatter" ? 4 : undefined),
          areaStyle: spec.type === "area" ? { color: seriesColor, opacity: 0.14 } : undefined,
          lineStyle: {
            color: seriesColor,
            width: userOptions.line_width || 1.5
          },
          itemStyle: { color: seriesColor }
        }];
      }
    }
    option.series = (option.series || []).filter(Boolean);
    return option;
  }

  function isTemporalSpec(spec) {
    if (!spec || spec.case_id == null || !runtime.current) return false;
    if (!["line", "scatter", "area", "dual-line"].includes(spec.type)) return false;
    return Boolean(
      spec.x &&
      Array.isArray(spec.x.data) &&
      spec.x.data.length >= 2 &&
      ["s", "cycle"].includes(spec.x.unit)
    );
  }

  function temporalFrameIndex(spec, dataIndex) {
    if (!runtime.current || !spec || !spec.x || dataIndex < 0) return -1;
    if (Array.isArray(spec.source_indices)) {
      const sourceValue = finiteNumber(spec.source_indices[dataIndex]);
      const sourceIndex = sourceValue === null ? null : Math.round(sourceValue);
      if (sourceIndex === null) return -1;
      return runtime.current.meta.frames.findIndex((frame) => (
        finiteNumber(frame.sourceIndex) === sourceIndex
      ));
    }
    const value = spec.x.data[dataIndex];
    const frameValues = runtime.current.meta.frames.map((frame) => (
      spec.x.unit === "s" ? frame.time : frame.cycle
    ));
    return nearestIndex(frameValues, Number(value));
  }

  function currentTemporalValue(spec) {
    const state = store.get();
    return spec.x.unit === "s" ? state.currentTime : state.currentCycle;
  }

  function attachTemporalInteraction(chart, spec, container) {
    if (!isTemporalSpec(spec)) return;
    const cursor = document.createElement("div");
    cursor.className = "time-cursor";
    container.appendChild(cursor);
    chart.__temporalCursor = cursor;
    chart.__temporalSpec = spec;
    chart.on("click", (event) => {
      if (event.dataIndex != null) {
        const frameIndex = temporalFrameIndex(spec, event.dataIndex);
        if (frameIndex >= 0) actions.setFrame(frameIndex, { source: "chart-click" });
      }
    });
    const zr = chart.getZr();
    let dragging = false;
    const updateFromPointer = (event) => {
      let point;
      try {
        point = chart.convertFromPixel({ gridIndex: 0 }, [event.offsetX, event.offsetY]);
      } catch (ignored) {
        return;
      }
      if (!point) return;
      const values = spec.x.data;
      const dataIndex = nearestIndex(values, Number(point[0]));
      const frameIndex = temporalFrameIndex(spec, dataIndex);
      if (frameIndex >= 0) actions.setFrame(frameIndex, { source: "chart-drag" });
    };
    zr.on("mousedown", (event) => {
      dragging = true;
      updateFromPointer(event);
    });
    zr.on("mousemove", (event) => {
      if (!dragging) return;
      updateFromPointer(event);
    });
    zr.on("mouseup", () => { dragging = false; });
    zr.on("globalout", () => { dragging = false; });
    container.addEventListener("mouseleave", () => { dragging = false; });
    zr.setCursorStyle("crosshair");
  }

  function updateTemporalMarkers() {
    if (!runtime.ready || !runtime.current) return;
    runtime.charts.forEach((entry) => {
      const spec = entry.spec;
      const cursor = entry.chart && entry.chart.__temporalCursor;
      if (!spec || !cursor || !isTemporalSpec(spec)) return;
      const x = Number(currentTemporalValue(spec));
      let pixel;
      try {
        pixel = entry.chart.convertToPixel({ xAxisIndex: 0 }, x);
      } catch (ignored) {
        pixel = null;
      }
      if (!Number.isFinite(pixel)) {
        cursor.hidden = true;
        return;
      }
      cursor.hidden = false;
      cursor.style.left = pixel.toFixed(2) + "px";
    });
    if (runtime.historyChart && runtime.historyChart.__temporal) {
      const value = store.get().currentCycle;
      const cursor = runtime.historyChart.__temporalCursor;
      if (cursor && Number.isFinite(value)) {
        let pixel = null;
        try {
          pixel = runtime.historyChart.convertToPixel({ xAxisIndex: 0 }, value);
        } catch (ignored) {}
        if (Number.isFinite(pixel)) {
          cursor.hidden = false;
          cursor.style.left = pixel.toFixed(2) + "px";
        }
      }
    }
  }

  function makeChartEntries(specs) {
    runtime.charts.forEach((entry) => entry.chart.dispose());
    runtime.charts = [];
    byId("chartGrid").replaceChildren();
    const metricStatus = runtime.current.meta.metricStatus || {};
    runtime.currentCharts.displacement = metricStatus.displacement === "SUPPORTED"
      ? addCurrentHistogram("当前帧累计位移分布", "displacement")
      : null;
    runtime.currentCharts.speed = metricStatus.speed === "SUPPORTED"
      ? addCurrentHistogram("当前帧速度分布", "speed")
      : null;
    specs.forEach((spec) => {
      const sourceLabel = spec.type === "case-compare"
        ? "可用 " + Number(spec.available_case_count || 0) + "/" +
          Number(spec.total_case_count || 0) + " · 缺失 " +
          Number(spec.missing_case_count || 0)
        : spec.case_id == null
          ? "Experiment"
          : (spec.decision && spec.decision.derived ? "DERIVED" : "REAL_PFC");
      const panel = createChartPanel(spec.title || spec.id || "数据图", sourceLabel);
      if (spec.type === "case-compare") {
        panel.section.dataset.availableCaseCount = String(spec.available_case_count || 0);
        panel.section.dataset.totalCaseCount = String(spec.total_case_count || 0);
        panel.section.dataset.missingCaseCount = String(spec.missing_case_count || 0);
        panel.section.dataset.missingCaseIds = (spec.missing_case_ids || []).join(",");
        panel.status.title = "缺失 Case: " + (spec.missing_case_ids || []).join(", ");
      }
      panel.section.title = spec.decision && spec.decision.reason
        ? spec.decision.reason
        : (spec.basis || "");
      byId("chartGrid").appendChild(panel.section);
      const option = buildChartOption(spec);
      if (!option) {
        const empty = document.createElement("div");
        empty.className = "empty-chart";
        empty.textContent = "该图表类型有数据声明但当前 Viewer 不支持渲染。";
        panel.section.appendChild(empty);
        return;
      }
      const chart = echarts.init(panel.div, null, { renderer: "svg" });
      chart.setOption(option, { notMerge: true, lazyUpdate: false });
      attachTemporalInteraction(chart, spec, panel.section);
      runtime.charts.push({ chart, spec, panel });
    });
    body.dataset.chartCount = String(runtime.charts.filter((entry) => !entry.linkedHistogram).length);
    body.dataset.linkedChartCount = String(runtime.charts.filter((entry) => entry.linkedHistogram).length);
    body.dataset.chartRenderer = "svg";
  }

  function quantileSorted(sorted, probability) {
    if (!sorted.length) return null;
    if (sorted.length === 1) return sorted[0];
    const position = (sorted.length - 1) * probability;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    if (lower === upper) return sorted[lower];
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
  }

  function histogramFormatting(values) {
    const finite = values.map(finiteNumber).filter((value) => value !== null);
    const nonzero = finite.map(Math.abs).filter((value) => value > 0);
    if (!nonzero.length) return null;
    const smallest = Math.min(...nonzero);
    const largest = Math.max(...nonzero);
    const scientific = smallest < 1.0e-3 || largest >= 1.0e5;
    if (!scientific) return { axis_notation: "DECIMAL", decimals: 4 };
    const exponent = Math.floor(Math.log10(largest));
    const scale = Math.pow(10, exponent);
    const superscript = String(exponent)
      .replace(/-/g, "⁻")
      .replace(/[0-9]/g, (digit) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[Number(digit)]);
    return {
      axis_notation: "SCIENTIFIC_SHARED_EXPONENT",
      axis_exponent: exponent,
      axis_scale: scale,
      axis_scale_label: "× 10" + superscript,
      decimals: 3
    };
  }

  function robustHistogramBins(values, count = 32) {
    const finite = values.map(finiteNumber)
      .filter((value) => value !== null)
      .sort((left, right) => left - right);
    if (!finite.length) return null;
    const q05 = quantileSorted(finite, 0.05);
    const q95 = quantileSorted(finite, 0.95);
    const underflow = finite.filter((value) => value < q05);
    const overflow = finite.filter((value) => value > q95);
    const interior = finite.filter((value) => value >= q05 && value <= q95);
    let interiorCounts;
    let interiorEdges;
    if (q95 > q05 && interior.length) {
      const binCount = Math.min(count, Math.max(5, interior.length));
      interiorCounts = new Array(binCount).fill(0);
      const width = (q95 - q05) / binCount;
      interior.forEach((value) => {
        const index = Math.max(
          0,
          Math.min(binCount - 1, Math.floor((value - q05) / width))
        );
        interiorCounts[index] += 1;
      });
      interiorEdges = Array.from(
        { length: binCount + 1 },
        (_, index) => q05 + width * index
      );
    } else {
      interiorCounts = [interior.length];
      interiorEdges = [q05, q95];
    }
    const centers = interiorEdges.slice(0, -1).map(
      (value, index) => (value + interiorEdges[index + 1]) * 0.5
    );
    const labels = ["< P05", ...centers, "> P95"];
    const bins = [
      underflow.length,
      ...interiorCounts,
      overflow.length
    ];
    const ranges = [
      [finite[0], q05],
      ...interiorEdges.slice(0, -1).map(
        (value, index) => [value, interiorEdges[index + 1]]
      ),
      [q95, finite[finite.length - 1]]
    ];
    return {
      centers,
      labels,
      bins,
      edges: interiorEdges,
      ranges,
      formatting: histogramFormatting(centers),
      rangePolicy: "ROBUST_P05_P95_WITH_OVERFLOW",
      finiteCount: finite.length,
      underflowCount: underflow.length,
      overflowCount: overflow.length,
      interiorMin: q05,
      interiorMax: q95,
      observedMin: finite[0],
      observedMax: finite[finite.length - 1]
    };
  }

  function addCurrentHistogram(title, metric) {
    const panel = createChartPanel(title, "linked");
    byId("chartGrid").appendChild(panel.section);
    const chart = echarts.init(panel.div, null, { renderer: "svg" });
    const unit = metric === "speed" ? "m/s" : "m";
    chart.setOption({
      ...baseOption({ title }),
      grid: { left: 56, right: 20, top: 56, bottom: 72, containLabel: true },
      tooltip: { ...baseOption({}).tooltip, trigger: "axis" },
      brush: { xAxisIndex: 0, throttleType: "debounce", throttleDelay: 80 },
      toolbox: { show: false },
      xAxis: categoryStyle(metric === "speed" ? "速度分箱" : "累计位移分箱", unit, []),
      yAxis: axisStyle("颗粒数", "count", null, { include_zero: true }),
      series: [{
        type: "bar",
        data: [],
        barCategoryGap: "2%",
        itemStyle: { color: metric === "speed" ? COLORS.slate : COLORS.primary, opacity: 0.86 },
        markArea: { silent: true, itemStyle: { color: "rgba(243,155,127,0.16)" }, data: [] }
      }]
    }, { notMerge: true });
    chart.__metric = metric;
    chart.__histogram = null;
    chart.on("brushSelected", (event) => {
      const batch = event.batch && event.batch[0];
      const area = batch && batch.areas && batch.areas[0];
      if (!area || !area.coordRange || !chart.__histogram) return;
      const range = area.coordRange;
      const data = chart.__histogram;
      const last = data.ranges.length;
      const start = Math.max(0, Math.min(last - 1, Math.floor(Number(range[0]))));
      const end = Math.max(start + 1, Math.min(last, Math.ceil(Number(range[1]))));
      actions.setRange(
        [data.ranges[start][0], data.ranges[end - 1][1]],
        metric,
        { source: "histogram-brush" }
      );
    });
    chart.getZr().on("click", (event) => {
      const point = chart.convertFromPixel({ gridIndex: 0 }, [event.offsetX, event.offsetY]);
      if (!point || !chart.__histogram) return;
      const index = Math.max(
        0,
        Math.min(chart.__histogram.ranges.length - 1, Math.round(Number(point[0])))
      );
      actions.setRange(
        chart.__histogram.ranges[index],
        metric,
        { source: "histogram-click" }
      );
    });
    chart.getZr().setCursorStyle("crosshair");
    chart.dispatchAction({
      type: "takeGlobalCursor",
      key: "brush",
      brushOption: { brushType: "lineX", brushMode: "single" }
    });
    runtime.charts.push({ chart, spec: null, panel, linkedHistogram: true, metric });
    return chart;
  }

  function updateCurrentHistograms(frame) {
    if (!frame) return;
    const summary = runtime.current.summary;
    const specs = {
      displacement: {
        values: decodeF32(frame.displacement),
        hi: Math.max(summary.maxDisplacement, 1e-12)
      },
      speed: {
        values: decodeF32(frame.speed),
        hi: Math.max(summary.maxSpeed, 1e-12)
      }
    };
    Object.entries(runtime.currentCharts).forEach(([metric, chart]) => {
      if (!chart) return;
      const source = specs[metric];
      const finite = source.values.filter(Number.isFinite);
      const entry = runtime.charts.find((item) => item.chart === chart);
      if (!finite.length) {
        chart.__histogram = {
          centers: [],
          labels: [],
          bins: [],
          edges: [],
          ranges: []
        };
        chart.setOption({
          xAxis: { data: [] },
          series: [{ data: [] }]
        }, { lazyUpdate: true, silent: true });
        if (entry && entry.panel) entry.panel.status.textContent = "NOT_CAPTURED";
        return;
      }
      const histogram = robustHistogramBins(source.values, 32);
      if (!histogram) {
        if (entry && entry.panel) entry.panel.status.textContent = "NOT_CAPTURED";
        return;
      }
      chart.__histogram = histogram;
      chart.setOption({
        xAxis: categoryStyle(
          metric === "speed" ? "速度分箱" : "累计位移分箱",
          metric === "speed" ? "m/s" : "m",
          histogram.labels,
          histogram.formatting
        ),
        series: [{ data: histogram.bins }]
      }, { lazyUpdate: true, silent: true });
      if (entry && entry.panel) {
        entry.panel.status.textContent = "P05–P95 + 尾部";
        entry.panel.section.dataset.histogramRangePolicy = histogram.rangePolicy;
        entry.panel.section.dataset.histogramFiniteCount = String(histogram.finiteCount);
        entry.panel.section.dataset.histogramUnderflowCount = String(histogram.underflowCount);
        entry.panel.section.dataset.histogramOverflowCount = String(histogram.overflowCount);
        entry.panel.section.dataset.histogramInteriorMin = String(histogram.interiorMin);
        entry.panel.section.dataset.histogramInteriorMax = String(histogram.interiorMax);
        entry.panel.section.dataset.histogramObservedMin = String(histogram.observedMin);
        entry.panel.section.dataset.histogramObservedMax = String(histogram.observedMax);
      }
    });
  }

  function mappedHistoryRows(rows, meta) {
    return (rows || []).map((row) => {
      const sourceValue = finiteNumber(row.sourceFrameIndex);
      const viewerValue = finiteNumber(row.viewerFrameIndex);
      if (sourceValue === null || viewerValue === null) return null;
      const sourceFrameIndex = Math.round(sourceValue);
      const viewerFrameIndex = Math.round(viewerValue);
      const frame = meta.frames[viewerFrameIndex];
      if (
        !frame ||
        Math.round(finiteNumber(frame.sourceIndex)) !== sourceFrameIndex
      ) return null;
      return { row, frame };
    }).filter(Boolean);
  }

  function updateHistoryChart() {
    const ids = store.get().selectedBallIds;
    const panel = byId("historyPanel");
    const status = byId("historyStatus");
    if (!ids.length) {
      panel.hidden = true;
      body.dataset.historyVisible = "0";
      if (runtime.historyChart) {
        runtime.historyChart.clear();
        runtime.historyChart.__temporal = false;
        if (runtime.historyChart.__temporalCursor) {
          runtime.historyChart.__temporalCursor.hidden = true;
        }
      }
      body.dataset.historyPointCount = "0";
      body.dataset.historySourceFrameIndices = "";
      body.dataset.historyViewerFrameIndices = "";
      body.dataset.historyCycleValues = "";
      return;
    }
    panel.hidden = false;
    body.dataset.historyVisible = "1";
    if (!runtime.historyChart) {
      runtime.historyChart = echarts.init(byId("historyChart"), null, { renderer: "svg" });
      runtime.historyChart.__temporal = true;
      const cursor = document.createElement("div");
      cursor.className = "time-cursor";
      byId("historyPanel").appendChild(cursor);
      runtime.historyChart.__temporalCursor = cursor;
      runtime.historyChart.on("click", (event) => {
        const cycle = Number(event.value && event.value[0]);
        const frames = runtime.current.meta.frames;
        const index = nearestIndex(frames.map((frame) => frame.cycle), cycle);
        if (index >= 0) actions.setFrame(index, { source: "history-chart" });
      });
    }
    const secondaryMetric = store.get().colorMetric === "acceleration"
      ? "acceleration"
      : "speed";
    const secondaryLabel = secondaryMetric === "acceleration" ? "加速度" : "速度";
    const secondaryUnit = secondaryMetric === "acceleration" ? "m/s^2" : "m/s";
    status.textContent = "位移 / " + secondaryLabel + " · 力历史 NOT_CAPTURED";
    const series = [];
    const firstMappedRows = [];
    ids.slice(0, 8).forEach((ballId, index) => {
      const rows = runtime.selectedHistories.get(ballId);
      if (!rows || !rows.length) return;
      const mapped = mappedHistoryRows(rows, runtime.current.meta);
      if (!mapped.length) return;
      if (!firstMappedRows.length) firstMappedRows.push(...mapped);
      const color = chartColors()[index % chartColors().length];
      series.push({
        name: "Ball " + ballId + " 位移",
        type: "line",
        data: mapped.map((item) => [item.frame.cycle, item.row.displacement]),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { color, width: 1.25 },
        itemStyle: { color }
      });
      if (index === 0) {
        series.push({
          name: "Ball " + ballId + " " + secondaryLabel,
          type: "line",
          yAxisIndex: 1,
          data: mapped.map((item) => [
            item.frame.cycle,
            item.row[secondaryMetric]
          ]),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { color, width: 1, type: "dashed", opacity: 0.8 },
          itemStyle: { color }
        });
      }
    });
    runtime.historyChart.setOption({
      animation: false,
      title: {
        show: false,
        text: "Ball 历史",
        left: 12,
        top: 8,
        textStyle: { color: COLORS.ink, fontSize: 12, fontWeight: 600 }
      },
      textStyle: { fontFamily: "Arial, Helvetica, PingFang SC, Microsoft YaHei, sans-serif" },
      grid: { left: 50, right: 48, top: 42, bottom: 42 },
      legend: {
        top: 3, right: 8, itemWidth: 13, itemHeight: 2,
        textStyle: { color: COLORS.muted, fontSize: 8.5 }, type: "scroll"
      },
      tooltip: {
        trigger: "axis", confine: true,
        backgroundColor: COLORS.tooltipBackground, borderColor: COLORS.tooltipBorder,
        textStyle: { color: COLORS.ink, fontSize: 10 }
      },
      xAxis: axisStyle("Cycle", "cycle", null, { include_zero: false }),
      yAxis: [
        axisStyle("累计位移", "m", null, { include_zero: false }),
        axisStyle(secondaryLabel, secondaryUnit, null, { include_zero: false })
      ],
      series
    }, { notMerge: true });
    body.dataset.historyPointCount = String(firstMappedRows.length);
    body.dataset.historySourceFrameIndices = firstMappedRows
      .map((item) => Math.round(item.row.sourceFrameIndex))
      .join(",");
    body.dataset.historyViewerFrameIndices = firstMappedRows
      .map((item) => Math.round(item.row.viewerFrameIndex))
      .join(",");
    body.dataset.historyCycleValues = firstMappedRows
      .map((item) => item.frame.cycle)
      .join(",");
    runtime.historyChart.__temporal = true;
    updateTemporalMarkers();
  }

  async function loadSelectedHistories() {
    const ids = store.get().selectedBallIds;
    const caseId = store.get().currentCase;
    if (!ids.length || caseId == null) {
      runtime.selectedHistories.clear();
      updateHistoryChart();
      updateTrajectories();
      return;
    }
    const token = runtime.frameToken;
    const loaded = [];
    for (const ballId of ids.slice(0, 8)) {
      if (runtime.selectedHistories.has(ballId)) {
        loaded.push([ballId, runtime.selectedHistories.get(ballId)]);
        continue;
      }
      const bucket = await ensureHistoryBucket(caseId, ballId);
      const entry = bucket.entries.find((item) => item.id === ballId);
      if (!entry) {
        loaded.push([ballId, []]);
        continue;
      }
      const rows = mappedHistoryRows(
        decodeHistoryRows(entry.data),
        DATA.caseMeta[caseId]
      ).map((item) => item.row);
      runtime.selectedHistories.set(ballId, rows);
      loaded.push([ballId, rows]);
    }
    if (token !== runtime.frameToken || store.get().currentCase !== caseId) return;
    runtime.selectedHistories = new Map(loaded);
    updateHistoryChart();
    updateTrajectories();
  }

  async function switchCase(caseId, source) {
    const token = ++runtime.caseToken;
    runtime.frameToken += 1;
    pausePlayback();
    loading.hidden = false;
    loading.textContent = "正在读取 Case " + caseId + " 元数据…";
    try {
      const meta = await loadCaseMeta(caseId);
      const specs = await loadCaseCharts(caseId);
      if (token !== runtime.caseToken) return;
      const summary = DATA.catalog.cases.find((item) => item.id === caseId);
      const caseStatic = staticCases[String(caseId)];
      if (!caseStatic) throw new Error("Case 静态实体未注册: " + caseId);
      staticBalls = caseStatic.balls;
      staticById = new Map();
      staticBalls.forEach((ball, index) => {
        staticById.set(ball[0], { index, radius: ball[4] });
      });
      const focus = ballFocusBounds(staticBalls);
      focusCenter = focus.center;
      focusSpan = focus.span;
      runtime.current = { meta, summary, specs };
      currentFrameData = null;
      runtime.selectedHistories.clear();
      runtime.currentHistories = Object.create(null);
      syncCaseVisualCapabilities(meta);
      makeChartEntries(specs);
      buildCrackLayers(meta.cracks || []);
      updateHistoryChart();
      updateTrajectories();
      byId("timeline").min = "0";
      byId("timeline").max = String(Math.max(0, meta.frames.length - 1));
      byId("timeline").value = "0";
      byId("caseSelect").value = String(caseId);
      byId("caseSubtitle").textContent =
        meta.viewerFrameCount + " 个实测帧 · Cycle " + meta.frames[0].cycle + "–" +
        meta.frames[meta.frames.length - 1].cycle + " · 无帧间插值";
      byId("runBadge").textContent = summary.runId + " · " +
        (meta.sampled ? "显式抽样" : "完整真实帧集") + " · " + summary.frameStatus;
      store.set({
        currentCase: caseId,
        currentFrame: 0,
        currentCycle: meta.frames[0].cycle,
        currentTime: meta.frames[0].time,
        selectedBallIds: [],
        selectedRange: null,
        selectedMetric: store.get().colorMetric
      }, "case");
      body.dataset.selectedBallIds = "";
      body.dataset.selectedRange = "";
      body.dataset.selectedMetric = store.get().selectedMetric;
      updateHistoryChart();
      updateTrajectories();
      await setFrame(0, { source, force: true, fromCaseSwitch: true });
      applyViewPreset(currentViewPreset || "fit");
      body.dataset.caseId = String(caseId);
      body.dataset.caseReady = "1";
      document.title = DATA.catalog.meta.title + " · " + summary.runId;
    } catch (error) {
      showError("CASE_LOAD_ERROR", error);
    } finally {
      if (token === runtime.caseToken) {
        loading.hidden = true;
        loading.textContent = "正在加载当前实测帧…";
      }
    }
  }

  async function setFrame(index, options) {
    if (!runtime.current) return;
    const settings = options || {};
    const caseId = store.get().currentCase;
    const token = ++runtime.frameToken;
    const meta = runtime.current.meta;
    const target = Math.max(0, Math.min(meta.frames.length - 1, Number(index)));
    if (!settings.force && target === store.get().currentFrame) return;
    const frameMeta = meta.frames[target];
    loading.hidden = false;
    loading.textContent = "正在加载实测帧 " + (target + 1) + " / " + meta.frames.length + "…";
    try {
      const chunk = await ensureChunk(caseId, frameMeta.chunk);
      if (token !== runtime.frameToken || store.get().currentCase !== caseId) return;
      const frame = chunk.frames[frameMeta.chunkOffset];
      if (!frame) throw new Error("帧块中缺少目标帧");
      currentFrameData = frame;
      updateParticles(frame, highlightIdsForState());
      const now = performance.now();
      if (!runtime.playing || now - runtime.lastHistogramUpdate >= 500) {
        runtime.lastHistogramUpdate = now;
        updateCurrentHistograms(frame);
      }
      updateCracks(frame.cycle);
      store.set({
        currentFrame: target,
        currentCycle: frame.cycle,
        currentTime: frame.time
      }, settings.source || "frame");
      const nextMeta = meta.frames[target + 1];
      if (nextMeta && nextMeta.chunk !== frameMeta.chunk) ensureChunk(caseId, nextMeta.chunk).catch(() => {});
      body.dataset.ready = "1";
      body.dataset.frameIndex = String(target);
      body.dataset.cycle = String(frame.cycle);
      body.dataset.chunkIndex = String(frameMeta.chunk);
      body.dataset.loadedChunkCount = String(caseRuntime(caseId).chunkCache.size);
    } catch (error) {
      showError("FRAME_LOAD_ERROR", error);
    } finally {
      if (token === runtime.frameToken) loading.hidden = true;
    }
  }

  const actions = {
    setCase(caseId, options) {
      const numeric = Number(caseId);
      if (Number.isFinite(numeric)) switchCase(numeric, (options && options.source) || "case-select");
    },
    setFrame(index, options) {
      return setFrame(index, options);
    },
    async selectBalls(ids, options) {
      const settings = options || {};
      const state = store.get();
      const current = settings.additive ? new Set(state.selectedBallIds) : new Set();
      ids.forEach((id) => {
        const numeric = Number(id);
        if (!Number.isFinite(numeric)) return;
        if (settings.additive && current.has(numeric)) current.delete(numeric);
        else current.add(numeric);
      });
      store.set({
        selectedBallIds: Array.from(current),
        selectedRange: null,
        selectedMetric: settings.metric || state.selectedMetric
      }, settings.source || "ball-selection");
      if (settings.focus && ids.length) focusBall(Number(ids[0]));
      if (ids.length) {
        byId("ballInput").value = String(ids[0]);
        if (!currentFrameData || !decodeU32(currentFrameData.ids).includes(Number(ids[0]))) {
          const meta = runtime.current.meta;
          for (const frame of meta.frames) {
            const chunk = await ensureChunk(store.get().currentCase, frame.chunk);
            const data = chunk.frames[frame.chunkOffset];
            if (decodeU32(data.ids).includes(Number(ids[0]))) {
              await setFrame(frame.index, { source: "select-ball" });
              break;
            }
          }
        }
      }
      await loadSelectedHistories();
    },
    async setRange(range, metric, options) {
      if (!Array.isArray(range) || range.length !== 2 || !Number.isFinite(Number(range[0])) || !Number.isFinite(Number(range[1]))) return;
      const lo = Math.min(Number(range[0]), Number(range[1]));
      const hi = Math.max(Number(range[0]), Number(range[1]));
      store.set({
        selectedRange: [lo, hi],
        selectedMetric: metric || store.get().selectedMetric,
        colorMetric: metric || store.get().colorMetric
      }, (options && options.source) || "range");
      const histogram = runtime.currentCharts[metric] && runtime.currentCharts[metric].__histogram;
      if (histogram) {
        const startIndex = Math.max(0, histogram.edges.findIndex((edge, index) =>
          index < histogram.edges.length - 1 && hi >= edge && lo <= histogram.edges[index + 1]
        ));
        const endIndex = Math.max(startIndex, histogram.edges.findIndex((edge) => edge >= hi));
        const xStart = histogram.centers[startIndex];
        const xEnd = histogram.centers[Math.max(startIndex, endIndex - 1)];
        Object.values(runtime.currentCharts).forEach((chart) => {
          if (chart) chart.setOption({ series: [{ markArea: { data: [] } }] }, { lazyUpdate: true, silent: true });
        });
        runtime.currentCharts[metric].setOption({
          series: [{ markArea: { silent: true, itemStyle: { color: "rgba(243,155,127,0.16)" }, data: [[{ xAxis: xStart }, { xAxis: xEnd }]] } }]
        }, { lazyUpdate: true, silent: true });
      }
    },
    clearSelection() {
      store.set({
        selectedBallIds: [],
        selectedRange: null
      }, "clear-selection");
      runtime.selectedHistories.clear();
      updateHistoryChart();
      updateTrajectories();
      Object.values(runtime.currentCharts).forEach((chart) => {
        if (chart) chart.setOption({ series: [{ markArea: { data: [] } }] }, { lazyUpdate: true, silent: true });
      });
    },
    setColorMetric(metric) {
      if (!["displacement", "speed", "acceleration", "contactForce"].includes(metric)) return false;
      if (runtime.current && runtime.current.meta.metricStatus[metric] !== "SUPPORTED") {
        body.dataset.metricRejected = metric + ":NOT_CAPTURED";
        return false;
      }
      store.set({ colorMetric: metric }, "color-metric");
      return true;
    }
  };

  function renderState(state, previous, reason) {
    if (!runtime.ready) return;
    const meta = runtime.current && runtime.current.meta;
    if (!meta) return;
    const frameMeta = meta.frames[state.currentFrame];
    if (!frameMeta) return;
    byId("timeline").value = String(state.currentFrame);
    byId("frameLabel").textContent = "实测帧 " + (state.currentFrame + 1) + " / " + meta.frames.length;
    byId("cycleLabel").textContent = "Cycle " + state.currentCycle + " · t=" + formatNumber(state.currentTime, 6) + " s";
    byId("cycleInput").value = String(state.currentCycle);
    byId("metricStress").textContent = formatMetric(frameMeta.stressMPa, "MPa", 3);
    byId("metricStrain").textContent = formatMetric(frameMeta.strain, "", 5);
    byId("metricLoad").textContent = frameMeta.loadN == null ? "未采集" : formatMetric(frameMeta.loadN / 1e6, "MN", 3);
    byId("metricShortening").textContent = formatMetric(frameMeta.shorteningM, "m", 5);
    byId("metricBalls").textContent = String(frameMeta.ballCount);
    byId("metricCracks").textContent = meta.crackStatus === "NOT_CAPTURED" ? "未采集" :
      meta.crackStatus === "INVALID_GEOMETRY" ? "几何无效" : String(
        meta.cracks.filter((row) => row[6] <= state.currentCycle).length
      );
    byId("rampLabel").textContent = state.colorMetric === "speed"
      ? "速度"
      : (state.colorMetric === "acceleration"
        ? "加速度"
        : (state.colorMetric === "contactForce" ? "接触力" : "累计位移"));
    if (runtime.colorRange) {
      byId("rampRange").textContent = " P05–P95 " +
        formatNumber(runtime.colorRange.low, 3) + "–" +
        formatNumber(runtime.colorRange.high, 3) +
        (state.colorMetric === "speed"
          ? " m/s"
          : (state.colorMetric === "acceleration"
            ? " m/s²"
            : (state.colorMetric === "contactForce" ? " N" : " m")));
    }
    if (previous.currentCase !== state.currentCase || previous.colorMetric !== state.colorMetric ||
        previous.selectedBallIds !== state.selectedBallIds || previous.selectedRange !== state.selectedRange) {
      updateSelectionVisuals();
    }
    if (previous.currentFrame !== state.currentFrame || reason === "frame") {
      updateTemporalMarkers();
    }
    renderSummaryTable(state, meta, frameMeta);
    body.dataset.selectedBallIds = state.selectedBallIds.join(",");
    body.dataset.selectedRange = state.selectedRange ? state.selectedRange.join(",") : "";
    body.dataset.selectedMetric = state.selectedMetric;
    body.dataset.historyVisible = byId("historyPanel").hidden ? "0" : "1";
  }

  function renderSummaryTable(state, meta, frameMeta) {
    const target = byId("summaryBody");
    if (!target) return;
    const summary = runtime.current && runtime.current.summary ? runtime.current.summary : {};
    const missing = "未采集";
    const stress = frameMeta.stressMPa == null ? missing : formatNumber(frameMeta.stressMPa, 3) + " MPa";
    const balls = frameMeta.ballCount == null ? missing : String(frameMeta.ballCount);
    const cracks = meta.crackStatus === "NOT_CAPTURED" ? missing : String(
      meta.cracks ? meta.cracks.filter((row) => row[6] <= state.currentCycle).length
        : (meta.fractureEvents || 0)
    );
    const force = summary.maxContactForce == null || !Number.isFinite(summary.maxContactForce)
      ? missing : formatNumber(summary.maxContactForce, 3) + " N";
    const runTime = state.currentTime == null ? missing : formatNumber(state.currentTime, 3) + " s";
    const rows = [
      ["轴向应力", stress], ["当前颗粒数", balls], ["累计裂纹", cracks],
      ["最大接触力", force], ["机械时间", runTime]
    ];
    target.innerHTML = rows.map(([label, value]) =>
      "<tr><td>" + escapeHtml(label) + "</td><td>" + escapeHtml(String(value)) + "</td></tr>"
    ).join("");
  }

  store.subscribe((state, previous, reason) => {
    pendingState = state;
    pendingReason = reason;
    if (stateRenderQueued) return;
    stateRenderQueued = true;
    requestAnimationFrame(() => {
      stateRenderQueued = false;
      const next = pendingState;
      const before = lastRenderedState || previous;
      lastRenderedState = next;
      renderState(next, before, pendingReason);
    });
  });

  function pausePlayback() {
    runtime.playing = false;
    runtime.playAccumulator = 0;
    byId("playButton").textContent = "▶ 播放";
    if (currentFrameData) updateCurrentHistograms(currentFrameData);
    updateTemporalMarkers();
  }

  function togglePlayback() {
    if (!runtime.current) return;
    const state = store.get();
    if (!runtime.playing && state.currentFrame >= runtime.current.meta.frames.length - 1) {
      actions.setFrame(0, { source: "play-reset" });
    }
    runtime.playing = !runtime.playing;
    runtime.playAccumulator = 0;
    byId("playButton").textContent = runtime.playing ? "⏸ 暂停" : "▶ 播放";
  }

  function resetCamera() {
    applyViewPreset(currentViewPreset || "fit");
  }

  function setCameraMode(mode) {
    if (!camera) return;
    const chosen = mode === "orthographic" ? orthographicCamera :
      mode === "perspective" ? perspectiveCamera : (is2D ? orthographicCamera : perspectiveCamera);
    if (chosen !== camera) {
      controls.dispose();
      camera = chosen;
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
    }
    resetCamera();
    body.dataset.cameraMode = chosen === orthographicCamera ? "orthographic" : "perspective";
  }

  function applyViewPreset(preset) {
    if (!camera) return;
    currentViewPreset = preset || "fit";
    const direction = {
      fit: is2D ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1.18, -1.48, 0.72),
      isometric: new THREE.Vector3(1, -1, 0.72),
      front: new THREE.Vector3(0, -1, 0),
      top: new THREE.Vector3(0, 0, 1),
      side: new THREE.Vector3(1, 0, 0)
    }[currentViewPreset] || (is2D ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1.18, -1.48, 0.72));
    direction.normalize();
    const target = focusCenter || center;
    const framedSpan = Math.max(focusSpan || span, 1.0e-9);
    // Compensate for narrow/portrait stages: the horizontal FOV is the
    // limiting one there, so the fit sphere must be enlarged accordingly.
    const framingAspect = Math.max(camera.aspect || 1, 0.1);
    const framingRadius = framedSpan * Math.sqrt(3) * 0.56 * Math.max(1, 1 / framingAspect);
    controls.target.copy(target);
    if (camera === perspectiveCamera) {
      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const horizontalFov = 2 * Math.atan(
        Math.tan(verticalFov * 0.5) * Math.max(camera.aspect || 1, 0.1)
      );
      const limitingHalfFov = Math.min(verticalFov, horizontalFov) * 0.5;
      const distance = framingRadius / Math.max(Math.sin(limitingHalfFov), 1.0e-6);
      camera.position.copy(target).add(direction.multiplyScalar(distance));
      camera.near = framedSpan * 0.001;
      camera.far = framedSpan * 100;
    } else {
      orthoExtent = framingRadius;
      camera.position.copy(target).add(direction.multiplyScalar(framedSpan * 2.2));
      camera.near = framedSpan * 0.001;
      camera.far = framedSpan * 100;
      camera.zoom = 1;
    }
    camera.up.set(0, 0, 1);
    if (currentViewPreset === "top" || (currentViewPreset === "fit" && is2D)) camera.up.set(0, 1, 0);
    camera.lookAt(target);
    camera.updateProjectionMatrix();
    controls.update();
    body.dataset.viewPreset = currentViewPreset;
    body.dataset.focusSpan = String(framedSpan);
  }

  function updateClipping() {
    if (!camera) return;
    const axis = byId("clipAxis").value;
    const index = { x: 0, y: 1, z: 2 }[axis] || 2;
    const low = [dmin.x, dmin.y, dmin.z][index];
    const high = [dmax.x, dmax.y, dmax.z][index];
    const cut = low + (high - low) * (Number(byId("clipPosition").value) / 100);
    const normal = new THREE.Vector3(0, 0, 0);
    normal.setComponent(index, -1);
    clippingPlane.normal.copy(normal);
    clippingPlane.constant = cut;
    const planes = byId("showClip").checked ? [clippingPlane] : [];
    particleMaterial.clippingPlanes = planes;
    particleMaterial.needsUpdate = true;
    [wallFaces, wallEdgeLines, crackTension, crackShear, contactLines, bondLines].forEach((line) => {
      if (!line) return;
      line.material.clippingPlanes = planes;
      line.material.needsUpdate = true;
    });
    body.dataset.clipping = byId("showClip").checked ? "ENABLED" : "DISABLED";
  }

  function niceDistance(value) {
    if (!Number.isFinite(value) || value <= 0) return 1;
    const power = Math.pow(10, Math.floor(Math.log10(value)));
    const unit = value / power;
    return (unit >= 5 ? 5 : unit >= 2 ? 2 : 1) * power;
  }

  function updateScaleBar() {
    if (!camera || !renderer) return;
    const height = Math.max(1, byId("stage").clientHeight);
    let worldPerPixel;
    if (camera === orthographicCamera) {
      worldPerPixel = (camera.top - camera.bottom) / (height * camera.zoom);
    } else {
      const distance = camera.position.distanceTo(controls.target);
      worldPerPixel = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5)) / height;
    }
    const length = niceDistance(worldPerPixel * 110);
    const pixels = Math.max(28, Math.min(180, length / Math.max(worldPerPixel, 1e-12)));
    byId("scaleLine").style.width = pixels.toFixed(1) + "px";
    byId("scaleText").textContent = formatNumber(length, 3) + " m";
  }

  function downloadDataUrl(name, dataUrl) {
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function renderSceneAt(width, background) {
    const stageWidth = Math.max(1, byId("stage").clientWidth);
    const stageHeight = Math.max(1, byId("stage").clientHeight);
    const targetWidth = Math.max(800, Math.min(12000, Number(width) || 3200));
    const targetHeight = Math.max(1, Math.round(targetWidth * stageHeight / stageWidth));
    const priorBackground = scene.background;
    const priorRatio = renderer.getPixelRatio();
    scene.background = background === "transparent" ? null : new THREE.Color(0xffffff);
    renderer.setPixelRatio(1);
    renderer.setSize(targetWidth, targetHeight, false);
    camera.aspect = targetWidth / targetHeight;
    if (camera === orthographicCamera) {
      const aspect = camera.aspect;
      const halfHeight = orthoExtent;
      const halfWidth = halfHeight * aspect;
      camera.left = -halfWidth;
      camera.right = halfWidth;
      camera.top = halfHeight;
      camera.bottom = -halfHeight;
    }
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    const dataUrl = renderer.domElement.toDataURL("image/png");
    scene.background = priorBackground;
    renderer.setPixelRatio(priorRatio);
    resize();
    renderer.render(scene, camera);
    return dataUrl;
  }

  function loadImage(dataUrl) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("无法读取 Three.js 场景导出图像"));
      image.src = dataUrl;
    });
  }

  function currentMetricExportContract() {
    const state = store.get();
    const labels = {
      displacement: { label: "累计位移", unit: "m" },
      speed: { label: "速度", unit: "m/s" },
      acceleration: { label: "加速度", unit: "m/s²" }
    };
    const metric = labels[state.colorMetric] || labels.displacement;
    return {
      key: state.colorMetric,
      label: metric.label,
      unit: metric.unit,
      range: runtime.colorRange
        ? { ...runtime.colorRange }
        : null
    };
  }

  function setFittedText(context, text, x, y, maxWidth, align = "left") {
    const value = String(text || "");
    let size = Number.parseFloat(context.font.match(/(\d+(?:\.\d+)?)px/)?.[1] || "20");
    while (size > 10 && context.measureText(value).width > maxWidth) {
      size -= 1;
      context.font = context.font.replace(/(\d+(?:\.\d+)?)px/, size + "px");
    }
    context.textAlign = align;
    context.fillText(value, x, y);
    context.textAlign = "left";
  }

  async function scenePublicationDataUrl(width, background) {
    const targetWidth = Math.max(800, Math.min(12000, Number(width) || 3200));
    const scale = targetWidth / 3200;
    const margin = Math.max(28, Math.round(72 * scale));
    const sceneDataUrl = renderSceneAt(targetWidth, background);
    const sceneImage = await loadImage(sceneDataUrl);
    const state = store.get();
    const meta = runtime.current.meta;
    const frameMeta = meta.frames[state.currentFrame];
    const metric = currentMetricExportContract();
    const title = byId("viewerTitle").textContent || DATA.catalog.meta.title;
    const probeContext = document.createElement("canvas").getContext("2d");
    probeContext.font = `700 ${Math.round(42 * scale)}px Arial, Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif`;
    const titleLines = wrapCanvasText(
      probeContext,
      title,
      targetWidth - margin * 2,
      3
    );
    const titleLineHeight = Math.round(48 * scale);
    const headerHeight = Math.round(
      margin * 0.65 + 42 * scale + titleLines.length * titleLineHeight +
      58 * scale + margin * 0.55
    );
    const footerHeight = Math.round(margin * 0.65 + 156 * scale + margin * 0.55);
    const outputHeight = Math.round(
      headerHeight + sceneImage.height + footerHeight
    );
    const canvas = document.createElement("canvas");
    canvas.width = targetWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext("2d");
    const paper = "#ffffff";
    const ink = "#171717";
    const muted = "#6f7074";
    const primary = COLORS.primary || "#3C5488";
    if (background !== "transparent") {
      context.fillStyle = paper;
      context.fillRect(0, 0, canvas.width, canvas.height);
    }

    context.fillStyle = background === "transparent"
      ? "rgba(255,255,255,0.96)"
      : paper;
    context.fillRect(0, 0, targetWidth, headerHeight);
    context.fillStyle = ink;
    context.font = `700 ${Math.round(42 * scale)}px Arial, Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif`;
    titleLines.forEach((line, index) => {
      context.fillText(line, margin, margin + 42 * scale + index * titleLineHeight);
    });
    const titleBottom = margin + 42 * scale + (titleLines.length - 1) * titleLineHeight;
    context.fillStyle = muted;
    context.font = `400 ${Math.round(20 * scale)}px Arial, Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif`;
    const caseText = meta.label + " · " + meta.runId;
    setFittedText(
      context,
      "Case: " + caseText,
      margin,
      titleBottom + 36 * scale,
      targetWidth - margin * 2 - 280 * scale
    );
    context.fillStyle = primary;
    context.font = `600 ${Math.round(20 * scale)}px Arial, Helvetica, sans-serif`;
    context.textAlign = "right";
    context.fillText(
      "PFC " + meta.dimension + "D · " +
      String(DATA.catalog.meta.dataBoundary || "UNKNOWN"),
      targetWidth - margin,
      titleBottom + 36 * scale
    );
    context.textAlign = "left";
    context.strokeStyle = "#e5e9ee";
    context.lineWidth = Math.max(1, Math.round(scale));
    context.beginPath();
    context.moveTo(0, headerHeight - 1);
    context.lineTo(targetWidth, headerHeight - 1);
    context.stroke();

    context.drawImage(sceneImage, 0, headerHeight, targetWidth, sceneImage.height);

    const footerY = headerHeight + sceneImage.height;
    context.fillStyle = background === "transparent"
      ? "rgba(255,255,255,0.96)"
      : paper;
    context.fillRect(0, footerY, targetWidth, footerHeight);
    context.strokeStyle = "#e5e9ee";
    context.beginPath();
    context.moveTo(0, footerY + 0.5);
    context.lineTo(targetWidth, footerY + 0.5);
    context.stroke();

    const footerTop = footerY + margin * 0.55;
    const rampWidth = Math.min(Math.round(860 * scale), targetWidth * 0.34);
    const rampHeight = Math.max(20, Math.round(24 * scale));
    const rampX = margin;
    context.fillStyle = ink;
    context.font = `600 ${Math.round(20 * scale)}px Arial, Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif`;
    context.fillText(
      metric.label + " [" + metric.unit + "]",
      rampX,
      footerTop + 18 * scale
    );
    const gradient = context.createLinearGradient(rampX, 0, rampX + rampWidth, 0);
    if (Array.isArray(COLORS.ramp) && COLORS.ramp.length >= 2) {
      COLORS.ramp.forEach((stop) => {
        gradient.addColorStop(
          Math.max(0, Math.min(1, Number(stop.at) || 0)),
          stop.color
        );
      });
    } else {
      gradient.addColorStop(0, COLORS.low || "#EAEEF5");
      gradient.addColorStop(1, COLORS.high || "#3C5488");
    }
    context.fillStyle = gradient;
    context.fillRect(
      rampX,
      footerTop + 31 * scale,
      rampWidth,
      rampHeight
    );
    context.strokeStyle = "#cfd6df";
    context.strokeRect(
      rampX + 0.5,
      footerTop + 31 * scale + 0.5,
      rampWidth - 1,
      rampHeight - 1
    );
    context.fillStyle = muted;
    context.font = `400 ${Math.round(17 * scale)}px Arial, Helvetica, sans-serif`;
    const range = metric.range;
    const lowText = range ? formatNumber(range.low, 6) : "N/A";
    const highText = range ? formatNumber(range.high, 6) : "N/A";
    context.fillText(lowText, rampX, footerTop + 78 * scale);
    context.textAlign = "right";
    context.fillText(highText, rampX + rampWidth, footerTop + 78 * scale);
    context.textAlign = "left";
    context.fillText(
      range ? "真实帧 P05–P95 · 区间外颜色饱和" : "当前帧无有限颗粒值",
      rampX,
      footerTop + 104 * scale
    );

    const infoX = rampX + rampWidth + margin;
    const infoWidth = Math.max(280 * scale, targetWidth - infoX - margin);
    context.fillStyle = ink;
    context.font = `600 ${Math.round(19 * scale)}px Arial, Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif`;
    const infoLines = [
      "Frame " + (state.currentFrame + 1) + " / " + meta.frames.length +
        " · source " + frameMeta.sourceIndex,
      "Cycle " + state.currentCycle + " · t=" +
        formatNumber(state.currentTime, 8) + " s",
      "Balls " + frameMeta.ballCount +
        " · selected " + state.selectedBallIds.length
    ];
    infoLines.forEach((line, index) => {
      setFittedText(
        context,
        line,
        infoX,
        footerTop + (17 + index * 28) * scale,
        infoWidth
      );
    });
    context.fillStyle = muted;
    context.font = `400 ${Math.round(16 * scale)}px Arial, Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif`;
    const annotations = [];
    if (meta.crackStatus === "SUPPORTED") {
      annotations.push("蓝线：拉伸裂纹", "红线：剪切裂纹");
    }
    annotations.push("缺失值不进入颜色映射");
    annotations.push("真实坐标与半径 · 无帧间插值");
    annotations.forEach((line, index) => {
      context.fillText(
        line,
        infoX,
        footerTop + (112 + index * 21) * scale
      );
    });

    const scaleText = byId("scaleText").textContent || "— m";
    const displayedScalePixels = Number.parseFloat(byId("scaleLine").style.width);
    const sourceStageWidth = Math.max(1, byId("stage").clientWidth);
    const exportScalePixels = Number.isFinite(displayedScalePixels)
      ? displayedScalePixels * targetWidth / sourceStageWidth
      : 120 * scale;
    const scaleX = targetWidth - margin - Math.max(80 * scale, exportScalePixels);
    const scaleY = footerTop + 104 * scale;
    context.strokeStyle = ink;
    context.lineWidth = Math.max(2, Math.round(2 * scale));
    context.beginPath();
    context.moveTo(scaleX, scaleY);
    context.lineTo(scaleX + exportScalePixels, scaleY);
    context.lineTo(scaleX + exportScalePixels, scaleY - 8 * scale);
    context.moveTo(scaleX, scaleY);
    context.lineTo(scaleX, scaleY - 8 * scale);
    context.stroke();
    context.fillStyle = ink;
    context.font = `600 ${Math.round(16 * scale)}px Arial, Helvetica, sans-serif`;
    context.textAlign = "center";
    context.fillText(scaleText, scaleX + exportScalePixels * 0.5, scaleY - 14 * scale);
    context.textAlign = "left";

    body.dataset.sceneExportWidth = String(canvas.width);
    body.dataset.sceneExportHeight = String(canvas.height);
    body.dataset.sceneExportMetric = metric.key;
    body.dataset.sceneExportUnit = metric.unit;
    body.dataset.sceneExportIncludesMetadata = "true";
    body.dataset.sceneExportFormat = "PNG";
    return canvas.toDataURL("image/png");
  }

  async function exportScene() {
    if (!runtime.current) return;
    const frame = store.get().currentFrame;
    const dataUrl = await scenePublicationDataUrl(
      byId("exportWidth").value,
      byId("exportBackground").value
    );
    downloadDataUrl("pfc_case_" + store.get().currentCase + "_frame_" + frame + ".png", dataUrl);
    body.dataset.sceneExportStatus = "GENERATED";
    return dataUrl;
  }

  async function exportFrame() {
    const raw = window.prompt("输入要导出的实测帧号（从 1 开始）", String(store.get().currentFrame + 1));
    if (raw == null) return;
    const target = Number(raw) - 1;
    if (!Number.isFinite(target)) return;
    await setFrame(target, { source: "export-frame", force: true });
    await exportScene();
    body.dataset.frameExportStatus = "GENERATED";
  }

  function exportChartSVGs() {
    const caseId = store.get().currentCase;
    const jobs = [];
    runtime.charts.forEach((entry, index) => {
      const chartNumber = index + 1;
      const fileName = "pfc_case_" + caseId + "_chart_" +
        String(chartNumber).padStart(2, "0") + ".svg";
      jobs.push(new Promise((resolve) => setTimeout(() => {
        const dataUrl = chartSVGDataUrl(entry, true);
        downloadDataUrl(fileName, dataUrl);
        resolve(fileName);
      }, index * 120)));
    });
    if (runtime.historyChart && !byId("historyPanel").hidden) {
      const fileName = "pfc_case_" + caseId + "_ball_history.svg";
      jobs.push(new Promise((resolve) => setTimeout(() => {
        const dataUrl = echartSVGDataUrl(
          runtime.historyChart,
          "Ball 历史",
          {
            id: "viewer:ball_history:" + caseId,
            caseId
          }
        );
        downloadDataUrl(fileName, dataUrl);
        resolve(fileName);
      }, jobs.length * 120)));
    }
    body.dataset.chartExportStatus = "SCHEDULED";
    return Promise.all(jobs).then((names) => {
      body.dataset.chartExportNames = names.join("|");
      body.dataset.chartExportStatus = "GENERATED";
      return names;
    });
  }

  function chartExportEntries() {
    const caseId = store.get().currentCase;
    return runtime.charts.map((entry, index) => ({
      id: (entry.spec && entry.spec.id) ||
        "viewer:current_frame:" + caseId + ":" +
          ((entry.metric || entry.panel.title.textContent || String(index + 1))),
      caseId,
      fileName: "pfc_case_" + caseId + "_chart_" +
        String(index + 1).padStart(2, "0") + ".svg",
      title: (entry.spec && entry.spec.title) ||
        (entry.panel && entry.panel.title && entry.panel.title.textContent) || ""
    }));
  }

  function wrapSvgTitle(title, maxCharacters = 44) {
    const text = String(title || "").trim();
    if (!text) return [];
    const lines = [];
    let remaining = text;
    while (remaining && lines.length < 3) {
      if (remaining.length <= maxCharacters || lines.length === 2) {
        lines.push(remaining);
        break;
      }
      let split = Math.max(
        remaining.lastIndexOf(" ", maxCharacters),
        remaining.lastIndexOf("–", maxCharacters),
        remaining.lastIndexOf("-", maxCharacters),
        remaining.lastIndexOf("，", maxCharacters)
      );
      if (split <= 0) split = maxCharacters;
      lines.push(remaining.slice(0, split).trim());
      remaining = remaining.slice(split).trim().replace(/^[–\-，]+/, "");
    }
    return lines;
  }

  function echartSVGDataUrl(chart, title, identity) {
    const dataUrl = chart.getDataURL({
      type: "svg",
      backgroundColor: COLORS.exportBackground,
      excludeComponents: ["toolbox", "brush"]
    });
    if (!title) return dataUrl;
    const comma = dataUrl.indexOf(",");
    if (comma < 0) return dataUrl;
    const header = dataUrl.slice(0, comma + 1);
    const svg = decodeURIComponent(dataUrl.slice(comma + 1));
    const titleLines = wrapSvgTitle(title);
    const titleMarkup = '<g data-pfc-embedded-title="1">' + titleLines.map((line, index) => (
      '<text x="12" y="' + (24 + index * 16) +
      '" fill="#171717" style="font:600 12px Arial, Helvetica, PingFang SC, Microsoft YaHei, sans-serif;">' +
      escapeHtml(line) + "</text>"
    )).join("") + "</g>";
    const attributes = [
      identity && identity.id
        ? ' data-pfc-chart-id="' + escapeHtml(identity.id) + '"'
        : "",
      identity && identity.caseId != null
        ? ' data-pfc-case-id="' + escapeHtml(identity.caseId) + '"'
        : "",
      title
        ? ' data-pfc-title="' + escapeHtml(title) + '"'
        : ""
    ].join("");
    const titledSvg = svg.replace(
      /(<svg\b[^>]*>)/,
      (openingTag) => (
        openingTag.replace(/>$/, attributes + ">") + titleMarkup
      )
    );
    return header + encodeURIComponent(titledSvg);
  }

  function chartSVGDataUrl(entry, includeTitle) {
    const title = includeTitle && entry
      ? (
        (entry.spec && entry.spec.title) ||
        (entry.panel && entry.panel.title && entry.panel.title.textContent) ||
        ""
      )
      : "";
    const caseId = store.get().currentCase;
    return echartSVGDataUrl(entry.chart, title, {
      id: (entry.spec && entry.spec.id) ||
        "viewer:current_frame:" + caseId + ":" +
          ((entry.metric || entry.panel.title.textContent || "chart")),
      caseId
    });
  }

  function compositeLayout(count, aspectRatio = 1.5) {
    if (count <= 0) return { template: "empty", panels: [] };
    let rows;
    let template;
    if (count === 1) {
      rows = [[1]];
      template = "single";
    } else if (count === 2) {
      rows = [[1, 1]];
      template = "two_columns";
    } else if (count === 3) {
      rows = [[1], [1, 1]];
      template = "featured_plus_two";
    } else if (count === 4) {
      rows = [[1, 1], [1, 1]];
      template = "two_by_two";
    } else if (count === 5) {
      rows = [[1], [1, 1], [1, 1]];
      template = "featured_plus_four";
    } else if (count === 6) {
      rows = [[1, 1], [1, 1], [1, 1]];
      template = "two_by_three";
    } else if (count === 7) {
      rows = [[1], [1, 1, 1], [1, 1, 1]];
      template = "featured_plus_six";
    } else if (count === 8) {
      rows = [[1, 1], [1, 1], [1, 1], [1, 1]];
      template = "two_by_four";
    } else {
      const featured = count % 2 === 1;
      const remaining = featured ? count - 1 : count;
      const columns = Math.max(2, Math.min(5, Math.round(Math.sqrt(remaining * aspectRatio))));
      rows = [];
      if (featured) rows.push([1]);
      let left = remaining;
      while (left > 0) {
        const take = Math.min(columns, left);
        rows.push(new Array(take).fill(1));
        left -= take;
      }
      template = featured ? "featured_balanced_grid" : "balanced_grid";
    }
    const heightWeights = rows.map((row, index) => (
      template.startsWith("featured") && index === 0 ? 1.2 : 1
    ));
    const totalHeight = heightWeights.reduce((sum, value) => sum + value, 0);
    const panels = [];
    let y = 0;
    let index = 0;
    rows.forEach((row, rowIndex) => {
      const rowHeight = heightWeights[rowIndex] / totalHeight;
      let x = 0;
      row.forEach((weight) => {
        const width = weight / row.reduce((sum, value) => sum + value, 0);
        panels.push({
          index,
          x,
          y,
          width,
          height: rowHeight,
          role: template.startsWith("featured") && rowIndex === 0 ? "primary" : "supporting"
        });
        x += width;
        index += 1;
      });
      y += rowHeight;
    });
    return { template, panels };
  }

  function panelLetter(index) {
    let value = Number(index) + 1;
    let output = "";
    while (value > 0) {
      value -= 1;
      output = String.fromCharCode(97 + (value % 26)) + output;
      value = Math.floor(value / 26);
    }
    return output;
  }

  function wrapCanvasText(context, text, maxWidth, maxLines = 2) {
    const value = String(text || "").trim();
    if (!value) return [""];
    const lines = [];
    let remaining = value;
    while (remaining && lines.length < maxLines) {
      if (context.measureText(remaining).width <= maxWidth) {
        lines.push(remaining);
        remaining = "";
        break;
      }
      let count = remaining.length;
      while (count > 1 && context.measureText(remaining.slice(0, count)).width > maxWidth) {
        count -= 1;
      }
      if (lines.length === maxLines - 1 && count < remaining.length) {
        let shortened = remaining.slice(0, Math.max(1, count - 1));
        while (shortened.length > 1 && context.measureText(shortened + "…").width > maxWidth) {
          shortened = shortened.slice(0, -1);
        }
        lines.push(shortened + "…");
        remaining = "";
        break;
      }
      lines.push(remaining.slice(0, count).trim());
      remaining = remaining.slice(count).trim();
    }
    return lines;
  }

  async function compositePanelsDataUrl() {
    const entries = runtime.charts.filter((entry) => !entry.linkedHistogram);
    if (!entries.length) return null;
    const width = 3600;
    const height = 2400;
    const margin = 56;
    const gap = 24;
    const layout = compositeLayout(entries.length, width / height);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    const images = await Promise.all(entries.map((entry) => new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = entry.chart.getDataURL({ type: "svg", backgroundColor: COLORS.exportBackground, excludeComponents: ["toolbox", "brush"] });
    })));
    images.forEach((image, index) => {
      const panel = layout.panels[index];
      const x = margin + panel.x * (width - margin * 2) + gap * 0.5;
      const y = margin + panel.y * (height - margin * 2) + gap * 0.5;
      const cellWidth = panel.width * (width - margin * 2) - gap;
      const cellHeight = panel.height * (height - margin * 2) - gap;
      const entry = entries[index];
      context.font = "600 21px Arial, Helvetica, sans-serif";
      const titleWidth = Math.max(120, cellWidth - 360);
      const titleLines = wrapCanvasText(
        context,
        entry.panel.title.textContent,
        titleWidth,
        2
      );
      const headerHeight = 64 + Math.max(0, titleLines.length - 1) * 22;
      context.fillStyle = "#ffffff";
      context.fillRect(x, y, cellWidth, cellHeight);
      context.strokeStyle = "#e5e9ee";
      context.lineWidth = 1;
      context.strokeRect(x, y, cellWidth, cellHeight);
      context.fillStyle = "#171717";
      context.font = "700 25px Arial, Helvetica, sans-serif";
      context.fillText("(" + panelLetter(index) + ")", x + 16, y + 38);
      context.font = "600 21px Arial, Helvetica, sans-serif";
      titleLines.forEach((line, lineIndex) => {
        context.fillText(line, x + 66, y + 37 + lineIndex * 22);
      });
      context.fillStyle = "#6f7074";
      context.font = "13px Arial, Helvetica, sans-serif";
      const status = entry.panel.status.textContent || "";
      context.fillText(status, x + cellWidth - context.measureText(status).width - 16, y + 35);
      context.strokeStyle = "#e5e9ee";
      context.beginPath();
      context.moveTo(x, y + headerHeight);
      context.lineTo(x + cellWidth, y + headerHeight);
      context.stroke();
      const graphicX = x + 8;
      const graphicY = y + headerHeight + 4;
      const graphicWidth = cellWidth - 16;
      const graphicHeight = cellHeight - headerHeight - 12;
      const sourceRatio = image.width / Math.max(1, image.height);
      const targetRatio = graphicWidth / Math.max(1, graphicHeight);
      let drawWidth = graphicWidth;
      let drawHeight = graphicHeight;
      if (sourceRatio > targetRatio) drawHeight = graphicWidth / sourceRatio;
      else drawWidth = graphicHeight * sourceRatio;
      context.drawImage(
        image,
        graphicX + (graphicWidth - drawWidth) * 0.5,
        graphicY + (graphicHeight - drawHeight) * 0.5,
        drawWidth,
        drawHeight
      );
    });
    return canvas.toDataURL("image/png");
  }

  async function exportCompositePanels() {
    const dataUrl = await compositePanelsDataUrl();
    if (!dataUrl) return;
    downloadDataUrl("pfc_case_" + store.get().currentCase + "_composite_panels.png", dataUrl);
    body.dataset.compositeExportStatus = "GENERATED";
  }

  function chartSVGDataUrls() {
    return runtime.charts
      .filter((entry) => !entry.linkedHistogram)
      .map((entry) => chartSVGDataUrl(entry, true));
  }

  function bindControls() {
    byId("caseSelect").addEventListener("change", (event) => actions.setCase(Number(event.target.value), { source: "case-select" }));
    byId("timeline").addEventListener("input", (event) => {
      pausePlayback();
      actions.setFrame(Number(event.target.value), { source: "timeline" });
    });
    byId("prevFrame").addEventListener("click", () => {
      pausePlayback();
      actions.setFrame(store.get().currentFrame - 1, { source: "prev" });
    });
    byId("nextFrame").addEventListener("click", () => {
      pausePlayback();
      actions.setFrame(store.get().currentFrame + 1, { source: "next" });
    });
    byId("playButton").addEventListener("click", togglePlayback);
    byId("playbackSpeed").addEventListener("change", () => {
      runtime.playAccumulator = 0;
    });
    byId("locateCycle").addEventListener("click", () => {
      const target = Number(byId("cycleInput").value);
      if (!Number.isFinite(target) || !runtime.current) return;
      const index = runtime.current.meta.frames.findIndex((frame) => frame.cycle === target);
      if (index < 0) {
        byId("cycleInput").setCustomValidity("该 Case 未精确采集此 Cycle；不会插值。");
        byId("cycleInput").reportValidity();
        return;
      }
      byId("cycleInput").setCustomValidity("");
      pausePlayback();
      actions.setFrame(index, { source: "cycle-locate", force: true });
    });
    byId("cycleInput").addEventListener("input", (event) => event.target.setCustomValidity(""));
    byId("locateBall").addEventListener("click", () => {
      const id = Number(byId("ballInput").value);
      if (Number.isFinite(id)) actions.selectBalls([id], { focus: true, source: "ball-input" });
    });
    byId("ballInput").addEventListener("input", (event) => event.target.setCustomValidity(""));
    byId("clearSelection").addEventListener("click", actions.clearSelection);
    byId("showParticles").addEventListener("change", (event) => { particles.visible = event.target.checked; });
    byId("showWalls").addEventListener("change", (event) => {
      const on = event.target.checked && !!currentFrameData && !!currentFrameData.wallIds;
      // With real facet topology the closed thin slab is the wall; show only
      // that. Without it (PFC2D / old data) the rod/line fallback is correct.
      const hasSlab = wallFaces && wallFaces.geometry.getAttribute("position")
        && Number(document.body.dataset.wallFaces || 0) > 0;
      if (wallFaces) wallFaces.visible = on && !!hasSlab;
      if (wallEdgeLines) wallEdgeLines.visible = on && !!hasSlab;
      if (wallLines) wallLines.visible = on && !hasSlab;
      if (wallPoints) wallPoints.visible = on && !hasSlab;
      if (wallSolids) wallSolids.visible = on && !hasSlab;
    });
    byId("showCracks").addEventListener("change", () => updateCracks(store.get().currentCycle));
    byId("showContacts").addEventListener("change", () => {
      if (currentFrameData) updateParticles(currentFrameData, highlightIdsForState());
    });
    byId("showBonds").addEventListener("change", () => {
      if (currentFrameData) updateParticles(currentFrameData, highlightIdsForState());
    });
    byId("showAxes").addEventListener("change", (event) => {
      axesHelper.visible = event.target.checked;
      grid.visible = is2D && event.target.checked;
    });
    byId("showBounds").addEventListener("change", (event) => { domainBox.visible = event.target.checked; });
    byId("showTrajectory").addEventListener("change", updateTrajectories);
    byId("showClip").addEventListener("change", updateClipping);
    byId("clipAxis").addEventListener("change", updateClipping);
    byId("clipPosition").addEventListener("input", updateClipping);
    byId("colorMetric").addEventListener("change", (event) => { metricUserSet = true; actions.setColorMetric(event.target.value); });
    byId("colorPalette").addEventListener("change", (event) => {
      setPalette(event.target.value);
      if (currentFrameData) updateSelectionVisuals();
    });
    byId("showInsets").addEventListener("change", () => {
      if (currentFrameData) updateParticles(currentFrameData, highlightIdsForState());
    });
    byId("cameraMode").addEventListener("change", (event) => setCameraMode(event.target.value));
    byId("viewPreset").addEventListener("change", (event) => applyViewPreset(event.target.value));
    byId("resetCamera").addEventListener("click", resetCamera);
    byId("exportScene").addEventListener("click", exportScene);
    byId("exportFrame").addEventListener("click", exportFrame);
    byId("exportCharts").addEventListener("click", exportChartSVGs);
    byId("exportPanels").addEventListener("click", exportCompositePanels);
    byId("notesButton").addEventListener("click", () => {
      const notes = byId("notes");
      notes.hidden = !notes.hidden;
      byId("notesButton").setAttribute("aria-expanded", notes.hidden ? "false" : "true");
    });
    document.body.dataset.theme = 'light';
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !byId("notes").hidden) byId("notes").hidden = true;
      if (event.target && /INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) return;
      if (event.code === "Space") { event.preventDefault(); togglePlayback(); }
      else if (event.code === "ArrowLeft") { event.preventDefault(); pausePlayback(); actions.setFrame(store.get().currentFrame - 1, { source: "keyboard" }); }
      else if (event.code === "ArrowRight") { event.preventDefault(); pausePlayback(); actions.setFrame(store.get().currentFrame + 1, { source: "keyboard" }); }
      else if (event.code === "Home") { pausePlayback(); actions.setFrame(0, { source: "keyboard" }); }
      else if (event.code === "End") { pausePlayback(); actions.setFrame(runtime.current.meta.frames.length - 1, { source: "keyboard" }); }
    });
  }

  function populateNotes() {
    const meta = DATA.catalog.meta;
    const domainText = meta.domain && Array.isArray(meta.domain.min) && Array.isArray(meta.domain.max)
      ? "[" + meta.domain.min.map((v) => formatNumber(v, 4)).join(", ") + "] → [" +
        meta.domain.max.map((v) => formatNumber(v, 4)).join(", ") + "]"
      : "未提供";
    const activeCase = DATA.catalog.cases.find((item) => Number(item.id) === Number(meta.defaultCase));
    const runText = activeCase ? escapeHtml(activeCase.runId) : "未提供";
    byId("notesBody").innerHTML = [
      "<h3>当前状态</h3>",
      "<ul>",
      "<li>维度：" + (Number(meta.dimension) === 2 ? "PFC2D（平面）" : "PFC3D") +
        "；Case " + escapeHtml(String(meta.defaultCase)) + " · Run " + runText + "。</li>",
      "<li>模型边界（真实 domain，单位 m）：" + domainText +
        "；边界框可在三维显示选项中开关，比例尺见场景左下。</li>",
      "</ul>",
      "<h3>真实性</h3>",
      "<ul>",
      "<li>数据边界：" + escapeHtml(meta.dataBoundary) + "；播放只切换真实采样帧，不在帧间插值。</li>",
      "<li>Ball 集合按每帧真实 ID 和变长偏移读取，不以数组下标代替 Ball ID。</li>",
      "<li>缺失值保持缺失并以灰色显示，不补零、不伪造。</li>",
      "<li>颗粒连续色标采用当前真实帧的 P05–P95 稳健区间；图例显示实际数值，超过 P95 的值饱和为高色。</li>",
      "<li>接触与 Bond 网络仅在同帧端点 ID 存在时显示；线色对应实际采集或合法派生的力值。</li>",
      "</ul>",
      "<h3>性能架构</h3>",
      "<ul>",
      "<li>HTML 仅包含页面结构；Three.js、ECharts 和帧数据分别本地加载。</li>",
      "<li>帧数据按块加载并做 LRU 淘汰；颗粒历史按 ID 桶按需加载。</li>",
      "<li>Three.js 实例、ECharts 实例和几何对象在播放及联动时不重复创建。</li>",
      "<li>组合图使用奇偶数量与主次面板自适应布局，并保留标题、来源和面板编号。</li>",
      "</ul>",
      "<h3>支持边界</h3>",
      "<ul>",
      "<li>单颗粒应力与接触力历史仅在实际采集对应字段时提供；当前基线若未采集则明确标记。</li>",
      "<li>裂纹颜色：拉伸裂纹使用主蓝色，剪切裂纹使用朱红色。</li>",
      "<li>空间热力图表示分箱颗粒数密度，不解释为物理应力场。</li>",
      "</ul>"
    ].join("");
  }

  function populateCaseSelect() {
    const select = byId("caseSelect");
    DATA.catalog.cases.forEach((item) => {
      const option = document.createElement("option");
      option.value = String(item.id);
      option.textContent = item.label + " · " + item.runId + " · " + item.viewerFrameCount + "帧";
      select.appendChild(option);
    });
  }

  function resize() {
    if (!renderer || !camera) return;
    const width = Math.max(1, byId("stage").clientWidth);
    const height = Math.max(1, byId("stage").clientHeight);
    camera.aspect = width / height;
    if (camera === orthographicCamera) {
      const aspect = camera.aspect;
      camera.left = -orthoExtent * aspect;
      camera.right = orthoExtent * aspect;
      camera.top = orthoExtent;
      camera.bottom = -orthoExtent;
    }
    if (runtime.viewShift && camera && controls) {
      camera.position.sub(runtime.viewShift);
      controls.target.sub(runtime.viewShift);
      runtime.viewShift = null;
    }
    camera.updateProjectionMatrix();
    const dock = byId("controlDock");
    const dockOpen = body.dataset.dock === "open" && dock && !dock.classList.contains("collapsed");
    const reserve = dockOpen ? Math.min(dock.getBoundingClientRect().height, height * 0.36) : 0;
    if (reserve > 8 && camera && controls) {
      const worldPerPixel = camera === orthographicCamera
        ? (camera.top - camera.bottom) / height
        : (2 * camera.position.distanceTo(controls.target) * Math.tan(camera.fov * Math.PI / 360)) / height;
      const shift = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion).normalize()
        .multiplyScalar(-worldPerPixel * reserve * 0.5);
      camera.position.add(shift);
      controls.target.add(shift);
      runtime.viewShift = shift;
      controls.update();
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    runtime.charts.forEach((entry) => entry.chart.resize());
    if (runtime.historyChart) runtime.historyChart.resize();
  }

  function renderLoop(now) {
    requestAnimationFrame(renderLoop);
    const state = store.get();
    if (!runtime.ready) {
      if (renderer) renderer.render(scene, camera);
      return;
    }
    const last = renderLoop.last || now;
    const delta = Math.min(0.1, (now - last) / 1000);
    renderLoop.last = now;
    if (runtime.playing && runtime.current) {
      runtime.playAccumulator += delta;
      const fps = Number(byId("playbackSpeed").value) || 8;
      if (runtime.playAccumulator >= 1 / fps) {
        runtime.playAccumulator = 0;
        if (state.currentFrame >= runtime.current.meta.frames.length - 1) pausePlayback();
        else actions.setFrame(state.currentFrame + 1, { source: "playback" });
      }
    }
    controls.update();
    renderer.render(scene, camera);
    updateScaleBar();
    renderLoop.metricsFrames = (renderLoop.metricsFrames || 0) + 1;
    if (!renderLoop.metricsLast) renderLoop.metricsLast = now;
    if (now - renderLoop.metricsLast >= 500) {
      const elapsed = (now - renderLoop.metricsLast) / 1000;
      body.dataset.fps = (renderLoop.metricsFrames / elapsed).toFixed(1);
      body.dataset.drawCalls = String(renderer.info.render.calls);
      body.dataset.triangles = String(renderer.info.render.triangles);
      body.dataset.geometries = String(renderer.info.memory.geometries);
      body.dataset.textures = String(renderer.info.memory.textures);
      if (performance.memory) body.dataset.jsHeapBytes = String(performance.memory.usedJSHeapSize);
      renderLoop.metricsLast = now;
      renderLoop.metricsFrames = 0;
    }
  }

  function cleanup() {
    pausePlayback();
    runtime.charts.forEach((entry) => entry.chart.dispose());
    runtime.charts = [];
    if (runtime.historyChart) runtime.historyChart.dispose();
    clearTrajectories();
    if (particles) {
      particles.geometry.dispose();
      particles.material.dispose();
      scene.remove(particles);
    }
    if (highlightMesh) {
      highlightMesh.material.dispose();
      scene.remove(highlightMesh);
    }
    if (highlightGeometry) highlightGeometry.dispose();
    if (wallLines) { wallLines.geometry.dispose(); wallLines.material.dispose(); }
    if (wallPoints) { wallPoints.geometry.dispose(); wallPoints.material.dispose(); }
    if (wallSolids) { scene.remove(wallSolids); wallSolids.geometry.dispose(); wallSolids.material.dispose(); }
    if (wallFaces) { scene.remove(wallFaces); wallFaces.geometry.dispose(); wallFaces.material.dispose(); }
    if (wallEdgeLines) { scene.remove(wallEdgeLines); wallEdgeLines.geometry.dispose(); wallEdgeLines.material.dispose(); }
    [crackTension, crackShear].forEach((line) => {
      if (!line) return;
      line.geometry.dispose();
      line.material.dispose();
    });
    [contactLines, bondLines].forEach((line) => {
      if (!line) return;
      line.geometry.dispose();
      line.material.dispose();
    });
    if (controls) controls.dispose();
    if (renderer) {
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    }
    runtime.caseRuntimes.clear();
    window.removeEventListener("resize", resize);
  }

  async function boot() {
    try {
      if (!DATA.catalog || !DATA.static) throw new Error("DATA_PAYLOAD_MISSING");
      if (!window.THREE || !window.echarts) throw new Error("OFFLINE_VENDOR_MISSING");
      if (Array.isArray(window.PFC_VIEWER_CASE_FILTER)) {
        const allowed = new Set(window.PFC_VIEWER_CASE_FILTER.map(Number));
        DATA.catalog.cases = DATA.catalog.cases.filter((caseItem) => allowed.has(Number(caseItem.id)));
        if (!DATA.catalog.cases.length) throw new Error("CASE_FILTER_EMPTY");
        if (!DATA.catalog.cases.some((caseItem) => caseItem.id === DATA.catalog.meta.defaultCase)) {
          DATA.catalog.meta.defaultCase = DATA.catalog.cases[0].id;
        }
      }
      const probe = webglProbe();
      body.dataset.webglStatus = probe.available ? "available" : "unavailable";
      if (!probe.available) throw new Error("WEBGL_UNAVAILABLE");
      createScene();
      populateCaseSelect();
      populateNotes();
      bindControls();
      runtime.ready = true;
      setCameraMode("adaptive");
      resize();
      applyViewPreset("fit");
      requestAnimationFrame(renderLoop);
      body.dataset.payloadVersion = DATA.catalog.meta.payloadVersion;
      body.dataset.schemaVersion = DATA.catalog.meta.schemaVersion;
      body.dataset.dimension = String(is2D ? 2 : 3);
      body.dataset.caseCount = String(DATA.catalog.cases.length);
      body.dataset.visualSemanticsVersion = visualSemantics.version || "NOT_DECLARED";
      body.dataset.loadMs = (performance.now() - viewerStarted).toFixed(2);
      window.addEventListener("pagehide", cleanup, { once: true });
      window.PFCViewer = {
        state: store,
        actions,
        setFrame: (index) => actions.setFrame(index, { source: "api" }),
        setCase: (caseId) => actions.setCase(caseId, { source: "api" }),
        selectBall: (ballId) => actions.selectBalls([ballId], { source: "api" }),
        // Project a real Ball's current-frame position to CSS screen
        // coordinates.  Used by browser acceptance to click an exact Ball
        // even in sparse/linear scenes where fixed screen offsets miss.
        projectBallToScreen: (ballId) => {
          if (!camera || !currentFrameData || !renderer) return null;
          const frame = currentFrameData;
          if (!frame.ids || !frame.xyz) return null;
          const ids = decodeU32(frame.ids);
          const xyz = decodeF32(frame.xyz);
          let idx = -1;
          for (let i = 0; i < ids.length; i += 1) {
            if (String(ids[i]) === String(ballId)) { idx = i; break; }
          }
          if (idx < 0) return null;
          const v = new THREE.Vector3(
            xyz[idx * 3], xyz[idx * 3 + 1],
            Number(DATA.catalog.meta.dimension) === 2 ? 0 : xyz[idx * 3 + 2]
          );
          v.project(camera);
          const rect = renderer.domElement.getBoundingClientRect();
          return {
            x: rect.left + (v.x * 0.5 + 0.5) * rect.width,
            y: rect.top + (-v.y * 0.5 + 0.5) * rect.height,
            inView: v.z >= -1 && v.z <= 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1
          };
        },
        selectRange: (range, metric) => actions.setRange(range, metric, { source: "api" }),
        clearSelection: () => actions.clearSelection(),
        setViewPreset: (preset) => applyViewPreset(preset),
        exportPNG: () => exportScene(),
        exportFramePNG: async (frameIndex, width) => {
          if (Number.isFinite(Number(width))) byId("exportWidth").value = String(width);
          await setFrame(Number(frameIndex), { source: "api-export", force: true });
          return scenePublicationDataUrl(
            byId("exportWidth").value,
            byId("exportBackground").value
          );
        },
        getPublicationExportContract: () => ({
          format: "PNG",
          includes_scene: true,
          includes_metric_label: true,
          includes_unit: true,
          includes_colorbar: true,
          includes_case: true,
          includes_cycle_and_time: true,
          includes_scale_bar: true,
          includes_annotations: true,
          scene_svg: "NOT_SUPPORTED",
          metadata_only_svg: "NOT_SUPPORTED"
        }),
        exportChartSVGs,
        exportCompositePanels,
        getChartSVGDataURLs: chartSVGDataUrls,
        getCompositePanelDataURL: compositePanelsDataUrl,
        getCompositePanelLayout: () => compositeLayout(
          runtime.charts.filter((entry) => !entry.linkedHistogram).length,
          1.5
        ),
        formatting: Object.freeze({
          number: (value, digits) => formatNumber(value, digits),
          metric: (value, unit, digits) => formatMetric(value, unit, digits),
          tooltip: (value, formatting) => formatTooltipValue(value, formatting)
        }),
        getChartExportEntries: chartExportEntries,
        cleanup
      };
      await switchCase(DATA.catalog.meta.defaultCase, "initial");
    } catch (error) {
      showError(error.code || "VIEWER_RUNTIME_ERROR", error);
    }
  }

  boot();
})();
