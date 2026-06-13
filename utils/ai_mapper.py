import hashlib
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from pydantic import BaseModel, Field
from asset_intel.models import EntityModel, AddressModel, CollectorResult

logger = logging.getLogger(__name__)

class FilingAddressSchema(BaseModel):
    street: str
    city: str
    state: str
    zip_code: Optional[str] = None
    country: str = "US"

class PersonSchema(BaseModel):
    name: str
    role: str  # e.g., Member, Manager, Registered Agent, President
    address: Optional[FilingAddressSchema] = None

class CorporateFilingSchema(BaseModel):
    """
    Represents the structured JSON schema that might be exported from filings.
    This schema guides the mapping utility to normalize the JSON.
    """
    company_name: str
    registration_number: str
    jurisdiction: str
    filing_date: Optional[str] = None
    registered_address: FilingAddressSchema
    principals: List[PersonSchema] = Field(default_factory=list)


class CorporateFilingMapper:
    """
    Translates raw and structured JSON corporate record exports into
    validated Pydantic models for the Neo4j schema representation.
    """

    @staticmethod
    def generate_address_id(addr: FilingAddressSchema) -> str:
        """Generates a deterministic hash key for an address to prevent duplicates in Neo4j."""
        raw = f"{addr.street.strip().lower()}|{addr.city.strip().lower()}|{addr.state.strip().lower()}|{addr.country.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_person_id(name: str) -> str:
        """Generates a deterministic ID for a person entity."""
        return "entity_" + hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()[:16]

    @classmethod
    def map_scc_json(cls, raw_json_str: str) -> CollectorResult:
        """
        Parses raw corporate filing JSON, validates against the expected schema,
        and generates a CollectorResult consisting of Entities, Addresses, and Relationships.
        
        Args:
            raw_json_str: String containing the corporate JSON filing.
            
        Returns:
            CollectorResult: Validated models (Entity, Address) and relationship mappings.
        """
        raw_data = json.loads(raw_json_str)
        # Validate raw data using our schema
        filing = CorporateFilingSchema(**raw_data)
        
        nodes = []
        relationships = []

        # 1. Create the primary Corporate Entity
        company_id = f"entity_{filing.registration_number.strip().lower()}"
        company_node = EntityModel(
            id=company_id,
            name=filing.company_name,
            type="Company",
            jurisdiction=filing.jurisdiction,
            registration_number=filing.registration_number
        )
        nodes.append(company_node)

        # 2. Create and associate the Registered Corporate Address
        addr_id = cls.generate_address_id(filing.registered_address)
        full_addr_str = f"{filing.registered_address.street}, {filing.registered_address.city}, {filing.registered_address.state} {filing.registered_address.zip_code or ''}, {filing.registered_address.country}"
        
        addr_node = AddressModel(
            id=addr_id,
            full_address=full_addr_str,
            city=filing.registered_address.city,
            country=filing.registered_address.country
        )
        nodes.append(addr_node)
        
        # Link Company -[:LOCATED_AT]-> Address
        relationships.append((
            "Entity", "id", company_id,
            "LOCATED_AT",
            "Address", "id", addr_id
        ))

        # 3. Process corporate principals (Members, Managers, Owners)
        for principal in filing.principals:
            p_id = cls.generate_person_id(principal.name)
            
            p_node = EntityModel(
                id=p_id,
                name=principal.name,
                type="Individual"
            )
            nodes.append(p_node)

            # Map the relationship: Individual -[:OWNED_BY or :ASSOCIATED_WITH]-> Company
            # For our graph, if they are members/managers, they own/run it. Let's use OWNED_BY or ASSOCIATED_WITH.
            # We map: Company -[:OWNED_BY]-> Individual or Individual -[:ASSOCIATED_WITH]-> Company
            rel_type = "OWNED_BY" if principal.role.lower() in ("member", "manager", "owner", "shareholder") else "ASSOCIATED_WITH"
            
            if rel_type == "OWNED_BY":
                relationships.append((
                    "Entity", "id", company_id,  # Company is owned by the Individual
                    "OWNED_BY",
                    "Entity", "id", p_id
                ))
            else:
                relationships.append((
                    "Entity", "id", p_id,
                    "ASSOCIATED_WITH",
                    "Entity", "id", company_id
                ))

            # If the principal has an address, map it
            if principal.address:
                p_addr_id = cls.generate_address_id(principal.address)
                p_full_addr_str = f"{principal.address.street}, {principal.address.city}, {principal.address.state} {principal.address.zip_code or ''}, {principal.address.country}"
                
                p_addr_node = AddressModel(
                    id=p_addr_id,
                    full_address=p_full_addr_str,
                    city=principal.address.city,
                    country=principal.address.country
                )
                nodes.append(p_addr_node)
                
                # Link Individual -[:LOCATED_AT]-> Address
                relationships.append((
                    "Entity", "id", p_id,
                    "LOCATED_AT",
                    "Address", "id", p_addr_id
                ))

        return CollectorResult(nodes=nodes, relationships=relationships)
