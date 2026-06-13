import logging
import aiohttp
from typing import Set
from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel, IPModel

class ReverseIPCollector(BaseCollector):
    """
    Performs reverse IP neighbors lookup using HackerTarget's public free API.
    Identifies other domains sharing host server properties.
    """
    def __init__(self):
        super().__init__(name="ReverseIPCollector")
        self.api_url = "https://api.hackertarget.com/reverseiplookup/"

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Performing reverse IP neighbors lookup for target: %s", target)
        
        nodes = []
        relationships = []
        seen_domains: Set[str] = set()

        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
            seen_domains.add(target.lower())
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        params = {"q": target}
        
        try:
            # HackerTarget free API call
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=8) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        
                        # HackerTarget returns plain text list of domains, one per line
                        if "API count exceeded" in content or "error" in content.lower():
                            self.logger.warning("HackerTarget API limit or error: %s", content.strip())
                            return CollectorResult(nodes=nodes, relationships=relationships)

                        lines = [line.strip().lower() for line in content.split("\n") if line.strip()]
                        
                        # Cap neighbors at 15 to keep database graph clusters clean and avoid spamming CDNs
                        for neighbor in lines[:15]:
                            if neighbor == target.lower() or neighbor in seen_domains:
                                continue
                            
                            try:
                                neighbor_domain = DomainModel(name=neighbor, tags=["neighbor"])
                                nodes.append(neighbor_domain)
                                seen_domains.add(neighbor)
                                
                                # Since we do not know the exact IP here, we map an association:
                                # Domain (target) -[:ASSOCIATED_WITH]-> Domain (neighbor)
                                relationships.append((
                                    "Domain", "name", target,
                                    "ASSOCIATED_WITH",
                                    "Domain", "name", neighbor
                                ))
                            except Exception:
                                continue
        except Exception as e:
            self.logger.warning("Reverse IP neighbors lookup request failed: %s", e)

        return CollectorResult(nodes=nodes, relationships=relationships)
