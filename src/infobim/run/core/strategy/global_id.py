
from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort


class GlobalIdStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args

        if "--global-id" in unprocessed_args:
            idx = unprocessed_args.index("--global-id")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                context.add_parameter("global_id", {
                    "value": val, 
                    "uri": "org.infobim.domain.context.strategy.parameter.global_id",
                    "param_uri": "org.infobim.domain.ifc.input.element.id"
                })
                context.clear_parameters(["--global-id", val])
            else:
                raise ValueError("Missing value for --global-id.")
            
        return context
