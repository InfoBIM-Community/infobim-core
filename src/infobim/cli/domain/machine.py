from ontobdc.cli.domain.port.machine import CliInitProcessStatePort


class InfoBIMInitProcessState(CliInitProcessStatePort):
    UNDEFINED = "__undefined__"
    ENGINE_READY = "__engine_ready__"
    ONTOBDC_DIRECTORY_READY = "__ontobdc_directory_ready__"
    STORAGE_INDEX_HEALTHY = "__storage_index_healthy__"
    EXECUTION_CONTEXT_HEALTHY = "__execution_context_healthy__"
    CONFIG_ADAPTER_READY = "__config_adapter_ready__"
    INFOBIM_CONFIG_READY = "__infobim_config_ready__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.ENGINE_READY: "Engine Ready",
                self.ONTOBDC_DIRECTORY_READY: "OntoBDC Directory Ready",
                self.STORAGE_INDEX_HEALTHY: "Storage Index Healthy",
                self.EXECUTION_CONTEXT_HEALTHY: "Execution Context Healthy",
                self.CONFIG_ADAPTER_READY: "Config Adapter Ready",
                self.INFOBIM_CONFIG_READY: "InfoBIM Config Ready",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.ENGINE_READY: "Engine Pronto",
                self.ONTOBDC_DIRECTORY_READY: "Diretorio OntoBDC Pronto",
                self.STORAGE_INDEX_HEALTHY: "Indice de Storage Saudavel",
                self.EXECUTION_CONTEXT_HEALTHY: "Contexto de Execucao Saudavel",
                self.CONFIG_ADAPTER_READY: "Adapter de Config Pronto",
                self.INFOBIM_CONFIG_READY: "Config do InfoBIM Pronta",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before any init step is executed.",
                self.ENGINE_READY: "The configured engine is available in the project configuration.",
                self.ONTOBDC_DIRECTORY_READY: "The command target directory contains the .__ontobdc__ directory.",
                self.STORAGE_INDEX_HEALTHY: "The storage.ttl file exists and conforms to the bootstrap checks.",
                self.EXECUTION_CONTEXT_HEALTHY: "The context.ttl file exists and conforms to the bootstrap checks.",
                self.CONFIG_ADAPTER_READY: "The config.yaml file exists and conforms to the bootstrap config contract.",
                self.INFOBIM_CONFIG_READY: "The __infobim__/config.yaml file exists and conforms to the InfoBIM bootstrap contract.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da execucao de qualquer etapa do init.",
                self.ENGINE_READY: "O engine configurado esta disponivel na configuracao do projeto.",
                self.ONTOBDC_DIRECTORY_READY: "O diretorio alvo do comando contem o diretorio .__ontobdc__.",
                self.STORAGE_INDEX_HEALTHY: "O arquivo storage.ttl existe e esta conforme com os checks de bootstrap.",
                self.EXECUTION_CONTEXT_HEALTHY: "O arquivo context.ttl existe e esta conforme com os checks de bootstrap.",
                self.CONFIG_ADAPTER_READY: "O arquivo config.yaml existe e esta conforme com o contrato de bootstrap de config.",
                self.INFOBIM_CONFIG_READY: "O arquivo __infobim__/config.yaml existe e esta conforme com o contrato de bootstrap do InfoBIM.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "InfoBIMInitProcessState":
        return getattr(InfoBIMInitProcessState, state.upper())
