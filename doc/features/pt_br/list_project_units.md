# Capability: Unidades do Projeto

- ID: org.infobim.base.capability.list_project_units
- Nome: Unidades do Projeto
- Versão: 0.1.0
- Arquivo: [list_project_units.py](../../../src/plugin/capability/base/list_project_units.py)
- Categoria: Base / Projeto
- Responsável: InfoBIM Team

## Objetivo
- Detectar as unidades do projeto IFC e fornecer fator de escala de comprimento para metros.
- Listar todas as unidades ligadas a IfcProject.UnitsInContext (SI, Base de Conversão, Derivadas).

## Entradas
- ifc_path (string, obrigatório): Caminho absoluto para o arquivo IFC

## Saídas
- length_unit (string): Nome da unidade de comprimento
- length_scale (number): Fator de escala para metros
- schema (string): Versão IFC
- units (array): Todas as entradas de UnitsInContext com:
  - unit_type
  - name
  - prefix
  - kind
  - elements_count (para IfcDerivedUnit)

## CLI
```bash
./infobim run org.infobim.base.capability.project_units ./test/data/ifc/rede_esgoto_projeto_existente.ifc
```

## Referências de código
- Implementação: [list_project_units.py](../../../src/plugin/capability/base/list_project_units.py)
