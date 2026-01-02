"""
Graph models for Neo4j relationship database.

Implements entity-relationship graph for investigations.
"""
from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Any


class NodeType(Enum):
    """Node types in the investigation graph."""
    PERSON = 'Person'
    COMPANY = 'Company'
    PHONE = 'Phone'
    EMAIL = 'Email'
    VEHICLE = 'Vehicle'
    ADDRESS = 'Address'
    EVIDENCE = 'Evidence'
    SOCIAL_PROFILE = 'SocialProfile'
    BANK_ACCOUNT = 'BankAccount'
    IP_ADDRESS = 'IpAddress'


class RelationshipType(Enum):
    """Relationship types in the investigation graph."""
    FAMILIAR_DE = 'FAMILIAR_DE'
    SOCIO_DE = 'SOCIO_DE'
    EMPLEADO_DE = 'EMPLEADO_DE'
    UTILIZA_TELEFONO = 'UTILIZA_TELEFONO'
    UTILIZA_EMAIL = 'UTILIZA_EMAIL'
    UTILIZA_VEHICULO = 'UTILIZA_VEHICULO'
    PROPIETARIO_DE = 'PROPIETARIO_DE'
    RESIDE_EN = 'RESIDE_EN'
    VISTO_EN = 'VISTO_EN'
    CONTACTO_CON = 'CONTACTO_CON'
    VINCULADO_A_EVIDENCIA = 'VINCULADO_A_EVIDENCIA'
    PERFIL_DE = 'PERFIL_DE'
    TITULAR_DE = 'TITULAR_DE'
    TRANSFERENCIA_A = 'TRANSFERENCIA_A'
    CONEXION_DESDE = 'CONEXION_DESDE'


