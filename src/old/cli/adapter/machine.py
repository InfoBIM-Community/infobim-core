from pathlib import Path
from typing import Type

from infobim.cli.domain.machine import InfoBIMInitProcessState
from infobim.cli.plugin.check.has_valid_engine.check import main as check_engine
from infobim.cli.plugin.check.has_valid_infobim_config.check import main as check_infobim_config
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.machine import (
    CliInitProcessStatePort,
    CliInitStateEvaluatorPort,
)
from ontobdc.cli.plugin.check.has_valid_config_file.check import main as check_config_file
from ontobdc.context.plugin.check.has_valid_context.check import main as check_execution_context
from ontobdc.storage.adapter.bootstrap import get_init_root_path, get_ontobdc_directory
from ontobdc.storage.plugin.check.is_root_set.check import main as check_storage_index


class InfoBIMInitStateEvaluatorAdapter(CliInitStateEvaluatorPort):
    @property
    def process_state_class(self) -> Type[CliInitProcessStatePort]:
        return InfoBIMInitProcessState

    def evaluate(self, context: CliContextPort) -> CliInitProcessStatePort:
        root_path: Path = get_init_root_path(context=context)
        ontobdc_directory: Path = get_ontobdc_directory(root_path)
        if not ontobdc_directory.is_dir():
            return InfoBIMInitProcessState.UNDEFINED

        if check_engine(root_path=str(root_path)) != 0:
            return InfoBIMInitProcessState.ONTOBDC_DIRECTORY_READY

        if check_storage_index(root_path=str(root_path)) != 0:
            return InfoBIMInitProcessState.ENGINE_READY

        if check_execution_context(root_path=str(root_path)) != 0:
            return InfoBIMInitProcessState.STORAGE_INDEX_HEALTHY

        if check_config_file(root_path=str(root_path)) != 0:
            return InfoBIMInitProcessState.EXECUTION_CONTEXT_HEALTHY

        if check_infobim_config(root_path=str(root_path)) != 0:
            return InfoBIMInitProcessState.CONFIG_ADAPTER_READY

        return InfoBIMInitProcessState.INFOBIM_CONFIG_READY
