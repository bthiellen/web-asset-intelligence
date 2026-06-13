import abc
import logging
from asset_intel.models import CollectorResult



class BaseCollector(abc.ABC):
    """
    Abstract Base Class for all OSINT and Manual data collectors.
    Enforces passive-only intelligence collection: no active socket scanning or scanning tools.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abc.abstractmethod
    async def collect(self, target: str) -> CollectorResult:
        """
        Executes passive information collection for the target identifier (e.g. domain, corporate name).
        
        Args:
            target: The query identifier (FQDN, corporate identity, certificate fingerprint)
            
        Returns:
            CollectorResult: Validated node models and relationship connections.
        """
        pass

    def log_passive_policy_notice(self):
        """Helper to ensure compliance with the passive-only design."""
        self.logger.info("[%s] Operating strictly under passive OSINT safety policy. No active probing.", self.name)
