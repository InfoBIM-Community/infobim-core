from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort


class InfoBIMCliContext(CliContextPort):
    def __init__(
        self,
        root_path: str,
        raw_args: Optional[List[str]] = None,
        unprocessed_args: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        target_capability_id: Optional[str] = None,
    ) -> None:
        self._root_path: str = root_path
        self._raw_args: List[str] = list(raw_args or [])
        self._unprocessed_args: List[str] = list(unprocessed_args or [])
        self._parameters: Dict[str, Any] = dict(parameters or {})
        self._language: Optional[str] = language
        self._target_capability_id: Optional[str] = target_capability_id

    @property
    def raw_args(self) -> List[str]:
        return list(self._raw_args)

    @property
    def unprocessed_args(self) -> List[str]:
        return list(self._unprocessed_args)

    @property
    def is_capability_targeted(self) -> bool:
        return isinstance(self._target_capability_id, str) and bool(self._target_capability_id.strip())

    @property
    def target_capability_id(self) -> Optional[str]:
        return self._target_capability_id

    @property
    def root_path(self) -> str:
        return self._root_path

    @property
    def language(self, fallback: str = None) -> Optional[str]:
        if isinstance(self._language, str) and self._language.strip():
            return self._language

        return fallback

    def has_parameter(self, param_key: str) -> bool:
        return param_key in self._parameters

    def get_parameter_value(self, param_key: str) -> Any:
        return self._parameters.get(param_key)

    def set_parameter_value(self, param_key: str, param_value: Any) -> None:
        self._parameters[param_key] = param_value

    def delete_parameter(self, param_key: str) -> None:
        self._parameters.pop(param_key, None)

    def clear_parameters(self, param_keys: List[str]) -> None:
        param_key: str
        for param_key in param_keys:
            self.delete_parameter(param_key)

    def reload(self) -> None:
        return None
