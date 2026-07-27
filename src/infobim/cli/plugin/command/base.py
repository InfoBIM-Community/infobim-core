
from typing import Any, Dict, List, Optional
from infobim.cli.adapter.machine import InfoBIMInitStateEvaluatorAdapter
from infobim.cli.domain.context import InfoBIMCliContext
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.port.machine import CliInitProcessStatePort
from ontobdc.cli.domain.response.command import CommandResponse, WelcomeCommandResponse
from infobim.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.model.language import LanguageResource


class CliBaseCommand(CliCommandPort):
    """
    Helper class for base command loading.
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="cli",
        description="Base CLI command handler.",
        depends_on=None,
    )
    _WELCOME_MARKDOWN: str = (
        "Welcome to InfoBIM.\n\n"
        "Build, inspect, and automate engineering workflows from a modular runtime "
        "designed for engineering automation."
    )
    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        if not args:
            return True

        return len(args) == 0

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self.__class__.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        config_adapter: ConfigDataAdapter = ConfigDataAdapter()
        system_status: str = self._system_status(config_adapter)
        welcome_content: Dict[str, Any] = {
            "hero": self._WELCOME_MARKDOWN,
            "overview": self._overview_rows(config_adapter),
            "system_status": system_status,
        }

        return WelcomeCommandResponse(
            title="InfoBIM Welcome",
            description="Display the InfoBIM welcome experience.",
            content=welcome_content,
        )

    def _overview_rows(self, config_adapter: ConfigDataAdapter) -> List[Dict[str, str]]:
        configured_language: Optional[str] = self._configured_language(config_adapter)
        return [
            {
                "label": "Root Directory",
                "value": str(config_adapter.root_dir),
            },
            {
                "label": "Engine",
                "value": self._engine(config_adapter),
            },
            {
                "label": "Languages",
                "value": self._format_languages(
                    config_adapter.available_languages,
                    configured_language,
                ),
            },
        ]

    def _engine(self, config_adapter: ConfigDataAdapter) -> str:
        config_data: Optional[Dict[str, Any]] = config_adapter.all
        if isinstance(config_data, dict):
            engine: object = config_data.get("engine")
            if isinstance(engine, str) and engine:
                return engine

        return "not set"

    def _configured_language(self, config_adapter: ConfigDataAdapter) -> Optional[str]:
        obdc_context: object = config_adapter.context_data.get("obdc", {})
        if not isinstance(obdc_context, dict):
            return None

        configured_language: object = obdc_context.get("contextLanguage")
        if isinstance(configured_language, str) and configured_language:
            return configured_language

        return None

    def _format_languages(
        self,
        languages: List[LanguageResource],
        configured_language: Optional[str],
    ) -> str:
        formatted_languages: List[str] = []
        available_language_ids: List[str] = []
        language: LanguageResource

        for language in languages:
            language_label: str = language.id
            available_language_ids.append(language.id)
            if language.id == configured_language:
                language_label = f"[bold blue]{language_label}[/]"

            formatted_languages.append(language_label)

        if configured_language and configured_language not in available_language_ids:
            formatted_languages.insert(0, f"[bold blue]{configured_language}[/]")

        if not formatted_languages:
            return "none detected"

        return ", ".join(formatted_languages)

    def _system_status(self, config_adapter: ConfigDataAdapter) -> CliInitProcessStatePort:
        context: InfoBIMCliContext = InfoBIMCliContext(
            root_path=str(config_adapter.root_dir),
            raw_args=list(self._request.command_args),
            unprocessed_args=list(self._request.command_args),
        )
        evaluator: InfoBIMInitStateEvaluatorAdapter = InfoBIMInitStateEvaluatorAdapter()
        state: CliInitProcessStatePort = evaluator.evaluate(context)
        return state
