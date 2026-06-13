import hashlib
import logging
import aiohttp
from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel, FaviconModel

class FaviconCollector(BaseCollector):
    """
    Passively requests the favicon.ico of a domain and hashes it.
    Can be used to map hidden server clusters on Shodan/Censys.
    """
    def __init__(self):
        super().__init__(name="FaviconCollector")

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Retrieving favicon signature for: %s", target)
        
        nodes = []
        relationships = []
        
        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        favicon_bytes = b""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        try:
            # Fetch favicon over HTTPS first, fallback to HTTP
            async with aiohttp.ClientSession(headers=headers) as session:
                for proto in ("https", "http"):
                    url = f"{proto}://{target}/favicon.ico"
                    try:
                        async with session.get(url, timeout=6, allow_redirects=True) as resp:
                            if resp.status == 200:
                                favicon_bytes = await resp.read()
                                if favicon_bytes:
                                    break
                    except Exception:
                        continue
        except Exception as e:
            self.logger.warning("Favicon network fetch encountered errors: %s", e)

        if not favicon_bytes:
            self.logger.warning("No favicon retrieved for %s. Skipping favicon extraction.", target)
            return CollectorResult(nodes=nodes, relationships=relationships)

        # Hash favicon bytes
        md5_hash = hashlib.md5(favicon_bytes).hexdigest()
        sha256_hash = hashlib.sha256(favicon_bytes).hexdigest()
        
        self.logger.info("Discovered favicon fingerprint: MD5=%s", md5_hash)

        try:
            favicon_node = FaviconModel(
                id=md5_hash,
                md5=md5_hash,
                sha256=sha256_hash
            )
            nodes.append(favicon_node)
            
            relationships.append((
                "Domain", "name", target,
                "HAS_FAVICON",
                "Favicon", "id", md5_hash
            ))
        except Exception as e:
            self.logger.debug("Failed validating favicon model: %s", e)

        return CollectorResult(nodes=nodes, relationships=relationships)
