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

class OntoInfoBIMIfcWorkScheduleTile extends HTMLElement {
  #root;

  static get observedAttributes() { return ["data-ontobdc-resource"]; }

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

  #entity() {
    const id = this.getAttribute("data-ontobdc-resource");
    const source = document.getElementById("ontobdc-surface-jsonld");
    if (!id || !source) return null;
    try {
      const graph = JSON.parse(source.textContent);
      return (Array.isArray(graph) ? graph : [graph]).find((node) => node?.["@id"] === id) || null;
    } catch { return null; }
  }

  #label(uri) {
    return String(uri).split(/[\/#]/).pop().replace(/_Ifc.*$/, "").replace(/([a-z])([A-Z])/g, "$1 $2");
  }

  #render() {
    const entity = this.#entity() || {};
    const rows = [];
    for (const [property, values] of Object.entries(entity)) {
      if (property.startsWith("@") || !Array.isArray(values)) continue;
      const value = values.map((item) => item?.["@value"] ?? item?.["@id"] ?? "").filter(Boolean).join(", ");
      if (value) rows.push([this.#label(property), value]);
    }
    const title = rows.find(([label]) => label.toLowerCase() === "title")?.[1]
      || rows.find(([label]) => label.toLowerCase() === "name")?.[1]
      || t("fallbackTitle");

    this.#root.innerHTML = `
      <style>
        :host { all:initial; display:block; inline-size:100%; block-size:100%; box-sizing:border-box; font-family:system-ui,sans-serif; color:var(--onto-theme-foreground,#0f172a); }
        article { block-size:100%; overflow:auto; padding:1rem; border-radius:var(--onto-theme-tile-border-radius,16px); border:1px solid color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 35%,transparent); background:color-mix(in srgb,var(--onto-theme-foreground,#0f172a) 4%,var(--onto-theme-background,#fff)); }
        .eyebrow { color:var(--onto-theme-accent,#0ea5e9); font-size:.68rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }
        h2 { margin:.22rem 0 .7rem; font-size:1.05rem; }
        dl { display:grid; grid-template-columns:minmax(6rem,.35fr) 1fr; gap:.35rem .65rem; margin:0; font-size:.74rem; }
        dt { font-weight:750; opacity:.62; } dd { margin:0; overflow-wrap:anywhere; }
      </style>
      <article><div class="eyebrow"></div><h2></h2><dl></dl></article>`;
    this.#root.querySelector(".eyebrow").textContent = t("eyebrow");
    this.#root.querySelector("h2").textContent = title;
    const dl = this.#root.querySelector("dl");
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = value;
      dl.append(dt, dd);
    }
  }
}

if (!customElements.get("onto-infobim-ifc-work-schedule-tile")) {
  customElements.define("onto-infobim-ifc-work-schedule-tile", OntoInfoBIMIfcWorkScheduleTile);
}

export { OntoInfoBIMIfcWorkScheduleTile };

