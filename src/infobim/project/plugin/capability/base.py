from ontobdc.shared.adapter.capability import TransactionCapability


class ProjectTransactionCapability(TransactionCapability):
    """Concrete InfoBIM capability base using CapabilityMetadata presentation text."""

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)
