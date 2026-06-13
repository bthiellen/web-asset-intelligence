import asyncio
import logging
import re
from datetime import datetime, timezone
from asset_intel.collectors.base import BaseCollector, CollectorResult
from asset_intel.models.entities import DomainModel

class WhoisCollector(BaseCollector):
    """
    Queries passive domain registration details using the system's local whois utility.
    Extracts registrar and domain creation timestamps without requiring external APIs.
    """
    def __init__(self):
        super().__init__(name="WhoisCollector")
        # Regex mappings for registrar and creation date
        self.registrar_regex = re.compile(
            r"(?:Registrar|registrar|Registrar Name|Sponsoring Registrar):\s*(.*)", re.IGNORECASE
        )
        self.creation_date_regex = re.compile(
            r"(?:Creation Date|creation date|Created On|Registration Time|Registered On):\s*(.*)", re.IGNORECASE
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Tries parsing raw date strings returned from WHOIS records."""
        date_str = date_str.strip()
        # Remove trailing timezones or clean ISO formats (e.g. 2020-04-12T00:00:00Z)
        cleaned_str = date_str.split(" ")[0].replace("Z", "")
        
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y"
        ):
            try:
                # Truncate strings to match formatting length
                dt = datetime.strptime(cleaned_str[:len(fmt.replace("%b", "Jan"))], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def collect(self, target: str) -> CollectorResult:
        self.log_passive_policy_notice()
        self.logger.info("Executing local whois command query for: %s", target)
        
        nodes = []
        
        # Execute the native shell command 'whois {target}'
        try:
            proc = await asyncio.create_subprocess_exec(
                "whois", target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode("utf-8", errors="ignore")
        except Exception as e:
            self.logger.warning("Local whois executable call failed: %s", e)
            output = ""

        registrar = None
        creation_date = None

        if output:
            # Parse output lines
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                # Check for registrar
                reg_match = self.registrar_regex.search(line)
                if reg_match and not registrar:
                    registrar = reg_match.group(1).strip()
                
                # Check for creation date
                date_match = self.creation_date_regex.search(line)
                if date_match and not creation_date:
                    raw_date = date_match.group(1).strip()
                    creation_date = self._parse_date(raw_date)

        # Update the target Domain model with registry attributes
        try:
            target_domain = DomainModel(
                name=target,
                tags=["target"],
                registrar=registrar,
                creation_date=creation_date
            )
            nodes.append(target_domain)
            self.logger.info(
                "WHOIS parsing completed: Registrar=%s, Created=%s", 
                registrar, creation_date
            )
        except Exception as e:
            self.logger.error("Failed validating Domain model with WHOIS attributes: %s", e)

        return CollectorResult(nodes=nodes, relationships=[])
