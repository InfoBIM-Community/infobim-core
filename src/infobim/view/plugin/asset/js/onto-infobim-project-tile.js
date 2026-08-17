const IFCOWL = "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#";
const DCTERMS = "http://purl.org/dc/terms/";
const SCHEMA = "https://schema.org/";
const INFOBIM_PRESENTATION = "urn:infobim:presentation:";
const I18N = __ONTOBDC_BUILD_I18N__;

function t(key, vars) {
  const locale = document.documentElement.lang || document.documentElement.dataset.language || "en";
  const table = I18N[locale] || I18N.en || {};
  let text = table[key] ?? key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) text = text.replaceAll(`{${name}}`, value);
  }
  return text;
}

class OntoInfoBIMProjectTile extends HTMLElement {
  #root;

  static get observedAttributes() {
    return ["data-ontobdc-resource"];
  }

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed" });
  }

  connectedCallback() {
    this.#render();
    document.addEventListener("language-changed", this.#onLanguageChanged);
  }

  disconnectedCallback() {
    document.removeEventListener("language-changed", this.#onLanguageChanged);
  }

  #onLanguageChanged = () => this.#render();

  attributeChangedCallback() { if (this.isConnected) this.#render(); }

  #graph() {
    const source = document.getElementById("ontobdc-surface-jsonld");
    if (!source) return [];
    try {
      const graph = JSON.parse(source.textContent);
      return Array.isArray(graph) ? graph : [graph];
    } catch { return []; }
  }

  #entity() {
    const id = this.getAttribute("data-ontobdc-resource");
    if (!id) return null;
    return this.#graph().find((node) => node?.["@id"] === id) || null;
  }

  #literal(entity, property) {
    const values = entity?.[property];
    if (!Array.isArray(values) || !values.length) return "";
    return String(values[0]?.["@value"] ?? values[0]?.["@id"] ?? "").trim();
  }

  #surfaceProjectPath() {
    if (window.location.protocol !== "file:") return "";
    try {
      let pathname = decodeURIComponent(new URL(".", window.location.href).pathname);
      if (/^\/[A-Za-z]:\//.test(pathname)) pathname = pathname.slice(1);
      pathname = pathname.replace(/\/$/, "");
      return navigator.userAgent.includes("Windows") ? pathname.replaceAll("/", "\\") : pathname;
    } catch { return ""; }
  }

  #indexedFileCount() {
    const projectId = this.getAttribute("data-ontobdc-resource");
    const resources = new Set();
    for (const node of this.#graph()) {
      if (!node || node["@id"] === projectId) continue;
      if (String(node["@id"] || "").startsWith("urn:infobim:presentation:ifc-model:")) continue;
      const hasFormat = Array.isArray(node[`${SCHEMA}encodingFormat`]) || Array.isArray(node[`${DCTERMS}format`]);
      const hasContent = Array.isArray(node[`${SCHEMA}contentUrl`]) || Array.isArray(node[`${SCHEMA}url`]);
      if (hasFormat || hasContent) resources.add(String(node["@id"] || JSON.stringify(node)));
    }
    return resources.size;
  }

  #renderGeolocation(latitude, longitude) {
    const value = this.#root.querySelector(".geolocation-value");
    if (!value) return;
    value.replaceChildren();

    const text = document.createElement("span");
    text.className = "geolocation-text";

    const lat = Number(latitude);
    const lon = Number(longitude);
    const isValid = Number.isFinite(lat) && Number.isFinite(lon)
      && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;

    if (!isValid) {
      text.textContent = "—";
      value.append(text);
      return;
    }

    text.textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;

    const pin = document.createElement("a");
    pin.className = "map-pin";
    pin.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(lat)}&mlon=${encodeURIComponent(lon)}#map=18/${encodeURIComponent(lat)}/${encodeURIComponent(lon)}`;
    pin.target = "_blank";
    pin.rel = "noopener noreferrer";
    pin.title = t("openLocationInMaps");
    pin.setAttribute("aria-label", t("openLocationInMaps"));
    pin.textContent = "\u{1F4CD}";

    value.append(text, pin);
  }

  #setGeolocation(entity) {
    if (!this.#root.querySelector(".geolocation-value")) return;
    const latitude = this.#literal(entity, `${SCHEMA}latitude`);
    const longitude = this.#literal(entity, `${SCHEMA}longitude`);
    if (latitude && longitude) {
      this.#renderGeolocation(latitude, longitude);
      return;
    }
    this.#renderGeolocation(null, null);
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.#renderGeolocation(position.coords.latitude, position.coords.longitude);
      },
      () => {},
      { enableHighAccuracy: false, maximumAge: 300000, timeout: 5000 },
    );
  }

  #render() {
    const entity = this.#entity();
    const globalId = this.#literal(entity, `${DCTERMS}identifier`);
    const name = this.#literal(entity, `${IFCOWL}name_IfcRoot`) || this.#literal(entity, `${DCTERMS}title`) || globalId;
    const longName = this.#literal(entity, `${IFCOWL}longName_IfcContext`);
    const phase = this.#literal(entity, `${IFCOWL}phase_IfcContext`);
    const description = this.#literal(entity, `${IFCOWL}description_IfcRoot`);
    const projectPath = this.#literal(entity, `${INFOBIM_PRESENTATION}projectPath`) || this.#surfaceProjectPath();
    const indexedFileCount = this.#indexedFileCount();

    this.#root.innerHTML = `
      <style>
        :host { all:initial; display:block; inline-size:100%; block-size:100%; box-sizing:border-box; font-family:system-ui,sans-serif; color:var(--onto-theme-foreground,#0f172a); }
        * { box-sizing:border-box; }
        article { block-size:100%; display:flex; flex-direction:column; gap:.5rem; overflow:auto; padding:clamp(12px,3cqw,22px); border-radius:var(--onto-theme-tile-border-radius,16px); border:1px solid color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 48%,transparent); background:linear-gradient(135deg,color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 17%,var(--onto-theme-background,#fff)),var(--onto-theme-background,#fff)); }
        .eyebrow { font-size:.7rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; color:var(--onto-theme-accent,#0ea5e9); }
        h1 { margin:0; font-size:clamp(1.1rem,4.5cqw,1.9rem); line-height:1.08; overflow-wrap:anywhere; }
        .long { font-size:.88rem; font-weight:600; opacity:.72; }
        .description { font-size:.85rem; line-height:1.4; opacity:.8; overflow-wrap:anywhere; }
        .meta { display:flex; flex-wrap:wrap; gap:.4rem .8rem; font:600 .72rem ui-monospace,monospace; opacity:.68; }
        dl { display:grid; gap:.35rem; margin:.1rem 0 0; }
        .row { display:grid; grid-template-columns:minmax(6rem,32%) 1fr; gap:.6rem; padding:.4rem .6rem; border:1px solid color-mix(in srgb,var(--onto-theme-foreground,#0f172a) 14%,transparent); border-radius:10px; background:color-mix(in srgb,var(--onto-theme-background,#fff) 86%,transparent); font-size:.85rem; }
        dt { margin:0; min-width:0; overflow-wrap:anywhere; font-weight:800; color:var(--onto-theme-accent,#0ea5e9); }
        dd { margin:0; overflow-wrap:anywhere; line-height:1.35; }
        .geolocation-value { display:inline-flex; align-items:center; gap:10px; max-width:100%; }
        .geolocation-text { overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
        .map-pin { display:inline-grid; place-items:center; flex:0 0 auto; inline-size:28px; block-size:28px; border:1px solid color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 45%,transparent); border-radius:999px; color:inherit; background:color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 10%,transparent); text-decoration:none; line-height:1; font-size:.95rem; }
        .map-pin:hover { background:color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 18%,transparent); }
        .map-pin:focus-visible { outline:2px solid var(--onto-theme-accent,#0ea5e9); outline-offset:2px; }
      </style>
      <article>
        <div class="eyebrow"></div>
        <h1></h1>
        <div class="long"></div>
        <div class="description"></div>
        <div class="meta"><span class="phase"></span></div>
        <dl>
          <div class="row"><dt class="globalid-label"></dt><dd class="globalid-value"></dd></div>
          <div class="row"><dt class="geolocation-label"></dt><dd class="geolocation-value"><span class="geolocation-text">—</span></dd></div>
          <div class="row"><dt class="path-label"></dt><dd class="path-value"></dd></div>
          <div class="row"><dt class="indexed-label"></dt><dd class="indexed-value"></dd></div>
        </dl>
      </article>`;
    this.#root.querySelector(".eyebrow").textContent = t("eyebrow");
    this.#root.querySelector("h1").textContent = name || t("fallbackName");
    this.#root.querySelector(".long").textContent = longName;
    this.#root.querySelector(".description").textContent = description || "—";
    this.#root.querySelector(".phase").textContent = phase ? t("phasePrefix", { phase }) : "";
    this.#root.querySelector(".globalid-label").textContent = t("globalIdLabel");
    this.#root.querySelector(".globalid-value").textContent = globalId || "—";
    this.#root.querySelector(".geolocation-label").textContent = t("geolocationLabel");
    this.#root.querySelector(".path-label").textContent = t("pathLabel");
    this.#root.querySelector(".path-value").textContent = projectPath || "—";
    this.#root.querySelector(".indexed-label").textContent = t("indexedFilesLabel");
    this.#root.querySelector(".indexed-value").textContent = String(indexedFileCount);
    this.#setGeolocation(entity);
  }
}

if (!customElements.get("onto-infobim-project-tile")) {
  customElements.define("onto-infobim-project-tile", OntoInfoBIMProjectTile);
}

export { OntoInfoBIMProjectTile };
