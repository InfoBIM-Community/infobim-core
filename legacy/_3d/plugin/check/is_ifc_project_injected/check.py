def main(project_path: str = None) -> int:
    """
    Report the Project's IfcProject as never already injected.

    Unlike the other states this codebase's machines check for, injecting
    the IfcProject as JSON-LD leaves no durable artifact on the Project's
    own disk: it is redone for every viewer launch, not a fact that can
    already be true about the Project the way a file existing is. There is
    nothing here for a check to find, by design, so this always reports
    the state as not yet reached.
    """
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
