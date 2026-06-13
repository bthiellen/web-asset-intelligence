import os
import logging
import time
from typing import Dict, Any, Optional
from neo4j import GraphDatabase, AsyncGraphDatabase, AsyncDriver
from asset_intel.models.entities import (
    DomainModel, IPModel, CertificateModel, EntityModel, AddressModel
)
from asset_intel.storage.schema import initialize_neo4j_schema

logger = logging.getLogger(__name__)

class Neo4jManager:
    """
    Manages connection to Neo4j and offers helper operations for storing nodes and relationships.
    """
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver: Optional[AsyncDriver] = None

    async def connect(self):
        """Initializes the async driver connection and runs schema initializations."""
        self.driver = AsyncGraphDatabase.driver(
            self.uri, auth=(self.user, self.password)
        )
        # Validate connection
        await self.driver.verify_connectivity()
        # Initialize unique constraints
        await initialize_neo4j_schema(self.driver)
        logger.info("Connected to Neo4j database at %s", self.uri)

    async def close(self):
        """Closes driver connection."""
        if self.driver:
            await self.driver.close()
            logger.info("Closed Neo4j driver connection.")

    async def create_node(self, label: str, key_field: str, properties: Dict[str, Any]) -> None:
        """
        Creates or updates a node in the graph database.
        Uses MERGE on the specified key_field to prevent duplication.
        """
        if not self.driver:
            raise RuntimeError("Database driver not connected. Call connect() first.")
        
        # Build dynamic Cypher query safely since labels and key_field are internal configuration strings
        query = f"""
        MERGE (n:{label} {{{key_field}: $key_value}})
        ON CREATE SET n += $props, n.created_at = timestamp()
        ON MATCH SET n += $props, n.updated_at = timestamp()
        """
        key_value = properties.get(key_field)
        if key_value is None:
            raise ValueError(f"Properties dictionary must contain key field '{key_field}'")

        # Strip key_field from properties to avoid duplicate storage inside props map
        props_to_save = {k: v for k, v in properties.items() if k != key_field}

        async with self.driver.session() as session:
            await session.run(query, key_value=key_value, props=props_to_save)

    async def create_relationship(
        self,
        source_label: str, source_key: str, source_val: str,
        rel_type: str,
        target_label: str, target_key: str, target_val: str
    ) -> None:
        """
        Creates a directed relationship between two nodes in the database.
        """
        if not self.driver:
            raise RuntimeError("Database driver not connected.")

        query = f"""
        MATCH (a:{source_label} {{{source_key}: $source_val}})
        MATCH (b:{target_label} {{{target_key}: $target_val}})
        MERGE (a)-[r:{rel_type}]->(b)
        ON CREATE SET r.created_at = timestamp()
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                source_val=source_val,
                target_val=target_val
            )
            logger.debug(
                "Created relationship (%s: %s) -[:%s]-> (%s: %s)",
                source_label, source_val, rel_type, target_label, target_val
            )

    async def check_node_freshness(self, label: str, key_field: str, key_value: str, max_age_seconds: int) -> bool:
        """
        Queries Neo4j to check if a node exists and was updated (or created)
        within the max_age_seconds threshold.
        """
        if not self.driver:
            return False

        query = f"""
        MATCH (n:{label} {{{key_field}: $key_value}})
        RETURN n.updated_at AS updated, n.created_at AS created
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, key_value=key_value)
                record = await result.single()
                if not record:
                    return False
                
                # Milliseconds timestamp from Neo4j
                ts = record["updated"] or record["created"]
                if not ts:
                    return False
                
                current_ms = int(time.time() * 1000)
                age_seconds = (current_ms - ts) / 1000.0
                return age_seconds <= max_age_seconds
        except Exception as e:
            logger.warning("Failed to check node freshness in database: %s", e)
            return False

