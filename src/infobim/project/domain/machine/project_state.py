from ontobdc.storage.domain.port.machine import ContainerCreateProcessStatePort


class ContainerCreateProcessState(ContainerCreateProcessStatePort):
    """
    Enum representing the possible states of the InfoBIM storage container creation process.
    """

    UNDEFINED = "__undefined__"
    INVALID_PATH = "__invalid_path__"
    INFOBIM_CONFIG_READY = "__infobim_config_ready__"
    DIRECTORY_READY = "__directory_ready__"
    CONTAINER_METADATA_READY = "__container_metadata_ready__"
    CONTAINER_STORAGE_INDEX_READY = "__container_storage_index_ready__"
    CONTAINER_MANIFEST_SYNCED = "__container_manifest_synced__"
    PROJECT_READY = "__project_ready__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.INVALID_PATH: "Invalid Path",
                self.INFOBIM_CONFIG_READY: "InfoBIM Config Ready",
                self.DIRECTORY_READY: "Directory Ready",
                self.CONTAINER_METADATA_READY: "Container Metadata Ready",
                self.CONTAINER_STORAGE_INDEX_READY: "Container Storage Index Ready",
                self.CONTAINER_MANIFEST_SYNCED: "Container Manifest Synced",
                self.PROJECT_READY: "Project Ready",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.INVALID_PATH: "Caminho Invalido",
                self.INFOBIM_CONFIG_READY: "Config do InfoBIM Pronta",
                self.DIRECTORY_READY: "Diretorio Pronto",
                self.CONTAINER_METADATA_READY: "Metadados do Container Prontos",
                self.CONTAINER_STORAGE_INDEX_READY: "Indice de Storage do Container Pronto",
                self.CONTAINER_MANIFEST_SYNCED: "Manifesto do Container Sincronizado",
                self.PROJECT_READY: "Projeto Pronto",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the target container directory exists.",
                self.INVALID_PATH: "The target path points to an existing file and cannot be used as a container directory.",
                self.INFOBIM_CONFIG_READY: "The project root contains a valid InfoBIM configuration ready for the storage container creation flow.",
                self.DIRECTORY_READY: "The target container directory exists and is ready for the next creation steps.",
                self.CONTAINER_METADATA_READY: "The container metadata file exists and contains a valid data container description without requiring datasets.",
                self.CONTAINER_STORAGE_INDEX_READY: "The storage index entry for the container matches the container metadata file and is synchronized.",
                self.CONTAINER_MANIFEST_SYNCED: "The container manifest file exists and lists all container files excluding marker and dataset directories.",
                self.PROJECT_READY: "The .__ontobdc__/__infobim__/project.ttl file exists in the target container and contains the basic project information.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da existencia do diretorio alvo do container.",
                self.INVALID_PATH: "O caminho alvo aponta para um arquivo existente e nao pode ser usado como diretorio de container.",
                self.INFOBIM_CONFIG_READY: "A raiz do projeto contem uma configuracao valida do InfoBIM pronta para o fluxo de criacao do container.",
                self.DIRECTORY_READY: "O diretorio alvo do container existe e esta pronto para as proximas etapas da criacao.",
                self.CONTAINER_METADATA_READY: "O arquivo de metadados do container existe e contem uma descricao valida do data container sem exigir datasets.",
                self.CONTAINER_STORAGE_INDEX_READY: "A entrada do container no indice de storage esta sincronizada com o arquivo de metadados do container.",
                self.CONTAINER_MANIFEST_SYNCED: "O manifesto do container existe e lista todos os arquivos do container exceto diretorios de marker e datasets.",
                self.PROJECT_READY: "O arquivo .__ontobdc__/__infobim__/project.ttl existe no container alvo e contem as informacoes basicas do projeto.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ContainerCreateProcessState":
        return getattr(ContainerCreateProcessState, state.upper())
