from pathlib import Path
from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from infobim.project.adapter.contract import ProjectGuard


class ContainerCommandProxy(CliCommandPort):
    """
    Runs an OntoBDC container command under the name InfoBIM gives it.

    An InfoBIM project is an OntoBDC container, so what a project command
    does is what the container command already does. The only thing InfoBIM
    changes is the word a user types for it, and the routing stage is the
    single place that word appears: everything past it — the scoped
    arguments, the parameter binding, the validation, the execution — is the
    container command's own, untouched.

    What InfoBIM does add is the contract: every project is a container, but
    a container is a project only while it carries the reserved InfoBIM
    dataset. A proxy therefore refuses a container that is not one, before
    the container command gets to act on it.
    """

    TARGET: ClassVar[Type[CliCommandPort]]
    COMPONENT: ClassVar[str] = "project"
    TARGET_COMPONENT: ClassVar[str] = "container"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    TARGET_SELECTOR_FLAG: ClassVar[str] = "--container"

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._target: CliCommandPort = self.TARGET(request)

    @classmethod
    def accepts_as_target(
        cls,
        target: Type[CliCommandPort],
        args: List[str],
    ) -> bool:
        """
        Report whether the target accepts these arguments under its own name.
        """
        if not args or args[0] != cls.COMPONENT:
            return False

        translated: List[str] = cls.translate_selector(list(args[1:]))

        return target.accepts([cls.TARGET_COMPONENT] + translated)

    @classmethod
    def translate_selector(cls, args: List[str]) -> List[str]:
        """
        Return the arguments under the flag name the container command reads.

        A user of InfoBIM names a project by the GlobalId of its IfcProject.
        The container command underneath names the same thing
        ``--container``, so the flag is translated on the way in — the value
        is not, because turning a GlobalId into a container is the parameter
        stage's job, and by the time the container command validates its
        arguments the container it needs is already in the context.
        """
        return [
            cls.TARGET_SELECTOR_FLAG if argument == cls.SELECTOR_FLAG else argument
            for argument in args
        ]

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        self._request.command_args = self.translate_selector(
            self._request.command_args
        )

        if not self._target.check():
            return False

        self.guard_project()

        return True

    def guard_project(self) -> None:
        """
        Refuse a selected container that is not an InfoBIM project.

        The container is read from where the parameter stage resolved it. A
        proxy whose command selects differently — by an identifier of its
        own, say — overrides this.
        """
        project_path: Any = self._request.context.get_parameter_value(
            "container_path"
        )
        if not isinstance(project_path, str) or not project_path.strip():
            return

        ProjectGuard.guard(
            Path(project_path).expanduser().resolve(),
            self._request.context.root_path,
        )

    def run(self) -> CommandResponse:
        """
        Execute the container command this one stands for.
        """
        return self._target.run()
