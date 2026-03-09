
from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort


class IfcClassStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args

        if "--ifc-class" in unprocessed_args:
            idx = unprocessed_args.index("--ifc-class")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                context.add_parameter("ifc_class", {
                    "value": val, 
                    "uri": "org.infobim.domain.context.strategy.parameter.ifc_class",
                    "param_uri": "org.infobim.domain.ifc.input.class"
                })
                context.clear_parameters(["--ifc-class", val])
            else:
                raise ValueError("Missing value for --ifc-class.")
            
        return context

