import logging
import aiohttp
from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel, EntityModel

class HTTPHeaderCollector(BaseCollector):
    """
    Passively requests HTTP/HTTPS headers from the target domain's root server
    to finger-print technology banners (Server software, script versions, CDNs).
    """
    def __init__(self):
        super().__init__(name="HTTPHeaderCollector")

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Retrieving HTTP response headers for target: %s", target)
        
        nodes = []
        relationships = []
        
        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        raw_headers = {}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Query HTTPS first, fallback to HTTP
                for proto in ("https", "http"):
                    url = f"{proto}://{target}"
                    try:
                        async with session.head(url, timeout=7, allow_redirects=True) as resp:
                            raw_headers = dict(resp.headers)
                            if raw_headers:
                                break
                    except Exception:
                        continue
        except Exception as e:
            self.logger.warning("HTTP header fetch request failed: %s", e)

        if not raw_headers:
            self.logger.warning("No HTTP response headers collected for %s.", target)
            return CollectorResult(nodes=nodes, relationships=relationships)

        # Extract Server technology signature
        server_header = raw_headers.get("Server", "").strip()
        powered_by = raw_headers.get("X-Powered-By", "").strip()

        # Create software nodes
        if server_header:
            self.logger.info("Detected HTTP Server signature: %s", server_header)
            try:
                server_entity = EntityModel(
                    id=f"server_{server_header.replace(' ', '_').lower()}",
                    name=f"HTTP Server: {server_header}",
                    type="Company"
                )
                nodes.append(server_entity)
                
                relationships.append((
                    "Domain", "name", target,
                    "ASSOCIATED_WITH",
                    "Entity", "id", server_entity.id
                ))
            except Exception as e:
                self.logger.debug("Failed validating Server Entity: %s", e)

        if powered_by:
            self.logger.info("Detected X-Powered-By signature: %s", powered_by)
            try:
                powered_entity = EntityModel(
                    id=f"powered_{powered_by.replace(' ', '_').lower()}",
                    name=f"Technology Profile: {powered_by}",
                    type="Company"
                )
                nodes.append(powered_entity)
                
                relationships.append((
                    "Domain", "name", target,
                    "ASSOCIATED_WITH",
                    "Entity", "id", powered_entity.id
                ))
            except Exception as e:
                self.logger.debug("Failed validating Powered Entity: %s", e)

        return CollectorResult(nodes=nodes, relationships=relationships)
