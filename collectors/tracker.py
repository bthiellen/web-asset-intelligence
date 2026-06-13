import asyncio
import logging
import re
from typing import Set
import aiohttp

from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel, EntityModel

class TrackerExtractionCollector(BaseCollector):
    """
    Passively fetches the root HTML page of a site and runs regex parsers
    to extract Analytics IDs (Google Analytics UA/G-, GTM-, HubSpot, FB Pixels).
    Establish ownership linkages if multiple sites share tracking IDs.
    """
    def __init__(self):
        super().__init__(name="TrackerExtractionCollector")
        # Compile standard tracking code matching regexes
        self.patterns = {
            "Google Analytics UA": re.compile(r"UA-\d+-\d+"),
            "Google Analytics GA4": re.compile(r"G-[A-Z0-9]{5,15}"),
            "Google Tag Manager": re.compile(r"GTM-[A-Z0-9]{4,10}"),
            "HubSpot Portal": re.compile(r"js\.hs-scripts\.com/(\d+)\.js"),
            "Facebook Pixel": re.compile(r"fbq\('init',\s*'(\d+)'\)")
        }

    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        try:
            async with session.get(url, headers=headers, timeout=10, allow_redirects=True) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as e:
            self.logger.debug("Failed to fetch HTML from %s: %s", url, e)
        return ""

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Extracting tracking and pixel IDs from: %s", target)
        
        nodes = []
        relationships = []
        seen_trackers: Set[str] = set()

        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        html_content = ""
        try:
            async with aiohttp.ClientSession() as session:
                html_content = await self._fetch_html(session, f"https://{target}")
                if not html_content:
                    html_content = await self._fetch_html(session, f"http://{target}")
        except Exception as e:
            self.logger.warning("Could not connect to retrieve homepage HTML: %s", e)

        if not html_content:
            self.logger.warning("No HTML content retrieved for %s. Tracker extraction skipped.", target)
            return CollectorResult(nodes=nodes, relationships=relationships)

        for tracker_type, regex in self.patterns.items():
            matches = regex.findall(html_content)
            for raw_match in matches:
                if isinstance(raw_match, tuple):
                    tracker_id = raw_match[0]
                else:
                    tracker_id = raw_match
                
                tracker_id = tracker_id.strip()
                if not tracker_id or tracker_id in seen_trackers:
                    continue

                seen_trackers.add(tracker_id)
                self.logger.info("Found %s ID: %s", tracker_type, tracker_id)

                try:
                    tracker_entity = EntityModel(
                        id=f"tracker_{tracker_id}",
                        name=f"{tracker_type} ({tracker_id})",
                        type="Company"
                    )
                    nodes.append(tracker_entity)
                    
                    relationships.append((
                        "Domain", "name", target,
                        "OWNED_BY",
                        "Entity", "id", tracker_entity.id
                    ))
                except Exception as e:
                    self.logger.debug("Failed to validate tracker entity: %s", e)

        return CollectorResult(nodes=nodes, relationships=relationships)
