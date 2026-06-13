import logging
from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

# Node labels
LABEL_DOMAIN = "Domain"
LABEL_IP = "IP"
LABEL_CERT = "Certificate"
LABEL_ENTITY = "Entity"
LABEL_ADDRESS = "Address"
LABEL_FAVICON = "Favicon"

# Relationship types
REL_OWNED_BY = "OWNED_BY"
REL_HOSTS = "HOSTS"
REL_SHARES_CERT = "SHARES_CERT"
REL_LOCATED_AT = "LOCATED_AT"
REL_ASSOCIATED_WITH = "ASSOCIATED_WITH"
REL_HAS_FAVICON = "HAS_FAVICON"

# Cypher statements to set up constraints and indexes
INIT_CONSTRAINTS = [
    # Domain uniqueness constraint on FQDN 'name'
    "CREATE CONSTRAINT domain_name_uniq IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
    # IP uniqueness constraint on 'address'
    "CREATE CONSTRAINT ip_address_uniq IF NOT EXISTS FOR (i:IP) REQUIRE i.address IS UNIQUE",
    # Certificate uniqueness constraint on SHA-256 fingerprint
    "CREATE CONSTRAINT cert_sha_uniq IF NOT EXISTS FOR (c:Certificate) REQUIRE c.sha256 IS UNIQUE",
    # Entity uniqueness constraint on 'id'
    "CREATE CONSTRAINT entity_id_uniq IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    # Address uniqueness constraint on 'id'
    "CREATE CONSTRAINT address_id_uniq IF NOT EXISTS FOR (a:Address) REQUIRE a.id IS UNIQUE",
    # Favicon uniqueness constraint on 'id'
    "CREATE CONSTRAINT favicon_id_uniq IF NOT EXISTS FOR (f:Favicon) REQUIRE f.id IS UNIQUE",
]

async def initialize_neo4j_schema(driver: AsyncDriver) -> None:
    """
    Connects to Neo4j and initializes unique constraints and indexes.
    """
    logger.info("Initializing Neo4j schema, constraints, and indexes.")
    async with driver.session() as session:
        for stmt in INIT_CONSTRAINTS:
            try:
                await session.run(stmt)
                logger.debug("Successfully executed schema statement: %s", stmt)
            except Exception as e:
                logger.error("Failed to execute schema statement '%s': %s", stmt, e)
                # Some Neo4j versions might have varying syntax or require enterprise for certain constraints,
                # but standard unique constraints are supported on Neo4j Community Edition.
