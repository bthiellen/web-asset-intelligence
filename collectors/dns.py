import asyncio
import logging
from typing import Set
import aiohttp

from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel, IPModel

class PassiveDNSCollector(BaseCollector):
    """
    Queries public Cloudflare DNS-over-HTTPS (DoH) API and ip-api.com
    to passively discover domain IPs, MX servers, NS servers, and ASN mapping details.
    """
    def __init__(self):
        super().__init__(name="PassiveDNSCollector")
        self.doh_url = "https://cloudflare-dns.com/dns-query"
        self.ip_api_url = "http://ip-api.com/json"

    async def _query_doh(self, session: aiohttp.ClientSession, name: str, record_type: str) -> list:
        headers = {"accept": "application/dns-json"}
        params = {"name": name, "type": record_type}
        try:
            async with session.get(self.doh_url, headers=headers, params=params, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data.get("Answer", [])
        except Exception as e:
            self.logger.warning("DoH lookup failed for %s (%s): %s", name, record_type, e)
        return []

    async def _get_ip_details(self, session: aiohttp.ClientSession, ip: str) -> dict:
        try:
            async with session.get(f"{self.ip_api_url}/{ip}", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        as_str = data.get("as", "")
                        asn = None
                        if as_str.startswith("AS"):
                            parts = as_str.split(" ")
                            if parts:
                                try:
                                    asn = int(parts[0][2:])
                                except ValueError:
                                    pass
                        return {
                            "asn": asn,
                            "hosting_provider": data.get("org") or data.get("isp") or "Unknown Provider"
                        }
        except Exception as e:
            self.logger.warning("IP lookup failed for %s: %s", ip, e)
        return {"asn": None, "hosting_provider": "Unknown Provider"}

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Resolving passive DNS records for domain: %s", target)
        
        nodes = []
        relationships = []
        seen_ips: Set[str] = set()
        seen_domains: Set[str] = set()

        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
            seen_domains.add(target.lower())
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        try:
            async with aiohttp.ClientSession() as session:
                a_task = self._query_doh(session, target, "A")
                aaaa_task = self._query_doh(session, target, "AAAA")
                mx_task = self._query_doh(session, target, "MX")
                ns_task = self._query_doh(session, target, "NS")

                a_ans, aaaa_ans, mx_ans, ns_ans = await asyncio.gather(
                    a_task, aaaa_task, mx_task, ns_task
                )

                ip_records = []
                for record in a_ans + aaaa_ans:
                    ip_addr = record.get("data", "").strip()
                    if ip_addr and ip_addr not in seen_ips:
                        ip_records.append(ip_addr)
                        seen_ips.add(ip_addr)

                ip_details_list = []
                for idx, ip in enumerate(ip_records):
                    if idx > 0:
                        # Pacing delay to avoid ip-api.com rate limits
                        await asyncio.sleep(1.5)
                    details = await self._get_ip_details(session, ip)
                    ip_details_list.append(details)

                for ip_addr, details in zip(ip_records, ip_details_list):
                    try:
                        ip_node = IPModel(
                            address=ip_addr,
                            asn=details.get("asn"),
                            hosting_provider=details.get("hosting_provider")
                        )
                        nodes.append(ip_node)
                        relationships.append((
                            "Domain", "name", target,
                            "HOSTS",
                            "IP", "address", ip_addr
                        ))
                    except Exception as e:
                        self.logger.debug("Failed validating IP node %s: %s", ip_addr, e)

                for record in mx_ans:
                    raw_data = record.get("data", "").strip().rstrip(".")
                    parts = raw_data.split(" ")
                    mx_host = parts[-1].strip().lower()
                    if mx_host and mx_host not in seen_domains:
                        try:
                            mx_domain = DomainModel(name=mx_host, tags=["infrastructure", "mail"])
                            nodes.append(mx_domain)
                            seen_domains.add(mx_host)
                            
                            relationships.append((
                                "Domain", "name", target,
                                "ASSOCIATED_WITH",
                                "Domain", "name", mx_host
                            ))
                        except Exception:
                            continue

                for record in ns_ans:
                    ns_host = record.get("data", "").strip().lower().rstrip(".")
                    if ns_host and ns_host not in seen_domains:
                        try:
                            ns_domain = DomainModel(name=ns_host, tags=["infrastructure", "nameserver"])
                            nodes.append(ns_domain)
                            seen_domains.add(ns_host)
                            
                            relationships.append((
                                "Domain", "name", target,
                                "ASSOCIATED_WITH",
                                "Domain", "name", ns_host
                            ))
                        except Exception:
                            continue

        except Exception as e:
            self.logger.error("Failed executing passive DNS collector: %s", e)

        return CollectorResult(nodes=nodes, relationships=relationships)
