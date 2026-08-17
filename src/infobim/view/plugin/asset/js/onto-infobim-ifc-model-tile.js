const RDF_VALUE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#value";
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

class OntoInfoBIMIfcModelTile extends HTMLElement {
  #root;
  #className = null;
  #elementKey = null;

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

  attributeChangedCallback() {
    if (this.isConnected) {
      this.#className = null;
      this.#elementKey = null;
      this.#render();
    }
  }

  #payload() {
    const id = this.getAttribute("data-ontobdc-resource");
    const source = document.getElementById("ontobdc-surface-jsonld");
    if (!id || !source) return { classes: [], class_count: 0, element_count: 0 };
    try {
      const graph = JSON.parse(source.textContent);
      const entity = (Array.isArray(graph) ? graph : [graph]).find((node) => node?.["@id"] === id);
      const encoded = entity?.[RDF_VALUE]?.[0]?.["@value"];
      return encoded ? JSON.parse(encoded) : { classes: [] };
    } catch { return { classes: [] }; }
  }

  #globalId(element) {
    return String(element?.GlobalId ?? element?.globalId ?? element?.global_id ?? element?.URI ?? element?.uri ?? "").trim();
  }

  #name(element) {
    return String(element?.Name ?? element?.name ?? this.#globalId(element) ?? t("ifcElementFallback")).trim();
  }

  #render() {
    const payload = this.#payload();
    const classes = Array.isArray(payload.classes) ? payload.classes : [];
    const selectedClass = classes.find((item) => item.class_name === this.#className) || null;
    const elements = Array.isArray(selectedClass?.elements) ? selectedClass.elements : [];
    const selectedElement = elements.find((item) => this.#globalId(item) === this.#elementKey) || null;

    this.#root.innerHTML = `
      <style>
        :host { all:initial; display:block; inline-size:100%; block-size:100%; min-block-size:0; box-sizing:border-box; font-family:system-ui,sans-serif; color:var(--onto-theme-foreground,#0f172a); }
        * { box-sizing:border-box; }
        article { block-size:100%; min-block-size:0; display:grid; grid-template-rows:auto minmax(0,1fr); overflow:hidden; border-radius:var(--onto-theme-tile-border-radius,16px); border:1px solid color-mix(in srgb,var(--onto-theme-foreground,#0f172a) 22%,transparent); background:color-mix(in srgb,var(--onto-theme-foreground,#0f172a) 4%,var(--onto-theme-background,#fff)); }
        header { display:flex; align-items:center; justify-content:space-between; gap:.75rem; padding:.85rem 1rem; border-block-end:1px solid color-mix(in srgb,var(--onto-theme-foreground,#0f172a) 14%,transparent); }
        .title { min-inline-size:0; }
        .eyebrow { font-size:.66rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:var(--onto-theme-accent,#0ea5e9); }
        h2 { margin:.1rem 0 0; font-size:1.05rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .counts { font-size:.7rem; font-weight:700; opacity:.62; white-space:nowrap; }
        main { min-block-size:0; overflow:auto; padding:.65rem; }
        .list { display:grid; gap:.38rem; }
        button { inline-size:100%; display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; gap:.6rem; padding:.62rem .72rem; border:0; border-radius:10px; background:color-mix(in srgb,var(--onto-theme-foreground,#0f172a) 7%,transparent); color:inherit; text-align:start; cursor:pointer; }
        button:hover { background:color-mix(in srgb,var(--onto-theme-accent,#0ea5e9) 16%,transparent); }
        button.back { inline-size:auto; display:inline-flex; margin-block-end:.55rem; color:var(--onto-theme-accent,#0ea5e9); font-weight:750; }
        .name { min-inline-size:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:.8rem; font-weight:700; }
        .count { font:700 .68rem ui-monospace,monospace; opacity:.6; }
        dl { display:grid; grid-template-columns:minmax(7rem,.35fr) minmax(0,1fr); gap:.4rem .75rem; margin:0; font-size:.75rem; }
        dt { font-weight:750; opacity:.64; overflow-wrap:anywhere; }
        dd { margin:0; overflow-wrap:anywhere; white-space:pre-wrap; }
        .empty { padding:1rem; text-align:center; opacity:.58; font-size:.82rem; }
      </style>
      <article>
        <header><div class="title"><div class="eyebrow"></div><h2></h2></div><div class="counts"></div></header>
        <main></main>
      </article>`;

    this.#root.querySelector(".eyebrow").textContent = t("distributedIfc");
    this.#root.querySelector("h2").textContent = t("ifcModel");
    this.#root.querySelector(".counts").textContent =
      `${payload.class_count ?? classes.length} ${t("classes").toLowerCase()} · ${payload.element_count ?? 0} ${t("elements").toLowerCase()}`;
    const main = this.#root.querySelector("main");

    if (selectedElement) this.#renderElement(main, selectedClass, selectedElement);
    else if (selectedClass) this.#renderElements(main, selectedClass, elements);
    else this.#renderClasses(main, classes);
  }

  #back(main, label, action) {
    const button = document.createElement("button");
    button.className = "back";
    button.textContent = `← ${label}`;
    button.addEventListener("click", action);
    main.append(button);
  }

  #renderClasses(main, classes) {
    if (!classes.length) {
      main.innerHTML = '<div class="empty"></div>';
      main.querySelector(".empty").textContent = t("noClasses");
      return;
    }
    const list = document.createElement("div");
    list.className = "list";
    for (const item of classes) {
      const button = document.createElement("button");
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = item.class_name || item.class_uri || t("ifcClassFallback");
      const count = document.createElement("span");
      count.className = "count";
      count.textContent = String(item.element_count ?? 0);
      button.append(name, count);
      button.addEventListener("click", () => { this.#className = item.class_name; this.#render(); });
      list.append(button);
    }
    main.append(list);
  }

  #renderElements(main, selectedClass, elements) {
    this.#back(main, t("classes"), () => { this.#className = null; this.#render(); });
    if (!elements.length) {
      main.insertAdjacentHTML("beforeend", '<div class="empty"></div>');
      main.querySelector(".empty").textContent = t("noElements");
      return;
    }
    const list = document.createElement("div");
    list.className = "list";
    elements.forEach((element, index) => {
      const id = this.#globalId(element) || `row-${index + 1}`;
      const button = document.createElement("button");
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = this.#name(element);
      const count = document.createElement("span");
      count.className = "count";
      count.textContent = id;
      button.append(name, count);
      button.addEventListener("click", () => { this.#elementKey = id; this.#render(); });
      list.append(button);
    });
    main.append(list);
  }

  #renderElement(main, selectedClass, element) {
    this.#back(main, selectedClass.class_name || t("elements"), () => { this.#elementKey = null; this.#render(); });
    const values = { [t("ifcClassFallback")]: selectedClass.class_name, ...element };
    const dl = document.createElement("dl");
    for (const [key, raw] of Object.entries(values)) {
      if (raw === null || raw === undefined || raw === "") continue;
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = key;
      dd.textContent = Array.isArray(raw) ? raw.join("\n") : (typeof raw === "object" ? JSON.stringify(raw, null, 2) : String(raw));
      dl.append(dt, dd);
    }
    main.append(dl);
  }
}

if (!customElements.get("onto-infobim-ifc-model-tile")) {
  customElements.define("onto-infobim-ifc-model-tile", OntoInfoBIMIfcModelTile);
}

export { OntoInfoBIMIfcModelTile };

