from datetime import datetime, timezone
from typing import List, Optional, Literal, Union, Tuple
from pydantic import BaseModel, Field, field_validator
import re
import ipaddress

# Domain regex validator
DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,6}$"
)

class DomainModel(BaseModel):
    name: str = Field(..., description="Fully qualified domain name (FQDN)")
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = Field(default_factory=list)
    registrar: Optional[str] = Field(None, description="Domain registrar name")
    creation_date: Optional[datetime] = Field(None, description="Domain registration date")

    @field_validator("name")
    @classmethod
    def validate_domain_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not DOMAIN_REGEX.match(v):
            raise ValueError(f"Invalid domain name format: {v}")
        return v


class IPModel(BaseModel):
    address: str = Field(..., description="IPv4 or IPv6 address")
    asn: Optional[int] = Field(None, description="Autonomous System Number")
    hosting_provider: Optional[str] = Field(None, description="Name of hosting company")
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("address")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        v = v.strip()
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError(f"Invalid IP address format: {v}")
        return v


class CertificateModel(BaseModel):
    sha256: str = Field(..., description="SHA-256 fingerprint of the certificate")
    issuer: str = Field(..., description="Certificate Authority issuer CN")
    subject: str = Field(..., description="Subject CN")
    valid_from: datetime = Field(...)
    valid_to: datetime = Field(...)
    sans: List[str] = Field(default_factory=list, description="Subject Alternative Names (SANs)")

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-f0-9]{64}$", v):
            raise ValueError("SHA-256 fingerprint must be exactly 64 hex characters")
        return v


class EntityModel(BaseModel):
    id: str = Field(..., description="Unique identifier for the corporate or physical entity")
    name: str = Field(..., description="Legal name of individual or company")
    type: Literal["Individual", "Company"] = Field(...)
    jurisdiction: Optional[str] = Field(None, description="State/Country of filing or incorporation")
    registration_number: Optional[str] = Field(None, description="Corporate filing ID / LLC number")


class AddressModel(BaseModel):
    id: str = Field(..., description="Unique hash or string representing this address")
    full_address: str = Field(..., description="Full textual representation of address")
    country: Optional[str] = None
    city: Optional[str] = None


class FaviconModel(BaseModel):
    id: str = Field(..., description="Favicon unique MD5 hash fingerprint")
    md5: str = Field(..., description="MD5 hash of favicon file")
    sha256: Optional[str] = Field(None, description="SHA-256 hash of favicon file")


NodeModelType = Union[DomainModel, IPModel, CertificateModel, EntityModel, AddressModel, FaviconModel]


class CollectorResult(BaseModel):
    """
    Standardized payload returned by all collection modules.
    Contains nodes discovered and directed relationships between them.
    """
    nodes: List[NodeModelType] = Field(default_factory=list)
    # Relationships are represented as tuples: (source_node_type, source_node_key_field, source_node_key_value, 
    #                                          relationship_type, 
    #                                          target_node_type, target_node_key_field, target_node_key_value)
    # Example: ("Domain", "name", "example.com", "HOSTS", "IP", "address", "192.0.2.1")
    relationships: List[Tuple[str, str, str, str, str, str, str]] = Field(default_factory=list)

