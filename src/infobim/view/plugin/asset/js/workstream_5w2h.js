(function () {
  "use strict";

  const payload = window.infoBimWorkStreamView || {};
  const openButton = document.getElementById("open-container");
  const updateButton = document.getElementById("update-project");
  const statusElement = document.getElementById("container-status");
  const statusDot = document.getElementById("container-status-dot");
  const databaseName = "infobim-container-access";
  const storeName = "handles";
  const handleKey = String(payload.projectId || "active-project");
  let activeContainerHandle = null;
  let activePyodide = null;
  let resourceModel = {
    resources: [],
    catalogResources: [],
    relationships: {},
  };
  let previewObjectUrl = null;

  function setStatus(message, state) {
    statusElement.textContent = state === "is-ready"
      ? "Carregado"
      : state === "is-error"
        ? "Erro"
        : message;
    statusElement.title = message;
    statusDot.classList.remove("is-ready", "is-error");
    if (state) {
      statusDot.classList.add(state);
    }
  }

  function openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(databaseName, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(storeName)) {
          request.result.createObjectStore(storeName);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function loadStoredHandle() {
    const database = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction(storeName, "readonly");
      const request = transaction.objectStore(storeName).get(handleKey);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
  }

  async function storeHandle(handle) {
    const database = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction(storeName, "readwrite");
      transaction.objectStore(storeName).put(handle, handleKey);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  }

  async function deleteStoredHandle() {
    const database = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction(storeName, "readwrite");
      transaction.objectStore(storeName).delete(handleKey);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  }

  async function isContainerHandle(handle) {
    try {
      const metadataDirectory = await handle.getDirectoryHandle(".__ontobdc__");
      await metadataDirectory.getFileHandle("datapackage.json");
      return true;
    } catch (error) {
      if (error && error.name === "NotFoundError") {
        return false;
      }
      throw error;
    }
  }

  async function resolveContainerHandle(selectedHandle) {
    if (await isContainerHandle(selectedHandle)) {
      return selectedHandle;
    }

    const matches = [];
    for await (const entry of selectedHandle.values()) {
      if (entry.kind === "directory" && await isContainerHandle(entry)) {
        matches.push(entry);
      }
    }

    if (matches.length === 1) {
      return matches[0];
    }
    if (matches.length > 1) {
      throw new Error(
        "Esta pasta contém mais de um projeto InfoBIM. Escolha diretamente a pasta do projeto.",
      );
    }

    throw new Error(
      `A pasta “${selectedHandle.name}” não contém um projeto InfoBIM.`,
    );
  }

  async function requestWritableHandle(handle) {
    const permissionOptions = { mode: "readwrite" };
    const currentPermission = await handle.queryPermission(permissionOptions);
    return (
      currentPermission === "granted"
      || await handle.requestPermission(permissionOptions) === "granted"
    );
  }

  async function acquireContainerHandle() {
    let handle = await loadStoredHandle();
    if (handle) {
      if (await requestWritableHandle(handle)) {
        try {
          return await resolveContainerHandle(handle);
        } catch (error) {
          await deleteStoredHandle();
        }
      } else {
        await deleteStoredHandle();
      }
    }

    handle = await window.showDirectoryPicker({
      id: "infobim-project-container",
      mode: "readwrite",
      startIn: "documents",
    });
    const containerHandle = await resolveContainerHandle(handle);
    await storeHandle(handle);
    return containerHandle;
  }

  function renderWorkStream(record) {
    document.getElementById("workstream-name").textContent =
      record.Name || "WorkStream";
    document.getElementById("workstream-description").textContent =
      record.Description || "";

    document.querySelectorAll("[data-field]").forEach((element) => {
      const value = record[element.dataset.field];
      element.textContent = value === null || value === undefined || value === ""
        ? "—"
        : String(value);
    });
  }

  function categoryMatches(resource, category) {
    return resource.category === category;
  }

  function decodeCatalogComponent(value) {
    try {
      return decodeURIComponent(value);
    } catch (_error) {
      return value;
    }
  }

  function visibleResources(row) {
    const category = row.dataset.activeResource;
    const view = row.dataset.activeView || "related";
    let resources = resourceModel.resources.filter((resource) =>
      categoryMatches(resource, category)
    );
    if (view === "suggested") {
      return [];
    }
    if (view === "related") {
      const dimensionUri = `${payload.dimensionBaseUri}/${row.dataset.dimension}`;
      const relatedIds = new Set(resourceModel.relationships[dimensionUri] || []);
      resources = resources.filter((resource) => relatedIds.has(resource.id));
    }
    return resources;
  }

  function appendTreeItems(parent, node, row) {
    Object.keys(node.directories).sort().forEach((name) => {
      const item = document.createElement("li");
      const disclosure = document.createElement("details");
      disclosure.className = "workstream-tree-directory";
      disclosure.open = true;
      const label = document.createElement("summary");
      label.className = "workstream-tree-folder";
      label.textContent = name;
      disclosure.appendChild(label);
      const children = document.createElement("ul");
      appendTreeItems(children, node.directories[name], row);
      disclosure.appendChild(children);
      item.appendChild(disclosure);
      parent.appendChild(item);
    });
    node.files
      .sort((left, right) => left.name.localeCompare(right.name))
      .forEach((resource) => {
        const item = document.createElement("li");
        const fileRow = document.createElement("div");
        fileRow.className = "workstream-tree-file-row";
        const button = document.createElement("button");
        button.className = "workstream-tree-file";
        if (row.dataset.selectedResource === resource.id) {
          button.classList.add("is-active");
        }
        button.type = "button";
        button.textContent = resource.name;
        button.addEventListener("click", () => previewResource(row, resource));
        fileRow.appendChild(button);
        if (row.dataset.selectedResource === resource.id) {
          const action = relationActionDetails(row, resource);
          if (action) {
            const relationButton = document.createElement("button");
            relationButton.className = "workstream-tree-relation-action";
            relationButton.classList.toggle(
              "is-remove",
              action.action === "remove",
            );
            relationButton.type = "button";
            relationButton.setAttribute("aria-label", action.label);
            relationButton.title = action.label;
            relationButton.innerHTML = relationActionIcon(action.action);
            relationButton.addEventListener("click", (event) => {
              event.stopPropagation();
              row.querySelector("[data-relation-action]").click();
            });
            fileRow.appendChild(relationButton);
          }
        }
        item.appendChild(fileRow);
        parent.appendChild(item);
      });
  }

  function renderResourceTree(row) {
    const tree = row.querySelector("[data-file-tree]");
    const resources = visibleResources(row);
    tree.replaceChildren();
    if (resources.length === 0) {
      const empty = document.createElement("p");
      empty.className = "workstream-resource-empty";
      empty.textContent = row.dataset.activeView === "suggested"
        ? "Nenhum arquivo sugerido."
        : row.dataset.activeView === "found"
          ? "Nenhum arquivo encontrado."
          : "Nenhum arquivo relacionado.";
      tree.appendChild(empty);
      return;
    }

    const root = { directories: {}, files: [] };
    resources.forEach((resource) => {
      const parts = (
        Array.isArray(resource.displayParts)
          ? [...resource.displayParts]
          : resource.id
            .split("/")
            .filter(Boolean)
            .map(decodeCatalogComponent)
      );
      const filename = parts.pop() || resource.name;
      let node = root;
      parts.forEach((part) => {
        node.directories[part] ||= { directories: {}, files: [] };
        node = node.directories[part];
      });
      node.files.push({ ...resource, name: resource.name || filename });
    });
    const list = document.createElement("ul");
    list.className = "workstream-tree-root";
    appendTreeItems(list, root, row);
    tree.appendChild(list);
  }

  function clearPreview(row, message = "Selecione um arquivo.") {
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl);
      previewObjectUrl = null;
    }
    row.querySelector("[data-resource-preview-title]").textContent =
      "Selecione um arquivo";
    delete row.dataset.selectedResource;
    configureRelationAction(row, null);
    const preview = row.querySelector("[data-file-preview]");
    preview.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "workstream-resource-empty";
    empty.textContent = message;
    preview.appendChild(empty);
  }

  async function fileFromCatalogId(resourceId) {
    const cleanPath = resourceId
      .replace(/^\.?\//, "")
      .split("/")
      .map((part) => decodeURIComponent(part))
      .filter((part) => part && part !== "." && part !== "..");
    if (cleanPath.length === 0) {
      throw new Error("A referência não aponta para um arquivo.");
    }
    let directory = activeContainerHandle;
    for (const part of cleanPath.slice(0, -1)) {
      directory = await directory.getDirectoryHandle(part);
    }
    return directory.getFileHandle(cleanPath.at(-1)).then((handle) =>
      handle.getFile()
    );
  }

  function decodedCatalogPath(resourceId) {
    return resourceId
      .replace(/^\.?\//, "")
      .split("/")
      .map(decodeCatalogComponent)
      .join("/");
  }

  function previewRepresentation(resource) {
    if (!/\.dwg$/i.test(decodedCatalogPath(resource.id))) {
      return resource;
    }

    const sourcePath = decodedCatalogPath(resource.id);
    for (const extension of [".pdf", ".png"]) {
      const expectedPath = sourcePath
        .replace(/\.dwg$/i, extension)
        .toLocaleLowerCase();
      const representation = resourceModel.catalogResources.find(
        (candidate) =>
          decodedCatalogPath(candidate.id).toLocaleLowerCase()
          === expectedPath,
      );
      if (representation) {
        return representation;
      }
    }
    return resource;
  }

  function emailAddress(value) {
    if (!value) {
      return "";
    }
    if (typeof value === "string") {
      return value;
    }
    const address = value.address || value.email || "";
    const name = value.name || "";
    return name && address ? `${name} <${address}>` : name || address;
  }

  function emailAddressList(values) {
    if (!values) {
      return "";
    }
    const entries = Array.isArray(values) ? values : [values];
    return entries.map(emailAddress).filter(Boolean).join("; ");
  }

  function msgRecipients(message, type) {
    return emailAddressList(
      (message.recipients || []).filter(
        (recipient) => recipient.recipType === type,
      ),
    );
  }

  function safeEmailDocument(html) {
    const parser = new DOMParser();
    const documentValue = parser.parseFromString(
      html || "<p>Este e-mail não possui corpo.</p>",
      "text/html",
    );
    documentValue.querySelectorAll(
      "script, object, embed, iframe, form, input, button",
    ).forEach((element) => element.remove());
    documentValue.querySelectorAll("*").forEach((element) => {
      [...element.attributes].forEach((attribute) => {
        if (
          attribute.name.toLowerCase().startsWith("on")
          || (
            ["href", "src", "action"].includes(attribute.name.toLowerCase())
            && /^\s*(javascript|data:text\/html)/i.test(attribute.value)
          )
        ) {
          element.removeAttribute(attribute.name);
        }
      });
    });
    const content = documentValue.body.innerHTML;
    return `<!doctype html>
      <html lang="pt-BR">
        <head>
          <meta charset="utf-8">
          <meta
            http-equiv="Content-Security-Policy"
            content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'"
          >
          <style>
            :root { color-scheme: light; }
            body {
              margin: 0;
              padding: 20px;
              color: #172033;
              background: #fff;
              font: 15px/1.55 Inter, Arial, sans-serif;
              overflow-wrap: anywhere;
            }
            img { max-width: 100%; height: auto; }
            pre { white-space: pre-wrap; }
            table { max-width: 100%; }
          </style>
        </head>
        <body>${content}</body>
      </html>`;
  }

  function appendEmailField(container, label, value) {
    if (!value) {
      return;
    }
    const item = document.createElement("div");
    item.className = "workstream-email-field";
    const term = document.createElement("strong");
    term.textContent = label;
    const description = document.createElement("span");
    description.textContent = value;
    item.append(term, description);
    container.appendChild(item);
  }

  function renderEmail(preview, message) {
    const email = document.createElement("article");
    email.className = "workstream-email";
    const header = document.createElement("header");
    header.className = "workstream-email-header";
    const subject = document.createElement("h3");
    subject.textContent = message.subject || "Sem assunto";
    header.appendChild(subject);
    appendEmailField(
      header,
      "De",
      emailAddress(message.from)
        || emailAddress({
          name: message.senderName,
          email: message.senderSmtpAddress || message.senderEmail,
        }),
    );
    appendEmailField(
      header,
      "Para",
      emailAddressList(message.to) || msgRecipients(message, "to"),
    );
    appendEmailField(
      header,
      "Cc",
      emailAddressList(message.cc) || msgRecipients(message, "cc"),
    );
    appendEmailField(
      header,
      "Data",
      message.date
        || message.messageDeliveryTime
        || message.clientSubmitTime
        || message.creationTime,
    );
    email.appendChild(header);

    const frame = document.createElement("iframe");
    frame.className = "workstream-email-body";
    frame.title = `Conteúdo do e-mail: ${message.subject || "Sem assunto"}`;
    frame.setAttribute("sandbox", "");
    const htmlBytes = message.html instanceof Uint8Array
      ? new TextDecoder("utf-8").decode(message.html)
      : "";
    const body = message.html || htmlBytes
      ? message.html && typeof message.html === "string"
        ? message.html
        : htmlBytes
      : `<pre>${String(message.text || message.body || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")}</pre>`;
    frame.srcdoc = safeEmailDocument(body);
    email.appendChild(frame);

    const attachments = message.attachments || [];
    if (attachments.length > 0) {
      const footer = document.createElement("footer");
      footer.className = "workstream-email-attachments";
      const label = document.createElement("strong");
      label.textContent = `Anexos (${attachments.length})`;
      const names = document.createElement("span");
      names.textContent = attachments
        .map((attachment) =>
          attachment.filename
          || attachment.fileName
          || attachment.fileNameShort
          || "Anexo"
        )
        .join(" · ");
      footer.append(label, names);
      email.appendChild(footer);
    }
    preview.appendChild(email);
  }

  async function parseEmail(file, resourceId) {
    if (!window.InfoBIMEmailReader) {
      throw new Error("O leitor de e-mail não foi carregado.");
    }
    const buffer = await file.arrayBuffer();
    if (/\.msg$/i.test(resourceId)) {
      return window.InfoBIMEmailReader.parseMsg(buffer);
    }
    return window.InfoBIMEmailReader.parseEml(buffer);
  }

  async function directoryContainsFile(directory, pathParts) {
    try {
      let current = directory;
      for (const part of pathParts.slice(0, -1)) {
        current = await current.getDirectoryHandle(part);
      }
      await current.getFileHandle(pathParts.at(-1));
      return true;
    } catch (error) {
      if (error && error.name === "NotFoundError") {
        return false;
      }
      throw error;
    }
  }

  async function isDatasetDirectory(directory) {
    return (
      await directoryContainsFile(
        directory,
        [".__ontobdc__", "dataset.ttl"],
      )
      || await directoryContainsFile(
        directory,
        [".__ontobdc__", "nid.ttl"],
      )
      || await directoryContainsFile(
        directory,
        ["linkset", "datapackage.json"],
      )
    );
  }

  async function collectProjectFiles(directory, prefix = "") {
    const paths = [];
    for await (const entry of directory.values()) {
      const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.kind === "directory") {
        if (
          entry.name === ".__ontobdc__"
          || entry.name === ".__onmtobdc__"
          || await isDatasetDirectory(entry)
        ) {
          continue;
        }
        paths.push(...await collectProjectFiles(entry, relativePath));
      } else {
        paths.push(relativePath);
      }
    }
    return paths.sort((left, right) => left.localeCompare(right));
  }

  function encodeCatalogPath(path) {
    return path.split("/").map(encodeURIComponent).join("/");
  }

  function makeRoCrate(filePaths) {
    const fileIds = filePaths.map(encodeCatalogPath);
    return {
      "@context": "https://w3id.org/ro/crate/1.1/context",
      "@graph": [
        {
          "@id": "ro-crate-metadata.json",
          "@type": "CreativeWork",
          about: { "@id": "./" },
          conformsTo: {
            "@id": "https://w3id.org/ro/crate/1.1",
          },
        },
        {
          "@id": "./",
          "@type": "Dataset",
          hasPart: fileIds.map((id) => ({ "@id": id })),
        },
        ...fileIds.map((id) => ({
          "@id": id,
          "@type": "File",
        })),
      ],
    };
  }

  async function synchronizeProjectManifest() {
    if (!activeContainerHandle) {
      throw new Error("Abra o projeto antes de atualizar seus arquivos.");
    }
    const filePaths = await collectProjectFiles(activeContainerHandle);
    const metadataDirectory = await activeContainerHandle.getDirectoryHandle(
      ".__ontobdc__",
    );
    const manifestHandle = await metadataDirectory.getFileHandle(
      "ro-crate-metadata.json",
      { create: true },
    );
    const writable = await manifestHandle.createWritable();
    await writable.write(
      `${JSON.stringify(makeRoCrate(filePaths), null, 2)}\n`,
    );
    await writable.close();
    return filePaths.length;
  }

  async function previewResource(row, resource) {
    const title = row.querySelector("[data-resource-preview-title]");
    const preview = row.querySelector("[data-file-preview]");
    row.dataset.selectedResource = resource.id;
    renderResourceTree(row);
    configureRelationAction(row, resource);
    title.textContent = resource.name;
    preview.replaceChildren();
    try {
      const representation = previewRepresentation(resource);
      const file = await fileFromCatalogId(representation.id);
      const mediaType = representation.encodingFormat || file.type || "";
      if (previewObjectUrl) {
        URL.revokeObjectURL(previewObjectUrl);
      }
      if (mediaType.startsWith("image/")) {
        previewObjectUrl = URL.createObjectURL(file);
        const image = document.createElement("img");
        image.src = previewObjectUrl;
        image.alt = resource.name;
        preview.appendChild(image);
      } else if (mediaType === "application/pdf") {
        previewObjectUrl = URL.createObjectURL(file);
        const frame = document.createElement("iframe");
        frame.src = previewObjectUrl;
        frame.title = representation.name;
        preview.appendChild(frame);
      } else if (/\.(msg|eml)$/i.test(resource.id)) {
        renderEmail(preview, await parseEmail(file, resource.id));
      } else if (
        mediaType.startsWith("text/")
        || /\.(txt|md|csv|json|ttl|xml)$/i.test(resource.id)
      ) {
        const text = document.createElement("pre");
        text.textContent = await file.text();
        preview.appendChild(text);
      } else {
        const metadata = document.createElement("dl");
        metadata.className = "workstream-resource-metadata";
        [["Arquivo", resource.name], ["Caminho", resource.id],
          ["Tipo", mediaType || "não informado"]].forEach(([key, value]) => {
          const term = document.createElement("dt");
          term.textContent = key;
          const description = document.createElement("dd");
          description.textContent = value;
          metadata.append(term, description);
        });
        preview.appendChild(metadata);
      }
    } catch (error) {
      clearPreview(row, `Não foi possível abrir o arquivo: ${error.message}`);
    }
  }

  function relationActionIcon(action) {
    if (action === "remove") {
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M9.5 14.5 14.5 9.5"></path>
          <path d="m7 17-1.2 1.2a3.5 3.5 0 0 1-5-5L5 9a3.5 3.5 0 0 1 5 0"></path>
          <path d="m17 7 1.2-1.2a3.5 3.5 0 0 1 5 5L19 15a3.5 3.5 0 0 1-5 0"></path>
        </svg>`;
    }
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m10 13 4-4"></path>
        <path d="m7 17-1.2 1.2a3.5 3.5 0 0 1-5-5L5 9a3.5 3.5 0 0 1 5 0l1 1"></path>
        <path d="m17 7 1.2-1.2a3.5 3.5 0 0 1 5 5L19 15a3.5 3.5 0 0 1-5 0l-1-1"></path>
      </svg>`;
  }

  function configureRelationAction(row, resource) {
    const button = row.querySelector("[data-relation-action]");
    const details = relationActionDetails(row, resource);
    if (!details) {
      button.hidden = true;
      delete button.dataset.action;
      return;
    }

    button.hidden = false;
    button.disabled = false;
    button.dataset.action = details.action;
    button.classList.toggle("is-remove", details.action === "remove");
    button.setAttribute("aria-label", details.label);
    button.title = details.label;
    button.innerHTML = relationActionIcon(details.action);
  }

  function relationActionDetails(row, resource) {
    if (!resource) {
      return null;
    }
    const view = row.dataset.activeView || "related";
    const dimensionUri = `${payload.dimensionBaseUri}/${row.dataset.dimension}`;
    const related = new Set(resourceModel.relationships[dimensionUri] || []);
    if (view === "found" && related.has(resource.id)) {
      return null;
    }
    const action = view === "related" ? "remove" : "add";
    return {
      action,
      label: action === "add"
        ? "Relacionar arquivo"
        : "Remover relação",
    };
  }

  async function resourceLinksetHandle() {
    const metadata = await activeContainerHandle.getDirectoryHandle(
      ".__ontobdc__",
    );
    const linkset = await metadata.getDirectoryHandle("linkset", {
      create: true,
    });
    return linkset.getFileHandle("WorkStreamResource.ttl", { create: true });
  }

  async function serializeRelationship(action, dimensionUri, resourceId) {
    const fileHandle = await resourceLinksetHandle();
    const currentFile = await fileHandle.getFile();
    activePyodide.globals.set(
      "relationship_request_json",
      JSON.stringify({
        action,
        dimensionUri,
        resourceId,
        turtle: await currentFile.text(),
      }),
    );
    const resultProxy = await activePyodide.runPythonAsync(`
import hashlib
import json

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, XSD

request = json.loads(relationship_request_json)
LS = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#")
graph = Graph()
if request["turtle"].strip():
    graph.parse(data=request["turtle"], format="turtle")

def endpoint_value(element):
    identifier = graph.value(element, LS.hasIdentifier)
    return (
        graph.value(identifier, LS.uri)
        or graph.value(identifier, LS.identifier)
    )

matches = []
for link in graph.subjects(RDF.type, LS.DirectedBinaryLink):
    from_element = graph.value(link, LS.hasFromLinkElement)
    to_element = graph.value(link, LS.hasToLinkElement)
    values = {
        str(value)
        for value in (
            endpoint_value(from_element),
            endpoint_value(to_element),
        )
        if value is not None
    }
    if {
        request["dimensionUri"],
        request["resourceId"],
    }.issubset(values):
        matches.append((link, from_element, to_element))

if request["action"] == "add" and not matches:
    digest = hashlib.sha256(
        (request["dimensionUri"] + "|" + request["resourceId"]).encode()
    ).hexdigest()[:24]
    base = f"urn:infobim:linkset:workstream-resource:{digest}"
    link = URIRef(base)
    dimension_element = URIRef(base + ":dimension")
    resource_element = URIRef(base + ":resource")
    dimension_identifier = URIRef(base + ":dimension-identifier")
    resource_identifier = URIRef(base + ":resource-identifier")

    graph.add((link, RDF.type, LS.DirectedBinaryLink))
    graph.add((link, LS.hasFromLinkElement, dimension_element))
    graph.add((link, LS.hasToLinkElement, resource_element))
    graph.add((dimension_element, RDF.type, LS.LinkElement))
    graph.add((dimension_element, LS.hasIdentifier, dimension_identifier))
    graph.add((dimension_identifier, RDF.type, LS.URIBasedIdentifier))
    graph.add((
        dimension_identifier,
        LS.uri,
        Literal(request["dimensionUri"], datatype=XSD.anyURI),
    ))
    graph.add((resource_element, RDF.type, LS.LinkElement))
    graph.add((resource_element, LS.hasIdentifier, resource_identifier))
    graph.add((resource_identifier, RDF.type, LS.StringBasedIdentifier))
    graph.add((
        resource_identifier,
        LS.identifier,
        Literal(request["resourceId"]),
    ))

if request["action"] == "remove":
    for link, from_element, to_element in matches:
        graph.remove((link, None, None))
        graph.remove((None, None, link))
        for element in (from_element, to_element):
            still_used = any(
                graph.subjects(LS.hasFromLinkElement, element)
            ) or any(
                graph.subjects(LS.hasToLinkElement, element)
            )
            if still_used:
                continue
            identifier = graph.value(element, LS.hasIdentifier)
            if element is not None:
                graph.remove((element, None, None))
                graph.remove((None, None, element))
            if (
                identifier is not None
                and not any(graph.subjects(LS.hasIdentifier, identifier))
            ):
                graph.remove((identifier, None, None))
                graph.remove((None, None, identifier))

graph.bind("ls", LS)
graph.serialize(format="turtle")
`);
    const turtle = String(resultProxy);
    if (resultProxy && typeof resultProxy.destroy === "function") {
      resultProxy.destroy();
    }
    return { fileHandle, turtle };
  }

  async function updateRelationship(row, resource, action) {
    if (!activeContainerHandle || !activePyodide) {
      throw new Error("Abra o projeto antes de alterar relações.");
    }
    const dimensionUri = `${payload.dimensionBaseUri}/${row.dataset.dimension}`;
    const previous = [...(resourceModel.relationships[dimensionUri] || [])];
    const related = new Set(previous);
    if (action === "add") {
      related.add(resource.id);
    } else {
      related.delete(resource.id);
    }
    resourceModel.relationships[dimensionUri] = [...related];

    try {
      const { fileHandle, turtle } = await serializeRelationship(
        action,
        dimensionUri,
        resource.id,
      );
      const writable = await fileHandle.createWritable();
      await writable.write(turtle);
      await writable.close();
    } catch (error) {
      resourceModel.relationships[dimensionUri] = previous;
      throw error;
    }
  }

  function configureResourcePanels() {
    const resourceLabels = {
      drawings: "Pranchas",
      documents: "Documentos",
      messages: "Comunicação",
    };

    document.querySelectorAll(".five-w-two-h-row").forEach((row) => {
      const panel = row.querySelector("[data-resource-panel]");
      const title = row.querySelector("[data-resource-title]");
      const toggles = row.querySelectorAll("[data-resource-toggle]");
      const tabs = row.querySelectorAll("[data-resource-view]");
      const relationAction = row.querySelector("[data-relation-action]");
      if (!panel || !title || toggles.length === 0) {
        return;
      }

      toggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
          const resourceKey = toggle.dataset.resourceToggle;
          const isOpen = (
            toggle.classList.contains("is-active")
            && !panel.hidden
          );

          toggles.forEach((candidate) => {
            candidate.classList.remove("is-active");
            candidate.setAttribute("aria-expanded", "false");
          });

          if (isOpen) {
            panel.hidden = true;
            delete row.dataset.activeResource;
            panel.removeAttribute("data-active-resource");
            clearPreview(row);
            return;
          }

          toggle.classList.add("is-active");
          toggle.setAttribute("aria-expanded", "true");
          panel.dataset.activeResource = resourceKey;
          row.dataset.activeResource = resourceKey;
          row.dataset.activeView ||= "related";
          title.textContent = resourceLabels[resourceKey] || "Recursos";
          panel.hidden = false;
          clearPreview(row);
          renderResourceTree(row);
        });
      });

      tabs.forEach((tab, tabIndex) => {
        tab.addEventListener("click", () => {
          tabs.forEach((candidate) => {
            candidate.classList.remove("is-active");
            candidate.setAttribute("aria-selected", "false");
            candidate.tabIndex = -1;
          });
          tab.classList.add("is-active");
          tab.setAttribute("aria-selected", "true");
          tab.tabIndex = 0;
          row.dataset.activeView = tab.dataset.resourceView;
          row.querySelector("[data-file-tree]").setAttribute(
            "aria-labelledby",
            tab.id,
          );
          clearPreview(row);
          renderResourceTree(row);
        });
        tab.addEventListener("keydown", (event) => {
          if (!["ArrowLeft", "ArrowRight"].includes(event.key)) {
            return;
          }
          event.preventDefault();
          const offset = event.key === "ArrowRight" ? 1 : -1;
          tabs[(tabIndex + offset + tabs.length) % tabs.length].focus();
        });
      });

      relationAction.addEventListener("click", async () => {
        const resource = resourceModel.resources.find(
          (candidate) => candidate.id === row.dataset.selectedResource,
        );
        const action = relationAction.dataset.action;
        if (!resource || !["add", "remove"].includes(action)) {
          return;
        }

        relationAction.disabled = true;
        try {
          await updateRelationship(row, resource, action);
          if (action === "remove") {
            clearPreview(row);
          } else {
            configureRelationAction(row, resource);
          }
          renderResourceTree(row);
          relationAction.title = action === "add"
            ? "Arquivo relacionado"
            : "Relação removida";
        } catch (error) {
          relationAction.disabled = false;
          relationAction.title = `Falha ao gravar relação: ${error.message}`;
          relationAction.setAttribute("aria-label", relationAction.title);
        }
      });
    });
  }

  async function openContainer() {
    openButton.disabled = true;
    setStatus("Solicitando acesso ao projeto...", "");

    try {
      if (typeof window.showDirectoryPicker !== "function") {
        throw new Error(
          "Este navegador não oferece a File System Access API. Use Microsoft Edge ou Google Chrome.",
        );
      }
      if (typeof loadPyodide !== "function") {
        throw new Error("O carregador do Pyodide não está disponível.");
      }

      const containerHandle = await acquireContainerHandle();
      activeContainerHandle = containerHandle;
      document.getElementById("project-title").textContent =
        containerHandle.name || payload.projectName || "";
      setStatus(`Carregando o projeto “${containerHandle.name}”...`, "");
      const pyodide = await loadPyodide();
      activePyodide = pyodide;
      const mountPath = `/container_${Date.now()}`;
      const metadataHandle = await containerHandle.getDirectoryHandle(
        ".__ontobdc__",
      );
      const payloadHandle = await containerHandle.getDirectoryHandle("payload");
      pyodide.FS.mkdirTree(mountPath);
      await pyodide.mountNativeFS(
        `${mountPath}/.__ontobdc__`,
        metadataHandle,
      );
      await pyodide.mountNativeFS(`${mountPath}/payload`, payloadHandle);
      await pyodide.loadPackage("micropip");
      await pyodide.runPythonAsync(`
import micropip
await micropip.install(["openpyxl", "rdflib"])
`);
      pyodide.globals.set("view_payload_json", JSON.stringify(payload));
      pyodide.globals.set("container_mount_path", mountPath);
      const resultProxy = await pyodide.runPythonAsync(`
import json
from pathlib import Path
from urllib.parse import unquote

from openpyxl import load_workbook
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

payload = json.loads(view_payload_json)
container = Path(container_mount_path)
datapackage_path = container / payload["datapackagePath"]
linkset_path = container / payload["linksetPath"]
resource_linkset_path = container / payload["resourceLinksetPath"]
ro_crate_path = container / payload["roCratePath"]
file_display_ontology_path = container / payload["fileDisplayOntologyPath"]

datapackage = json.loads(datapackage_path.read_text(encoding="utf-8"))
resource = next(
    item
    for item in datapackage.get("resources", [])
    if item.get("name") == "work_stream"
)
workbook_path = (datapackage_path.parent / resource["path"]).resolve()
worksheet_name = (
    resource.get("dialect", {})
    .get("excel", {})
    .get("sheet", "WorkStream")
)

LS = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#")
linkset = Graph()
linkset.parse(linkset_path, format="turtle")
mappings = {}
for link in linkset.subjects(RDF.type, LS.DirectedBinaryLink):
    from_element = linkset.value(link, LS.hasFromLinkElement)
    to_element = linkset.value(link, LS.hasToLinkElement)
    from_identifier = linkset.value(from_element, LS.hasIdentifier)
    to_identifier = linkset.value(to_element, LS.hasIdentifier)
    column = linkset.value(from_identifier, LS.identifier)
    facade_field = linkset.value(to_identifier, LS.uri)
    if isinstance(column, Literal) and facade_field is not None:
        mappings[str(column)] = str(facade_field)

workbook = load_workbook(workbook_path, data_only=True, read_only=True)
worksheet = workbook[worksheet_name]
headers = [str(cell.value or "").strip() for cell in worksheet[1]]
record = None
for values in worksheet.iter_rows(min_row=2, values_only=True):
    candidate = dict(zip(headers, values))
    if str(candidate.get("GlobalId") or "").strip() == payload["elementId"]:
        record = candidate
        break
workbook.close()

if record is None:
    raise ValueError(
        f"WorkStream not found in workbook: {payload['elementId']}"
    )
if any(field not in mappings for field in headers):
    missing = sorted(field for field in headers if field not in mappings)
    raise ValueError(
        "The ICDD linkset does not map workbook fields: " + ", ".join(missing)
    )

def values(item, key):
    value = item.get(key)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def text_values(item, *keys):
    result = []
    for key in keys:
        for value in values(item, key):
            if isinstance(value, dict):
                value = value.get("@id") or value.get("@value")
            if value is not None:
                result.append(str(value))
    return result

FILE_DISPLAY = Namespace(
    "https://w3id.org/ontobdc/ontology/file-display#"
)
file_display_graph = Graph()
file_display_graph.parse(file_display_ontology_path, format="turtle")
display_profiles = []
for profile in file_display_graph.subjects(
    RDF.type,
    FILE_DISPLAY.FileDisplayProfile,
):
    category = file_display_graph.value(
        profile,
        FILE_DISPLAY.displayCategory,
    )
    if category is None:
        continue
    display_profiles.append({
        "category": str(category),
        "mimeTypes": {
            str(value).strip().lower()
            for value in file_display_graph.objects(
                profile,
                FILE_DISPLAY.acceptedMimeType,
            )
            if str(value).strip()
        },
        "extensions": {
            str(value).strip().lower()
            for value in file_display_graph.objects(
                profile,
                FILE_DISPLAY.acceptedExtension,
            )
            if str(value).strip()
        },
    })

def category_for(item, resource_id):
    formats = {
        value.strip().lower()
        for value in text_values(item, "encodingFormat")
        if value.strip()
    }
    extension = Path(unquote(resource_id)).suffix.lower()
    for profile in display_profiles:
        if (
            formats.intersection(profile["mimeTypes"])
            or extension in profile["extensions"]
        ):
            return profile["category"]
    return None

try:
    ro_crate_text = ro_crate_path.read_text(encoding="utf-8").strip()
    ro_crate = json.loads(ro_crate_text) if ro_crate_text else {"@graph": []}
except FileNotFoundError:
    ro_crate = {"@graph": []}

catalog_resources = []
resources = []
for item in ro_crate.get("@graph", []):
    resource_id = item.get("@id")
    types = set(text_values(item, "@type"))
    if not resource_id or resource_id in (".", "./"):
        continue
    if not types.intersection({
        "File", "MediaObject", "DigitalDocument",
        "CreativeWork", "Message", "EmailMessage",
    }):
        continue
    names = text_values(item, "name")
    formats = text_values(item, "encodingFormat")
    category = category_for(item, resource_id)
    display_parts = [
        unquote(part)
        for part in resource_id.split("/")
        if part
    ]
    catalog_resource = {
        "id": resource_id,
        "name": (
            unquote(names[0])
            if names
            else unquote(Path(resource_id).name)
        ),
        "displayParts": display_parts,
        "encodingFormat": formats[0] if formats else "",
    }
    catalog_resources.append(catalog_resource)
    if category is not None:
        resources.append({
            **catalog_resource,
            "category": category,
        })

relationships = {}
if resource_linkset_path.exists():
    resource_linkset = Graph()
    resource_linkset.parse(resource_linkset_path, format="turtle")
    resource_ids = {item["id"] for item in resources}

    def endpoint_value(element):
        identifier = resource_linkset.value(element, LS.hasIdentifier)
        return (
            resource_linkset.value(identifier, LS.uri)
            or resource_linkset.value(identifier, LS.identifier)
        )

    for link in resource_linkset.subjects(RDF.type, LS.DirectedBinaryLink):
        endpoints = [
            endpoint_value(resource_linkset.value(link, LS.hasFromLinkElement)),
            endpoint_value(resource_linkset.value(link, LS.hasToLinkElement)),
        ]
        endpoint_strings = [str(value) for value in endpoints if value is not None]
        dimension_uri = next(
            (
                value for value in endpoint_strings
                if value.startswith(payload["dimensionBaseUri"] + "/")
            ),
            None,
        )
        resource_id = next(
            (value for value in endpoint_strings if value in resource_ids),
            None,
        )
        if dimension_uri and resource_id:
            relationships.setdefault(dimension_uri, []).append(resource_id)

json.dumps(
    {
        "record": record,
        "mappings": mappings,
        "resources": resources,
        "catalogResources": catalog_resources,
        "relationships": relationships,
        "workbookPath": str(workbook_path),
        "linksetPath": str(linkset_path),
    },
    ensure_ascii=False,
)
`);
      const result = JSON.parse(String(resultProxy));
      if (resultProxy && typeof resultProxy.destroy === "function") {
        resultProxy.destroy();
      }
      renderWorkStream(result.record);
      resourceModel = {
        resources: result.resources || [],
        catalogResources: result.catalogResources || [],
        relationships: result.relationships || {},
      };
      document.querySelectorAll(".five-w-two-h-row").forEach((row) => {
        if (row.dataset.activeResource) {
          renderResourceTree(row);
        }
      });
      setStatus(
        `Projeto aberto: ${containerHandle.name}. Dados carregados.`,
        "is-ready",
      );
      openButton.textContent = "Reabrir projeto";
      updateButton.disabled = false;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(
        message.includes("datapackage.json")
          ? "O projeto selecionado não possui um datapackage.json acessível."
          : message,
        "is-error",
      );
    } finally {
      openButton.disabled = false;
    }
  }

  async function updateProject() {
    updateButton.disabled = true;
    openButton.disabled = true;
    setStatus("Atualizando os arquivos do projeto...", "");
    try {
      const fileCount = await synchronizeProjectManifest();
      setStatus(
        `${fileCount} arquivo(s) catalogado(s). Recarregando o projeto...`,
        "",
      );
      await openContainer();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(message, "is-error");
    } finally {
      openButton.disabled = false;
      updateButton.disabled = !activeContainerHandle;
    }
  }

  openButton.addEventListener("click", openContainer);
  updateButton.addEventListener("click", updateProject);
  configureResourcePanels();
}());
