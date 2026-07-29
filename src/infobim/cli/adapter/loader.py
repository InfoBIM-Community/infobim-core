
import inspect
import importlib
from typing import List, Optional, Type
from ontobdc.shared.domain.port.loader import PluginLoaderPort
from ontobdc.cli.domain.response.command import CommandResponse
from infobim.cli.domain.port.response import ResponseAnsiInformationAdapterPort


class ResponseAnsiInformationAdapterLoader(PluginLoaderPort):
    """
    Resolve InfoBIM response adapters from the local adapter module.
    """
    def __init__(self, module_name: str = "infobim.cli.adapter.response") -> None:
        self._module_name: str = module_name

    def get(self, response: CommandResponse) -> ResponseAnsiInformationAdapterPort:
        adapter: Optional[ResponseAnsiInformationAdapterPort] = self._resolve_adapter(response)

        if isinstance(adapter, ResponseAnsiInformationAdapterPort):
            return adapter

        raise ValueError(f"Unsupported response type: {type(response).__name__}")

    def get_all(self) -> List[ResponseAnsiInformationAdapterPort]:
        module = importlib.import_module(self._module_name)
        adapters: List[ResponseAnsiInformationAdapterPort] = []
        candidate_type: Type[object]
        adapter_type: Type[ResponseAnsiInformationAdapterPort]

        for _, candidate_type in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate_type, ResponseAnsiInformationAdapterPort):
                continue

            if candidate_type is ResponseAnsiInformationAdapterPort:
                continue

            adapter_type = candidate_type
            adapters.append(adapter_type())

        return adapters

    def _resolve_adapter(self, response: CommandResponse) -> Optional[ResponseAnsiInformationAdapterPort]:
        candidates: List[ResponseAnsiInformationAdapterPort] = [
            adapter for adapter in self.get_all() if adapter.accepts(response)
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda adapter: self._resolve_priority(response, adapter))
        return candidates[0]

    def _resolve_priority(
        self,
        response: CommandResponse,
        adapter: ResponseAnsiInformationAdapterPort,
    ) -> int:
        response_type: Type[CommandResponse] = type(response)
        candidate_type: Type[CommandResponse] = getattr(adapter, "response_type", CommandResponse)
        response_mro: List[Type[object]] = list(type(response).mro())

        if candidate_type in response_mro:
            return response_mro.index(candidate_type)

        if issubclass(response_type, candidate_type):
            return len(response_mro)

        return len(response_mro) + 1
