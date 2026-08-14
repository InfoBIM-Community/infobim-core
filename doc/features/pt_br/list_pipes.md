# Capability: List Pipes

- ID: org.infobim.base.capability.list_pipes  
- Nome: List Pipes  
- Versão: 0.1.0  
- Arquivo: [list_pipes.py](../../../src/plugin/capability/distribution/list_pipes.py)  
- Categoria: Distribuição / Fluxo  
- Responsável: Elias M. P. Junior

## Objetivo
- Extrair e listar segmentos de tubo com dados geométricos mínimos e de propriedades: DN, comprimento e cotas inicial/final (Z).  
- Suporta ambos IFC4 (IfcPipeSegment) e IFC2X3 (IfcFlowSegment).  
- Opcionalmente, sugere dimensionamento via UHC/NBR8160 quando ativado o modo de sugestão.

## Compatibilidade IFC
- IFC4: IfcPipeSegment  
- IFC2X3: IfcFlowSegment  
- Detecção automática de unidade para DN (mm vs m) e cálculo de comprimento/elevações a partir de representação Axis/Body.

## Entradas
- ifc_path (string, obrigatório): Caminho absoluto para o arquivo IFC  
- materials (boolean, opcional, default=false): Incluir informação de material na listagem  
- uhc-sizing-suggest (boolean, opcional, default=false): Ativa sugestão de dimensionamento por UHC (somente leitura)  
- org.ontobdc.common.lang.code (string, enum: en, pt_BR, default: en): Idioma para mensagens e colunas

Referência de schema: [ListPipesCapability.METADATA.input_schema](../../../src/plugin/capability/distribution/list_pipes.py)

## Saídas
- org.ontobdc.aeco.distribution.flow.pipe.list.count (integer): Total de tubos encontrados  
- org.ontobdc.aeco.distribution.flow.pipe.list (collection): Lista de objetos com:
  - guid (string)  
  - name (string)  
  - dn (number, em mm)  
  - material (string)  
  - z_start (number, em metros)  
  - z_end (number, em metros)  
  - length (number, em metros)

Quando uhc-sizing-suggest=true, inclui:  
- org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggestions (array): sugestões por segmento (guid, name, suggested_dn, suggested_slope, accumulated_uhc)
- events: ["org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested"]

Referência de schema: [ListPipesCapability.METADATA.output_schema](../../../src/plugin/capability/distribution/list_pipes.py)

## Eventos
- Sucesso:  
  - org.infobim.base.capability.list_pipes.empty  
  - org.infobim.base.capability.list_pipes.all  
  - org.infobim.base.capability.list_pipes.many  
  - org.infobim.base.capability.list_pipes.paginated
- Falha:  
  - org.infobim.base.capability.list_pipes.error
- Sizing UHC (quando sugerido):  
  - org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested

Referência: [ListPipesCapability.METADATA.events](../../../src/plugin/capability/distribution/list_pipes.py)

## Requisições internas
- Materiais (condicional: materials=true):  
  - id: org.infobim.base.capability.list_material  
  - type: collection  
- Dimensionamento UHC (condicional: uhc-sizing-suggest=true):  
  - id: org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc  
  - type: process

Referência: [ListPipesCapability.METADATA.request](../../../src/plugin/capability/distribution/list_pipes.py)

## Comportamento
- Leitura do IFC via ifcopenshell; detecção de unidade para conversões.  
- Extração de DN por Psets padrão e heurística de unidade (m → mm).  
- Geometria: tentativa Axis (Polyline) e fallback Body (ExtrudedAreaSolid) para comprimento e Z inicial/final.  
- Ordenação de saída: DN desc e Nome asc.  
- Modo UHC: aciona UHCSizingCapability para analisar rede e gerar sugestões por segmento.

## CLI
- ID: org.infobim.base.capability.list_pipes  
- Estratégia CLI: ListPipesCliStrategy (suporta colunas condicionais e i18n)

### Execução básica
```bash
./infobim run org.infobim.base.capability.list_pipes ./test/data/ifc/rede_esgoto_projeto_existente.ifc --lang pt_BR
```

### Incluir materiais
```bash
./infobim run org.infobim.base.capability.list_pipes ./test/data/ifc/rede_esgoto_projeto_existente.ifc --materials --lang pt_BR
```

### Sugestões de dimensionamento UHC
```bash
./infobim run org.infobim.base.capability.list_pipes ./test/data/ifc/rede_esgoto_projeto_existente.ifc --uhc-sizing-suggest --lang pt_BR
```

## Integração UHC
- UHCSizingCapability (pacote distribution/uhc_sizing) carrega tabelas de NBR8160 do próprio pacote e analisa a rede para sugerir DN mínimo e declividade.  
- Saída de sugestões inclui guid, name, suggested_dn, suggested_slope, accumulated_uhc.  
- Evento org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested é emitido em caso de sucesso.

## Erros comuns
- Arquivo IFC não encontrado: verificar caminho absoluto em ifc_path.  
- IFC sem eixos/geom. adequada: a capacidade tenta fallbacks, mas pode retornar comprimentos/cotas parciais.  
- Tabelas UHC ausentes: UHCSizingCapability usa dados empacotados em distribution/uhc_sizing/data.

## Referências de código
- Capability: [list_pipes.py](../../../src/plugin/capability/distribution/list_pipes.py)  
- Sizing UHC: [uhc_sizing/__init__.py](../../../src/plugin/capability/distribution/uhc_sizing/__init__.py), [analyzer.py](../../../src/plugin/capability/distribution/uhc_sizing/analyzer.py), [tables.py](../../../src/plugin/capability/distribution/uhc_sizing/tables.py)
