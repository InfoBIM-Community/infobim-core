from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort


class IfcPathStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args

        if "--ifc-path" in unprocessed_args:
            idx = unprocessed_args.index("--ifc-path")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                context.add_parameter("ifc_path", {
                    "value": val, 
                    "uri": "org.infobim.domain.context.strategy.parameter.ifc_path",
                    "param_uri": "org.infobim.domain.ifc.input.path"
                })
                context.clear_parameters(["--ifc-path", val])
            else:
                raise ValueError("Missing value for --ifc-path.")
            
        return context
