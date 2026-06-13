import asyncio
import argparse
import sys
import logging
import os
from typing import List
from dotenv import load_dotenv

from asset_intel.storage.database import Neo4jManager
from asset_intel.collectors.dns import PassiveDNSCollector
from asset_intel.collectors.cert import CertificateTransparencyCollector
from asset_intel.collectors.tracker import TrackerExtractionCollector
from asset_intel.collectors.favicon import FaviconCollector
from asset_intel.collectors.reverse_ip import ReverseIPCollector
from asset_intel.collectors.whois import WhoisCollector
from asset_intel.collectors.headers import HTTPHeaderCollector
from asset_intel.collectors.base import CollectorResult

# Configure logging to display clean structural context
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("asset_intel.engine")

class AnalysisEngine:
    """
    Orchestrates the passive collection pipeline, validates models,
    inserts entities/links into the Neo4j graph, and reports summaries.
    """
    def __init__(self, db_manager: Neo4jManager):
        self.db = db_manager
        # Initialize collectors
        self.collectors = [
            PassiveDNSCollector(),
            CertificateTransparencyCollector(),
            TrackerExtractionCollector(),
            FaviconCollector(),
            ReverseIPCollector(),
            WhoisCollector(),
            HTTPHeaderCollector()
        ]

    async def run_analysis(self, target_domain: str):
        logger.info("Initializing asset link analysis for target: %s", target_domain)
        
        # Connect to Neo4j
        try:
            await self.db.connect()
        except Exception as e:
            logger.error("Failed to connect to Neo4j database: %s. Continuing dry-run mode.", e)
            logger.warning("Graph database storage skipped. Data will only be summarized locally.")
            db_connected = False
        else:
            db_connected = True

        # Check graph cache freshness (24h threshold)
        if db_connected:
            cache_fresh = await self.db.check_node_freshness("Domain", "name", target_domain, max_age_seconds=86400)
            if cache_fresh:
                logger.info("Domain '%s' has fresh data inside the graph (within 24h). Skipping external lookups.", target_domain)
                print("\n" + "="*50)
                print("WEB ASSET INTELLIGENCE ENGINE SUMMARY REPORT")
                print("="*50)
                print(f"Target analyzed: {target_domain} (CACHED)")
                print("[+] Graph nodes and relationships are already fresh in the Neo4j database.")
                print("="*50 + "\n")
                await self.db.close()
                return

        # Aggregate results from passive collectors concurrently
        tasks = [collector.collect(target_domain) for collector in self.collectors]
        results: List[CollectorResult] = await asyncio.gather(*tasks)

        # Merge findings into a single execution report
        total_nodes = 0
        total_edges = 0
        node_summaries = {}

        for result in results:
            # 1. Process Nodes
            for node in result.nodes:
                label = node.__class__.__name__.replace("Model", "")
                # Discover key field (name for Domain, address for IP, sha256 for Certificate, id for Entity/Address)
                key_field = "id"
                if label == "Domain":
                    key_field = "name"
                elif label == "IP":
                    key_field = "address"
                elif label == "Certificate":
                    key_field = "sha256"

                # Standardize properties
                node_props = node.model_dump()
                key_val = node_props.get(key_field)

                # Count uniqueness
                node_summaries[f"{label}:{key_val}"] = (label, key_field, node_props)

                if db_connected:
                    try:
                        await self.db.create_node(label, key_field, node_props)
                        total_nodes += 1
                    except Exception as err:
                        logger.error("Error creating node %s: %s", key_val, err)

            # 2. Process Relationships
            for rel in result.relationships:
                src_lbl, src_key, src_val, r_type, tgt_lbl, tgt_key, tgt_val = rel
                if db_connected:
                    try:
                        await self.db.create_relationship(
                            src_lbl, src_key, src_val,
                            r_type,
                            tgt_lbl, tgt_key, tgt_val
                        )
                        total_edges += 1
                    except Exception as err:
                        logger.error("Error creating relationship: %s", err)
                else:
                    total_edges += 1

        # Print OSINT structural summary to stdout
        print("\n" + "="*50)
        print("WEB ASSET INTELLIGENCE ENGINE SUMMARY REPORT")
        print("="*50)
        print(f"Target analyzed: {target_domain}")
        print(f"Discovered Nodes count: {len(node_summaries)}")
        print(f"Discovered Relationships count: {total_edges}")
        print("\nResolved Infrastructure Map:")
        for key, (lbl, k_fld, props) in node_summaries.items():
            print(f" - [{lbl}] {props.get(k_fld)}")

        if db_connected:
            print(f"\n[+] Graph successfully synchronized into Neo4j ({total_nodes} nodes updated).")
            await self.db.close()
        else:
            print("\n[!] Dry-run completed. Graph sync skipped due to Neo4j connection failure.")
        print("="*50 + "\n")


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Modular Web Asset Intelligence Analysis Engine CLI"
    )
    parser.add_argument("domain", help="Target domain FQDN to query passively")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help="Neo4j connection URI")
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"), help="Neo4j database username")
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"), help="Neo4j database password")
    
    args = parser.parse_args()

    db_manager = Neo4jManager(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password
    )
    engine = AnalysisEngine(db_manager)
    
    try:
        asyncio.run(engine.run_analysis(args.domain))
    except KeyboardInterrupt:
        print("\n[-] Analysis aborted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
