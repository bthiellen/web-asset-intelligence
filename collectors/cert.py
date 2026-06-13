import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Set, Tuple, List
import aiohttp

from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel, CertificateModel

class CertificateTransparencyCollector(BaseCollector):
    """
    Queries public Certificate Transparency (CT) log indexes.
    Uses crt.sh as the primary index and Certspotter (SSLMate) as a fallback.
    """
    def __init__(self):
        super().__init__(name="CertificateTransparencyCollector")
        self.crt_sh_url = "https://crt.sh"
        self.certspotter_url = "https://api.certspotter.com/v1/issuances"

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Retrieving Certificate Transparency logs for target: %s", target)
        
        # 1. Query crt.sh
        result = await self._query_crt_sh(target)
        
        # 2. Fallback to Certspotter if crt.sh failed or returned no certificates (only the target domain node)
        if len(result.nodes) <= 1:
            self.logger.warning("Primary crt.sh CT lookup returned no certificates. Querying Certspotter API fallback...")
            result = await self._query_certspotter(target)
            
        return result

    async def _query_crt_sh(self, target: str) -> CollectorResult:
        self.logger.debug("Querying crt.sh for %s", target)
        nodes = []
        relationships = []
        
        seen_domains: Set[str] = set()
        seen_certs: Set[str] = set()
        
        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
            seen_domains.add(target.lower())
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        params = {"q": target, "output": "json"}
        
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.crt_sh_url, params=params) as response:
                    if response.status != 200:
                        self.logger.warning("crt.sh query failed with HTTP status %d", response.status)
                        return CollectorResult(nodes=nodes, relationships=relationships)
                    
                    data = await response.json()
                    if not isinstance(data, list):
                        return CollectorResult(nodes=nodes, relationships=relationships)
                    
                    for item in data[:15]:
                        serial = item.get("serial_number") or ""
                        if not serial:
                            serial = str(item.get("id", ""))
                        
                        fingerprint = hashlib.sha256(serial.encode("utf-8")).hexdigest()
                        if fingerprint in seen_certs:
                            continue
                            
                        try:
                            from_str = item.get("not_before", "").replace("Z", "")
                            to_str = item.get("not_after", "").replace("Z", "")
                            valid_from = datetime.fromisoformat(from_str)
                            valid_to = datetime.fromisoformat(to_str)
                        except (ValueError, TypeError):
                            valid_from = datetime.now(timezone.utc)
                            valid_to = datetime.now(timezone.utc)
                            
                        name_value = item.get("name_value") or ""
                        sans = list(set(
                            san.strip().lower()
                            for san in name_value.replace("\r", "").split("\n")
                            if san.strip()
                        ))
                        
                        try:
                            cert_node = CertificateModel(
                                sha256=fingerprint,
                                issuer=item.get("issuer_name", "Unknown Issuer"),
                                subject=item.get("common_name", "Unknown Subject"),
                                valid_from=valid_from,
                                valid_to=valid_to,
                                sans=sans
                            )
                            nodes.append(cert_node)
                            seen_certs.add(fingerprint)
                        except Exception as e:
                            self.logger.debug("Skipping cert validation error: %s", e)
                            continue
                            
                        for san in sans:
                            clean_san = san.replace("*.", "")
                            if clean_san not in seen_domains:
                                try:
                                    san_domain = DomainModel(
                                        name=clean_san, 
                                        tags=["subdomain" if clean_san.endswith(target) else "external"]
                                    )
                                    nodes.append(san_domain)
                                    seen_domains.add(clean_san)
                                except Exception:
                                    continue
                                    
                            relationships.append((
                                "Domain", "name", clean_san,
                                "SHARES_CERT",
                                "Certificate", "sha256", fingerprint
                            ))
                            
        except Exception as e:
            self.logger.warning("crt.sh query request encountered an error: %s", e)
            
        return CollectorResult(nodes=nodes, relationships=relationships)

    async def _query_certspotter(self, target: str) -> CollectorResult:
        self.logger.debug("Querying Certspotter for %s", target)
        nodes = []
        relationships = []
        
        seen_domains: Set[str] = set()
        seen_certs: Set[str] = set()
        
        try:
            target_domain = DomainModel(name=target, tags=["target"])
            nodes.append(target_domain)
            seen_domains.add(target.lower())
        except Exception as e:
            self.logger.error("Target domain validation failed: %s", e)
            return CollectorResult()

        params = {
            "domain": target,
            "include_subdomains": "true",
            "expand": ["dns_names", "issuer"]
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.certspotter_url, params=params) as response:
                    if response.status != 200:
                        self.logger.warning("Certspotter query failed with HTTP status %d", response.status)
                        return CollectorResult(nodes=nodes, relationships=relationships)
                    
                    data = await response.json()
                    if not isinstance(data, list):
                        return CollectorResult(nodes=nodes, relationships=relationships)
                    
                    for item in data[:15]:
                        cert_id = str(item.get("id", ""))
                        if not cert_id:
                            continue
                        
                        fingerprint = hashlib.sha256(cert_id.encode("utf-8")).hexdigest()
                        if fingerprint in seen_certs:
                            continue
                            
                        try:
                            from_str = item.get("not_before", "").replace("Z", "")
                            to_str = item.get("not_after", "").replace("Z", "")
                            valid_from = datetime.fromisoformat(from_str)
                            valid_to = datetime.fromisoformat(to_str)
                        except (ValueError, TypeError):
                            valid_from = datetime.now(timezone.utc)
                            valid_to = datetime.now(timezone.utc)
                            
                        sans = list(set(
                            san.strip().lower()
                            for san in item.get("dns_names", [])
                            if san.strip()
                        ))
                        
                        issuer_info = item.get("issuer", {})
                        issuer_name = issuer_info.get("name", "Unknown Issuer")
                        
                        try:
                            cert_node = CertificateModel(
                                sha256=fingerprint,
                                issuer=issuer_name,
                                subject=sans[0] if sans else "Unknown Subject",
                                valid_from=valid_from,
                                valid_to=valid_to,
                                sans=sans
                            )
                            nodes.append(cert_node)
                            seen_certs.add(fingerprint)
                        except Exception as e:
                            self.logger.debug("Skipping cert validation error: %s", e)
                            continue
                            
                        for san in sans:
                            clean_san = san.replace("*.", "")
                            if clean_san not in seen_domains:
                                try:
                                    san_domain = DomainModel(
                                        name=clean_san, 
                                        tags=["subdomain" if clean_san.endswith(target) else "external"]
                                    )
                                    nodes.append(san_domain)
                                    seen_domains.add(clean_san)
                                except Exception:
                                    continue
                                    
                            relationships.append((
                                "Domain", "name", clean_san,
                                "SHARES_CERT",
                                "Certificate", "sha256", fingerprint
                            ))
                            
        except Exception as e:
            self.logger.warning("Certspotter query request encountered an error: %s", e)
            
        return CollectorResult(nodes=nodes, relationships=relationships)
