from typing import Any, Dict

from infobim.a3.domain.port.machine import A3LlmSuggestionProcessStatePort


class A3LlmSuggestionProcessState(A3LlmSuggestionProcessStatePort):
    UNDEFINED = "__undefined__"
    CONTAINER_BOUND = "__container_bound__"
    RO_CRATE_LOADED = "__ro_crate_loaded__"
    FILES_ENUMERATED = "__files_enumerated__"
    LLM_EVALUATED = "__llm_evaluated__"
    SUGGESTIONS_SAVED = "__suggestions_saved__"

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, Dict[Any, str]] = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.CONTAINER_BOUND: "Container Bound",
                self.RO_CRATE_LOADED: "RO-Crate Loaded",
                self.FILES_ENUMERATED: "Files Enumerated",
                self.LLM_EVALUATED: "LLM Evaluated",
                self.SUGGESTIONS_SAVED: "Suggestions Saved",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.CONTAINER_BOUND: "Container Vinculado",
                self.RO_CRATE_LOADED: "RO-Crate Carregado",
                self.FILES_ENUMERATED: "Arquivos Enumerados",
                self.LLM_EVALUATED: "Avaliado pelo LLM",
                self.SUGGESTIONS_SAVED: "Sugestões Salvas",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, Dict[Any, str]] = {
            "en": {
                self.UNDEFINED: "Initial state before the command parameters are classified.",
                self.CONTAINER_BOUND: "The requested project, target BIM element and target dimension-property were bound to the execution context.",
                self.RO_CRATE_LOADED: "The container RO-Crate manifest was loaded and validated against the on-disk file listing.",
                self.FILES_ENUMERATED: "Every file tracked by the RO-Crate has been enriched with basic metadata and deduplicated.",
                self.LLM_EVALUATED: "Every enumerated file was evaluated through Claude Haiku/Sonnet against the target dimension-property.",
                self.SUGGESTIONS_SAVED: "Accepted LLM suggestions were persisted in the container for rendering on the Suggested Files screen.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da classificacao dos parametros do comando.",
                self.CONTAINER_BOUND: "O projeto solicitado, o elemento BIM alvo e a propriedade de dimensao alvo foram vinculados ao contexto de execucao.",
                self.RO_CRATE_LOADED: "O manifesto RO-Crate do container foi carregado e validado contra a lista de arquivos em disco.",
                self.FILES_ENUMERATED: "Cada arquivo rastreado pelo RO-Crate foi enriquecido com metadados basicos e deduplicado.",
                self.LLM_EVALUATED: "Cada arquivo enumerado foi avaliado por Claude Haiku/Sonnet contra a propriedade de dimensao alvo.",
                self.SUGGESTIONS_SAVED: "As sugestoes aceitas pelo LLM foram persistidas no container para renderizacao na tela de Arquivos Sugeridos.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "A3LlmSuggestionProcessState":
        normalized: str = str(state or "").strip().upper()
        if not normalized:
            raise ValueError(f"Empty A3 suggestion state: {state!r}")
        return getattr(A3LlmSuggestionProcessState, normalized)
