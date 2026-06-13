import json
from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.utils.ai_mapper import CorporateFilingMapper

class ManualFilingCollector(BaseCollector):
    """
    Manual data collector interface to ingest corporate registry listings (LLC, Inc. records).
    Expects structured filing raw JSON data input.
    """
    def __init__(self):
        super().__init__(name="ManualFilingCollector")

    async def collect(self, target: str) -> CollectorResult:
        """
        Ingests and translates structured JSON filing strings into graph nodes.
        
        Args:
            target: String representing raw JSON record or path to JSON corporate record.
        """
        self.logger.info("Ingesting manual corporate filing record.")
        try:
            # Let's see if the target is a valid JSON string or file path
            if target.strip().startswith("{"):
                json_data = target
            else:
                with open(target, "r") as f:
                    json_data = f.read()

            result = CorporateFilingMapper.map_scc_json(json_data)
            self.logger.info(
                "Ingestion complete: %d nodes and %d relationships resolved.",
                len(result.nodes), len(result.relationships)
            )
            return result
        except Exception as e:
            self.logger.error("Failed to parse manual filing: %s", e)
            return CollectorResult()
