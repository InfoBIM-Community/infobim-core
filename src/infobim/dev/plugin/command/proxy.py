from ontobdc.dev.plugin.command import proxy as _ontobdc_dev_proxy


class DevProxyCommand(_ontobdc_dev_proxy.DevProxyCommand):
    """Locate and execute the external ontobdc-dev package for InfoBIM.

    Reuses the entire proxy chain from OntoBDC, overriding only the target
    repository marker forwarded to the dev test runners (so pytest targets
    ``infobim/test/`` instead of ``ontobdc/test/``) and the default --system
    injected into ``doc --create ...`` calls.
    """

    TEST_REPO_VALUE: str = "infobim"
    SYSTEM_NAME: str = "infobim"
