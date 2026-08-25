const DCTERMS = "http://purl.org/dc/terms/";

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

// Promoted to the Tile's face, so they must not also appear in the
// collapsed field list.
const NAME_PROPERTIES = [`${DCTERMS}title`, `${DCTERMS}name`];
const IDENTIFIER_PROPERTY = `${DCTERMS}identifier`;
const DESCRIPTION_PROPERTY = `${DCTERMS}description`;

// A known property gets a translated label; anything else falls back to a
// humanized local name, so a schedule carrying properties this Tile has
// never seen still reads as prose rather than as an IRI.
const FIELD_LABEL_KEYS = {
  [`${DCTERMS}conformsTo`]: "conformsToLabel",
};

// Where EntityViewsPublishedCapability writes the standalone Gantt page for
// this entity: `.__ontobdc__/view/<path_segment>/<identifier>.html`, relative
// to the Surface's own index.html. The segment is IfcWorkScheduleViewPage's
// own `path_segment`.
const VIEW_PATH_SEGMENT = "ifc_work_schedule";

// Canonical URL-controlled presentation parameters. The page's URL-state
// runtime owns this list when it is present, and this Tile defers to it —
// but a Tile is self-sufficient by contract, so it also has to know the
// list itself. A link that quietly stops carrying state because a runtime
// from another package is missing is a broken link, not a degraded one.
const PRESENTATION_PARAMS = ["lang", "theme"];

const APPLIED_PRESENTATION_STATE = {
  lang: () =>
    document.documentElement.lang
    || document.documentElement.dataset.language
    || "",
  theme: () => document.documentElement.dataset.theme || "",
};

/**
 * Return `href` carrying the active presentation state, so the standalone
 * page opens in the language and theme in use here. A parameter the link
 * already declares always wins.
 */
function decorateInternalUrl(href) {
  const state = window.ontobdcUrlState;
  if (state && typeof state.decorate === "function") return state.decorate(href);

  try {
    const target = new URL(href, location.href);
    const current = new URLSearchParams(location.search);
    for (const name of PRESENTATION_PARAMS) {
      if (target.searchParams.has(name)) continue;
      const carried = current.get(name) || APPLIED_PRESENTATION_STATE[name]();
      if (carried) target.searchParams.set(name, carried);
    }
    return target.href;
  } catch {
    return href;
  }
}

class OntoInfoBIMIfcWorkScheduleTile extends HTMLElement {
  #root;
  #expanded = false;
  #originalRows = null;
  #originalMaxRows = null;
  #originalMinRows = 3;