class GraphNode:
    """
    Wrapper class for Neo4j nodes.

    Represents entities in the investigation graph.
    """

    def __init__(self, node_id: Optional[str], node_type: NodeType, properties: Dict[str, Any]):
        """
        Initialize graph node.

        Args:
            node_id: Neo4j node ID (None for new nodes)
            node_type: Type of node
            properties: Node properties
        """
        self.node_id = node_id
        self.node_type = node_type
        self.properties = properties

        # Ensure required properties
        if 'created_at' not in self.properties:
            self.properties['created_at'] = datetime.utcnow().isoformat()
        if 'updated_at' not in self.properties:
            self.properties['updated_at'] = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation."""
        return {
            'id': self.node_id,
            'type': self.node_type.value,
            'properties': self.properties
        }

    @classmethod
    def from_neo4j(cls, neo4j_node, node_type: NodeType):
        """
        Create GraphNode from Neo4j node result.

        Args:
            neo4j_node: Neo4j node object
            node_type: Type of node

        Returns:
            GraphNode instance
        """
        node_id = str(neo4j_node.id) if hasattr(neo4j_node, 'id') else None
        properties = dict(neo4j_node)
        return cls(node_id, node_type, properties)


class PersonNode(GraphNode):
    """Person node in the graph."""

    def __init__(self, node_id: Optional[str] = None, name: str = None,
                 dni_cif: str = None, birth_date: str = None,
                 properties: Dict[str, Any] = None):
        """
        Initialize person node.

        Args:
            node_id: Neo4j node ID
            name: Person's name
            dni_cif: DNI/CIF/NIE
            birth_date: Birth date
            properties: Additional properties
        """
        props = properties or {}
        if name:
            props['name'] = name
        if dni_cif:
            props['dni_cif'] = dni_cif
        if birth_date:
            props['birth_date'] = birth_date

        super().__init__(node_id, NodeType.PERSON, props)


class CompanyNode(GraphNode):
    """Company node in the graph."""

    def __init__(self, node_id: Optional[str] = None, name: str = None,
                 cif: str = None, properties: Dict[str, Any] = None):
        """
        Initialize company node.

        Args:
            node_id: Neo4j node ID
            name: Company name
            cif: CIF (tax ID)
            properties: Additional properties
        """
        props = properties or {}
        if name:
            props['name'] = name
        if cif:
            props['cif'] = cif

        super().__init__(node_id, NodeType.COMPANY, props)


class PhoneNode(GraphNode):
    """Phone number node in the graph."""

    def __init__(self, node_id: Optional[str] = None, number: str = None,
                 carrier: str = None, properties: Dict[str, Any] = None):
        """
        Initialize phone node.

        Args:
            node_id: Neo4j node ID
            number: Phone number
            carrier: Phone carrier
            properties: Additional properties
        """
        props = properties or {}
        if number:
            props['number'] = number
        if carrier:
            props['carrier'] = carrier

        super().__init__(node_id, NodeType.PHONE, props)


class EmailNode(GraphNode):
    """Email address node in the graph."""

    def __init__(self, node_id: Optional[str] = None, address: str = None,
                 provider: str = None, properties: Dict[str, Any] = None):
        """
        Initialize email node.

        Args:
            node_id: Neo4j node ID
            address: Email address
            provider: Email provider
            properties: Additional properties
        """
        props = properties or {}
        if address:
            props['address'] = address
        if provider:
            props['provider'] = provider

        super().__init__(node_id, NodeType.EMAIL, props)


class VehicleNode(GraphNode):
    """Vehicle node in the graph."""

    def __init__(self, node_id: Optional[str] = None, plate: str = None,
                 make: str = None, model: str = None,
                 properties: Dict[str, Any] = None):
        """
        Initialize vehicle node.

        Args:
            node_id: Neo4j node ID
            plate: License plate
            make: Vehicle make
            model: Vehicle model
            properties: Additional properties
        """
        props = properties or {}
        if plate:
            props['plate'] = plate
        if make:
            props['make'] = make
        if model:
            props['model'] = model

        super().__init__(node_id, NodeType.VEHICLE, props)


class AddressNode(GraphNode):
    """Address node in the graph."""

    def __init__(self, node_id: Optional[str] = None, street: str = None,
                 city: str = None, postal_code: str = None,
                 properties: Dict[str, Any] = None):
        """
        Initialize address node.

        Args:
            node_id: Neo4j node ID
            street: Street address
            city: City
            postal_code: Postal code
            properties: Additional properties
        """
        props = properties or {}
        if street:
            props['street'] = street
        if city:
            props['city'] = city
        if postal_code:
            props['postal_code'] = postal_code

        super().__init__(node_id, NodeType.ADDRESS, props)


class EvidenceNode(GraphNode):
    """Evidence reference node in the graph."""

    def __init__(self, node_id: Optional[str] = None, evidence_id: int = None,
                 filename: str = None, evidence_type: str = None,
                 properties: Dict[str, Any] = None):
        """
        Initialize evidence node.

        Args:
            node_id: Neo4j node ID
            evidence_id: PostgreSQL evidence.id
            filename: Evidence filename
            evidence_type: Type of evidence
            properties: Additional properties
        """
        props = properties or {}
        if evidence_id:
            props['evidence_id'] = evidence_id
        if filename:
            props['filename'] = filename
        if evidence_type:
            props['evidence_type'] = evidence_type

        super().__init__(node_id, NodeType.EVIDENCE, props)


class SocialProfileNode(GraphNode):
    """Social media profile node in the graph."""

    def __init__(self, node_id: Optional[str] = None, platform: str = None,
                 username: str = None, url: str = None,
                 properties: Dict[str, Any] = None):
        """
        Initialize social profile node.

        Args:
            node_id: Neo4j node ID
            platform: Social media platform (Facebook, Twitter, etc.)
            username: Profile username
            url: Profile URL
            properties: Additional properties
        """
        props = properties or {}
        if platform:
            props['platform'] = platform
        if username:
            props['username'] = username
        if url:
            props['url'] = url

        super().__init__(node_id, NodeType.SOCIAL_PROFILE, props)


class GraphRelationship:
    """
    Wrapper class for Neo4j relationships.

    Represents connections between entities in the investigation graph.
    """

    def __init__(self, relationship_id: Optional[str],
                 relationship_type: RelationshipType,
                 from_node_id: str, to_node_id: str,
                 properties: Dict[str, Any] = None):
        """
        Initialize graph relationship.

        Args:
            relationship_id: Neo4j relationship ID (None for new)
            relationship_type: Type of relationship
            from_node_id: Source node ID
            to_node_id: Target node ID
            properties: Relationship properties
        """
        self.relationship_id = relationship_id
        self.relationship_type = relationship_type
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.properties = properties or {}

        # Ensure required properties
        if 'created_at' not in self.properties:
            self.properties['created_at'] = datetime.utcnow().isoformat()
        if 'confidence' not in self.properties:
            self.properties['confidence'] = 1.0  # Default confidence: 100%

    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary representation."""
        return {
            'id': self.relationship_id,
            'type': self.relationship_type.value,
            'from': self.from_node_id,
            'to': self.to_node_id,
            'properties': self.properties
        }

    @classmethod
    def from_neo4j(cls, neo4j_rel, relationship_type: RelationshipType,
                   from_node_id: str, to_node_id: str):
        """
        Create GraphRelationship from Neo4j relationship result.

        Args:
            neo4j_rel: Neo4j relationship object
            relationship_type: Type of relationship
            from_node_id: Source node ID
            to_node_id: Target node ID

        Returns:
            GraphRelationship instance
        """
        rel_id = str(neo4j_rel.id) if hasattr(neo4j_rel, 'id') else None
        properties = dict(neo4j_rel)
        return cls(rel_id, relationship_type, from_node_id, to_node_id, properties)
