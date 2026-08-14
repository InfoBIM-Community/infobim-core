from enum import Enum


class ElementImportProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    UPDATED = "__updated__"
    IDENTIFIED = "__identified__"
    EXTRACTED = "__extracted__"
    SPATIALIZED = "__spatialized__"
    LOCALIZED = "__localized__"
    ARRANGED = "__arranged__"
    GROUNDED = "__grounded__"
    SEMANTICIZED = "__semanticized__"
    INSTANCE_DRAFTED = "__instance_drafted__"
    INSTANCE_PARSED = "__instance_parsed__"
    INSTANTIATED = "__instantiated__"
    GENERATED = "__generated__"
    LINKED = "__linked__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.UPDATED: "Updated",
                self.IDENTIFIED: "Identified",
                self.EXTRACTED: "Extracted",
                self.SPATIALIZED: "Spatialized",
                self.LOCALIZED: "Localized",
                self.ARRANGED: "Arranged",
                self.GROUNDED: "Grounded",
                self.SEMANTICIZED: "Semanticized",
                self.INSTANCE_DRAFTED: "Instance Drafted",
                self.INSTANCE_PARSED: "Instance Parsed",
                self.INSTANTIATED: "Instantiated",
                self.GENERATED: "Generated",
                self.LINKED: "Linked",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.UPDATED: "Atualizado",
                self.IDENTIFIED: "Identificado",
                self.EXTRACTED: "Extraido",
                self.SPATIALIZED: "Espacializado",
                self.LOCALIZED: "Localizado",
                self.ARRANGED: "Arranjado",
                self.GROUNDED: "Ancorado",
                self.SEMANTICIZED: "Semanticizado",
                self.INSTANCE_DRAFTED: "Rascunho de Instancias",
                self.INSTANCE_PARSED: "Instancia Interpretada",
                self.INSTANTIATED: "Materializado",
                self.GENERATED: "Gerado",
                self.LINKED: "Linked",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before any import learning artifact is materialized.",
                self.UPDATED: "The target project container RO-Crate metadata is updated and synchronized.",
                self.IDENTIFIED: "The import source produced the __identified__.json artifact.",
                self.EXTRACTED: "The import source produced the __extracted__.md artifact.",
                self.SPATIALIZED: "The import source produced the __spatialized__.json artifact.",
                self.LOCALIZED: "The import source produced the __localized__.json artifact.",
                self.ARRANGED: "The import source produced the __arranged__.json artifact.",
                self.GROUNDED: "The import source produced the __grounded__.json artifact.",
                self.SEMANTICIZED: "The import source produced the __semanticized__.json artifact.",
                self.INSTANCE_DRAFTED: "The import source produced the __instance_drafted__.json artifact.",
                self.INSTANCE_PARSED: "The import source produced the __instance_parsed__.json artifact.",
                self.INSTANTIATED: "The import source produced the __instantiated__.json artifact.",
                self.GENERATED: "The import source produced the __generated__.json artifact.",
                self.LINKED: "The import source produced the __linked__.json artifact.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes de qualquer artefato do import ser materializado.",
                self.UPDATED: "O container do projeto esta atualizado e com o RO-Crate sincronizado.",
                self.IDENTIFIED: "A fonte do import produziu o artefato __identified__.json.",
                self.EXTRACTED: "A fonte do import produziu o artefato __extracted__.md.",
                self.SPATIALIZED: "A fonte do import produziu o artefato __spatialized__.json.",
                self.LOCALIZED: "A fonte do import produziu o artefato __localized__.json.",
                self.ARRANGED: "A fonte do import produziu o artefato __arranged__.json.",
                self.GROUNDED: "A fonte do import produziu o artefato __grounded__.json.",
                self.SEMANTICIZED: "A fonte do import produziu o artefato __semanticized__.json.",
                self.INSTANCE_DRAFTED: "A fonte do import produziu o artefato __instance_drafted__.json.",
                self.INSTANCE_PARSED: "A fonte do import produziu o artefato __instance_parsed__.json.",
                self.INSTANTIATED: "A fonte do import produziu o artefato __instantiated__.json.",
                self.GENERATED: "A fonte do import produziu o artefato __generated__.json.",
                self.LINKED: "A fonte do import produziu o artefato __linked__.json.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ElementImportProcessState":
        return getattr(ElementImportProcessState, state.upper())