  static get observedAttributes() {
    return ["data-ontobdc-resource", "columns", "rows"];
  }

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed" });
  }

  connectedCallback() {
    // Captured once: a move within the same parent disconnects and
    // reconnects the element, and re-capturing mid-expand would record the
    // already-grown size as the original.
    if (this.#originalRows === null) {
      this.#originalRows = this.getAttribute("rows") || "3";
      this.#originalMaxRows = this.getAttribute("max-rows") || this.#originalRows;
      this.#originalMinRows = Math.max(1, Number.parseInt(this.getAttribute("min-rows") || "3", 10));
    }
    this.#render();
    // The open-link's carried state is snapshotted at render time — keep it
    // in sync if the user switches theme after this Tile already rendered.
    document.addEventListener("theme-changed", this.#onThemeChanged);
    document.addEventListener("language-changed", this.#onLanguageChanged);
  }

  disconnectedCallback() {
    document.removeEventListener("theme-changed", this.#onThemeChanged);
    document.removeEventListener("language-changed", this.#onLanguageChanged);
  }

  #onLanguageChanged = () => this.#render();

  #onThemeChanged = () => this.#syncOpenLink(this.#literal(this.#entity(), IDENTIFIER_PROPERTY));

  attributeChangedCallback() {
    if (this.isConnected) this.#render();
  }

  #graph() {
    const source = document.getElementById("ontobdc-surface-jsonld");
    if (!source) return [];
    try {
      const graph = JSON.parse(source.textContent);
      return Array.isArray(graph) ? graph : [graph];
    } catch {
      return [];
    }
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

  #localName(iri) {
    return String(iri).split(/[\/#]/).filter(Boolean).pop() || String(iri);
  }

  #humanize(iri) {
    return this.#localName(iri)
      .replace(/_Ifc.*$/, "")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/^./, (character) => character.toUpperCase());
  }

  // Everything the face does not already show, in stable document order.
  // An `@id` value renders as its local name with the full IRI on hover:
  // a bare facade URL is noise on a summary Tile, but throwing it away
  // would lose the only pointer to what the schedule conforms to.
  #populatedFields(entity) {
    if (!entity) return [];
    const shown = new Set([...NAME_PROPERTIES, IDENTIFIER_PROPERTY, DESCRIPTION_PROPERTY]);
    const fields = [];
    for (const [property, values] of Object.entries(entity)) {
      if (property.startsWith("@") || shown.has(property) || !Array.isArray(values)) continue;
      const parts = [];
      let iri = "";
      for (const item of values) {
        const literal = item?.["@value"];
        if (literal !== undefined && literal !== null && String(literal).trim()) {
          parts.push(String(literal).trim());
          continue;
        }
        const reference = item?.["@id"];
        if (reference) {
          iri = String(reference);
          parts.push(this.#humanize(reference));
        }
      }
      const value = parts.filter(Boolean).join(", ");
      if (!value) continue;
      const labelKey = FIELD_LABEL_KEYS[property];
      fields.push({
        label: labelKey ? t(labelKey) : this.#humanize(property),
        value,
        title: iri,
      });
    }
    return fields;
  }

  async #toggleExpand() {
    if (this.#expanded) {
      this.#collapse();
      return;
    }
    this.#expanded = true;
    const tileEl = this.#root.querySelector(".tile");
    tileEl.classList.add("expanded");
    this.#updateExpandButton();

    const surface = this.closest("onto-presentation-surface");
    let rows = this.#estimateRowsNeeded();
    this.setAttribute("max-rows", String(rows));
    this.setAttribute("rows", String(rows));
    surface?.sendToEnd(this);

    for (let attempt = 0; attempt < 5; attempt += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      if (tileEl.scrollHeight <= tileEl.clientHeight + 1) break;
      rows += 1;
      this.setAttribute("max-rows", String(rows));
      this.setAttribute("rows", String(rows));
      surface?.relayout();
    }

    requestAnimationFrame(() => this.scrollIntoView({ behavior: "smooth", block: "end" }));
  }

  #collapse() {
    this.#expanded = false;
    this.#root.querySelector(".tile").classList.remove("expanded");
    this.#updateExpandButton();
    this.setAttribute("rows", this.#originalRows);
    this.setAttribute("max-rows", this.#originalMaxRows);
    this.closest("onto-presentation-surface")?.relayout();
  }

  #estimateRowsNeeded() {
    const fieldCount = this.#populatedFields(this.#entity()).length;
    if (!fieldCount) return this.#originalMinRows;
    const estimated = Math.ceil((fieldCount * 2 + 3) / 3);
    return Math.max(this.#originalMinRows, estimated);
  }

  // Points at the standalone Gantt page published for this schedule. With
  // no identifier there is no page to point at, so the action is disabled
  // rather than left dangling.
  #syncOpenLink(identifier) {
    const openLink = this.#root.querySelector(".open-link");
    if (!openLink) return;
    if (!identifier) {
      openLink.removeAttribute("href");
      openLink.setAttribute("aria-disabled", "true");
      return;
    }
    openLink.href = decorateInternalUrl(
      `.__ontobdc__/view/${VIEW_PATH_SEGMENT}/${encodeURIComponent(identifier)}.html`,
    );
    openLink.removeAttribute("aria-disabled");
    const label = t("openView");
    openLink.title = label;
    openLink.setAttribute("aria-label", label);
  }

  #updateExpandButton() {
    const button = this.#root.querySelector(".expand-btn");
    if (!button) return;
    button.classList.toggle("is-expanded", this.#expanded);
    const label = this.#expanded ? t("collapse") : t("expand");
    button.title = label;
    button.setAttribute("aria-label", label);
  }

  #render() {
    const columns = Math.max(1, Number.parseInt(this.getAttribute("columns") || "1", 10));
    const rows = Math.max(1, Number.parseInt(this.getAttribute("rows") || "1", 10));
    const entity = this.#entity();

    this.#root.innerHTML = `
      <style>
        :host {
          all: initial;
          display: block;
          inline-size: 100%;
          block-size: 100%;
          min-inline-size: 0;
          min-block-size: 0;
          box-sizing: border-box;
          container-type: size;
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        *, *::before, *::after { box-sizing: border-box; }
        .tile {
          position: relative;
          inline-size: 100%;
          block-size: 100%;
          min-inline-size: 0;
          min-block-size: 0;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: clamp(6px, 3cqw, 14px);
          padding: clamp(12px, 5cqw, 22px);
          border-radius: var(--onto-theme-tile-border-radius, 16px);
          border: var(--onto-theme-tile-border-width, 1px) solid
            color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 22%, transparent);
          background: color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 5%, var(--onto-theme-background, #ffffff));
          color: var(--onto-theme-foreground, #0f172a);
        }
        .header-row {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 8px;
        }
        .label {
          font-size: clamp(10px, 3cqw, 12px);
          font-weight: 700;
          letter-spacing: .12em;
          text-transform: uppercase;
          color: color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 60%, transparent);
        }
        .body {
          display: grid;
          gap: clamp(2px, 1.4cqw, 6px);
          min-inline-size: 0;
        }
        .name {
          font-size: clamp(16px, 7cqw, 28px);
          font-weight: 800;
          line-height: 1.15;
          overflow-wrap: anywhere;
        }
        .identifier {
          font-size: clamp(9px, 2.4cqw, 11px);
          font-weight: 600;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          color: color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 62%, transparent);
          overflow-wrap: anywhere;
        }
        .description {
          font-size: clamp(11px, 2.6cqw, 13px);
          line-height: 1.4;
          overflow-wrap: anywhere;
          color: color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 82%, transparent);
        }
        .description:empty { display: none; }
        .fields {
          display: none;
          grid-template-columns: 1fr;
          gap: clamp(6px, 1.6cqh, 12px);
          padding-block-start: clamp(4px, 1.2cqh, 10px);
          border-block-start: 1px solid color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 14%, transparent);
        }
        .tile.expanded .fields { display: grid; }
        /* Nothing populated to reveal: no divider or padding either, or
           expanding would grow the Tile just to show empty space. */
        .fields:empty {
          display: none !important;
          border: 0;
          padding: 0;
        }
        .field-label {
          font-size: clamp(9px, 2.2cqw, 11px);
          font-weight: 700;
          letter-spacing: .08em;
          text-transform: uppercase;
          color: color-mix(in srgb, var(--onto-theme-accent, #0ea5e9) 85%, var(--onto-theme-foreground, #0f172a));
        }
        .field-value {
          font-size: clamp(11px, 2.6cqw, 13px);
          line-height: 1.4;
          overflow-wrap: anywhere;
          white-space: pre-wrap;
        }
        .footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        .dims {
          font-size: clamp(10px, 2.8cqw, 12px);
          color: color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 55%, transparent);
        }
        .badge {
          font-size: clamp(10px, 2.6cqw, 12px);
          font-weight: 600;
          padding: .3em .75em;
          border-radius: 999px;
          border: 1px solid color-mix(in srgb, var(--onto-theme-accent, #0ea5e9) 45%, transparent);
          color: var(--onto-theme-accent, #0ea5e9);
          white-space: nowrap;
        }
        .actions {
          display: flex;
          align-items: center;
          gap: 4px;
          flex: none;
        }
        .icon-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          inline-size: 24px;
          block-size: 24px;
          padding: 0;
          border: 0;
          border-radius: 6px;
          background: transparent;
          color: var(--onto-theme-accent, #0ea5e9);
          cursor: pointer;
        }
        .icon-btn:hover {
          background: color-mix(in srgb, var(--onto-theme-foreground, #0f172a) 10%, transparent);
        }
        .icon-btn:disabled,
        .icon-btn[aria-disabled="true"] {
          opacity: .35;
          cursor: default;
          pointer-events: none;
        }
        .icon-btn svg {
          inline-size: 14px;
          block-size: 14px;
          transition: transform .15s ease;
        }
        .icon-btn.expand-btn.is-expanded svg { transform: rotate(180deg); }
      </style>
      <article class="tile">
        <div class="header-row">
          <div class="label schedule-label"></div>
          <div class="actions">
            <a class="icon-btn open-link">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
            <button type="button" class="expand-btn icon-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
          </div>
        </div>
        <div class="body">
          <div class="name"></div>
          <div class="identifier"></div>
          <div class="description"></div>
        </div>
        <div class="fields"></div>
        <div class="footer">
          <span class="dims"></span>
          <span class="badge"></span>
        </div>
      </article>
    `;

    const name = NAME_PROPERTIES.map((property) => this.#literal(entity, property)).find(Boolean)
      || t("fallbackTitle");
    this.#root.querySelector(".schedule-label").textContent = t("eyebrow");
    this.#root.querySelector(".name").textContent = name;
    this.#root.querySelector(".identifier").textContent = this.#literal(entity, IDENTIFIER_PROPERTY);
    this.#root.querySelector(".description").textContent = this.#literal(entity, DESCRIPTION_PROPERTY);
    this.#root.querySelector(".dims").textContent = `${columns} × ${rows}`;
    this.#root.querySelector(".badge").textContent = t("badge");

    this.#syncOpenLink(this.#literal(entity, IDENTIFIER_PROPERTY));

    const fields = this.#populatedFields(entity);
    const fieldsContainer = this.#root.querySelector(".fields");
    for (const { label, value, title } of fields) {
      const row = document.createElement("div");
      row.className = "field";
      const labelEl = document.createElement("div");
      labelEl.className = "field-label";
      labelEl.textContent = label;
      const valueEl = document.createElement("div");
      valueEl.className = "field-value";
      valueEl.textContent = value;
      if (title) valueEl.title = title;
      row.append(labelEl, valueEl);
      fieldsContainer.appendChild(row);
    }

    const expandButton = this.#root.querySelector(".expand-btn");
    expandButton.addEventListener("click", (event) => {
      event.preventDefault();
      this.#toggleExpand();
    });
    // Nothing to expand into — don't offer an action that would just grow
    // the Tile to show empty space.
    expandButton.disabled = fields.length === 0;
    if (fields.length === 0) expandButton.title = t("noDetailsToShow");
    if (this.#expanded) this.#root.querySelector(".tile").classList.add("expanded");
    this.#updateExpandButton();
  }
}

if (!customElements.get("onto-infobim-ifc-work-schedule-tile")) {
  customElements.define("onto-infobim-ifc-work-schedule-tile", OntoInfoBIMIfcWorkScheduleTile);
}

export { OntoInfoBIMIfcWorkScheduleTile };
