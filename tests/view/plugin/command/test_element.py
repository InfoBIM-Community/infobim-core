from infobim.cli.domain.context import InfoBIMCliContext
from infobim.view.plugin.command.element import ViewElementCommand
from ontobdc.cli.domain.request.command import CliCommandRequest


def test_accepts_project_element_view_command() -> None:
    assert ViewElementCommand.accepts(
        [
            "view",
            "--project",
            "project-123",
            "--element",
            "workstream-456",
        ]
    )


def test_generates_live_workstream_view(
    tmp_path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    context = InfoBIMCliContext(
        root_path=str(tmp_path),
        parameters={"project_id": "project-123"},
    )
    request = CliCommandRequest(
        logical_component="view",
        component_action="element",
        command_args=[
            "--project",
            "project-123",
            "--element",
            "workstream-456",
        ],
        context=context,
    )
    command = ViewElementCommand(request)
    monkeypatch.setattr(
        ViewElementCommand,
        "_list_projects",
        lambda self, storage_file: [
            {
                "project_id": "project-123",
                "name": "Projeto teste",
                "path": str(project_path),
            }
        ],
    )
    monkeypatch.setattr(
        "infobim.view.adapter.html.webbrowser.open",
        lambda uri: True,
    )
    monkeypatch.setattr(
        "infobim.view.plugin.command.element.get_storage_file",
        lambda root_path: str(tmp_path / "storage.ttl"),
    )
    (tmp_path / "storage.ttl").write_text("", encoding="utf-8")

    assert command.check()
    response = command.run()

    assert response.content["element"] == "workstream-456"
    output_file = (
        project_path / "payload" / "view" / "workstream-456.html"
    )
    assert response.content["output_file"] == str(output_file)
    html = output_file.read_text(encoding="utf-8")
    assert "showDirectoryPicker" not in html
    assert "workstream_5w2h.js" in html
    assert "email_reader.js" in html
    assert "../../.__ontobdc__/asset/infobim-view" in html
    assert 'id="project-title">Projeto teste</span>' in html
    assert "Container semântico" not in html
    assert "five-w-two-h-index" not in html
    assert "workstream-status-bar" in html
    assert "Não carregado" in html
    assert "Abrir projeto" in html
    assert 'id="update-project"' in html
    assert "Atualizar arquivos do projeto" in html
    assert "Abrir container" not in html
    assert html.count('data-resource-toggle="drawings"') == 7
    assert html.count('data-resource-toggle="documents"') == 7
    assert html.count('data-resource-toggle="messages"') == 7
    assert html.count("Comunicação") == 7
    assert "Mensagens" not in html
    assert html.count("data-resource-panel") == 7
    assert html.count('data-resource-view="related"') == 7
    assert html.count('data-resource-view="suggested"') == 7
    assert html.count('data-resource-view="found"') == 7
    assert html.count("data-relation-action") == 7
    assert "Relacionadas" in html
    assert "Sugeridas" in html
    assert "Encontradas" in html
    assert 'type="search"' not in html
    assert (
        '"dimensionBaseUri": '
        '"urn:infobim:workstream/workstream-456/dimension"'
    ) in html
    assert "urn:infobim:workstream:workstream-456" not in html

    runtime_script = (
        project_path
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
        / "js"
        / "workstream_5w2h.js"
    ).read_text(encoding="utf-8")
    assert "resolveContainerHandle" in runtime_script
    assert 'getDirectoryHandle(".__ontobdc__")' in runtime_script
    assert 'getFileHandle("datapackage.json")' in runtime_script
    assert "await deleteStoredHandle()" in runtime_script
    assert "metadataHandle" in runtime_script
    assert "payloadHandle" in runtime_script
    assert '`${mountPath}/.__ontobdc__`' in runtime_script
    assert '`${mountPath}/payload`' in runtime_script
    assert '"Carregado"' in runtime_script
    assert '"Erro"' in runtime_script
    assert '"Reabrir projeto"' in runtime_script
    assert "configureResourcePanels" in runtime_script
    assert 'toggle.classList.contains("is-active")' in runtime_script
    assert "panel.hidden = true" in runtime_script
    assert "panel.hidden = false" in runtime_script
    assert 'item.get("name") == "work_stream"' in runtime_script
    assert "LS.DirectedBinaryLink" in runtime_script
    assert 'container / payload["roCratePath"]' in runtime_script
    assert 'item.get("@id")' in runtime_script
    assert 'ro_crate.get("@graph", [])' in runtime_script
    assert 'payload["dimensionBaseUri"] + "/"' in runtime_script
    assert "resource_linkset_path.exists()" in runtime_script
    assert "Nenhum arquivo sugerido." in runtime_script
    assert "Nenhum arquivo encontrado." in runtime_script
    assert "Nenhum arquivo catalogado no RO-Crate." not in runtime_script
    assert "fileDisplayOntologyPath" in html
    assert "FILE_DISPLAY.FileDisplayProfile" in runtime_script
    assert "FILE_DISPLAY.acceptedMimeType" in runtime_script
    assert "FILE_DISPLAY.acceptedExtension" in runtime_script
    assert "unquote(part)" in runtime_script
    display_ontology = (
        project_path
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
        / "ontology"
        / "file_display.ttl"
    ).read_text(encoding="utf-8")
    assert ':displayCategory "drawings"' in display_ontology
    assert '".dwg"' in display_ontology
    assert ':displayCategory "messages"' in display_ontology
    assert '".msg"' in display_ontology
    assert '".bak"' not in display_ontology
    email_reader = (
        project_path
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
        / "js"
        / "email_reader.js"
    )
    assert email_reader.exists()
    assert "InfoBIMEmailReader" in email_reader.read_text(encoding="utf-8")
    assert "parseMsg" in runtime_script
    assert "parseEml" in runtime_script
    assert "renderEmail" in runtime_script
    assert 'messages: "Comunicação"' in runtime_script
    assert 'document.createElement("details")' in runtime_script
    assert 'document.createElement("summary")' in runtime_script
    assert "workstream-tree-relation-action" in runtime_script
    assert 'row.querySelector("[data-relation-action]").click()' in (
        runtime_script
    )
    assert "getFileHandle(cleanPath.at(-1))" in runtime_script
    assert "previewRepresentation(resource)" in runtime_script
    assert "replace(/\\.dwg$/i, extension)" in runtime_script
    assert 'for (const extension of [".pdf", ".png"])' in runtime_script
    assert "resourceModel.catalogResources.find(" in runtime_script
    assert "fileFromCatalogId(representation.id)" in runtime_script
    assert "collectProjectFiles(activeContainerHandle)" in runtime_script
    assert "makeRoCrate(filePaths)" in runtime_script
    assert '"ro-crate-metadata.json"' in runtime_script
    assert 'entry.name === ".__ontobdc__"' in runtime_script
    assert '["linkset", "datapackage.json"]' in runtime_script
    assert "await manifestHandle.createWritable()" in runtime_script
    assert "synchronizeProjectManifest()" in runtime_script
    assert "catalogResources" in runtime_script
    assert '{ mode: "readwrite" }' in runtime_script
    assert 'mode: "readwrite"' in runtime_script
    assert 'getFileHandle("WorkStreamResource.ttl", { create: true })' in (
        runtime_script
    )
    assert "serializeRelationship" in runtime_script
    assert "LS.DirectedBinaryLink" in runtime_script
    assert "LS.URIBasedIdentifier" in runtime_script
    assert "datatype=XSD.anyURI" in runtime_script
    assert "LS.StringBasedIdentifier" in runtime_script
    assert "await fileHandle.createWritable()" in runtime_script
    assert "await writable.write(turtle)" in runtime_script
    assert "updateRelationship(row, resource, action)" in runtime_script
    assert 'action === "remove"' in runtime_script
    assert 'if (!resource || view === "suggested")' not in runtime_script
