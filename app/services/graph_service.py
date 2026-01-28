"""
Graph database service for Neo4j.

Implements investigation relationship graph using Neo4j.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError
from neo4j.time import Date, DateTime, Time, Duration
from flask import current_app
from app.models.graph import (
    GraphNode, GraphRelationship, NodeType, RelationshipType,
    PersonNode, CompanyNode, PhoneNode, EmailNode, VehicleNode,
    AddressNode, EvidenceNode, SocialProfileNode
)


class GraphService:
    """
    Service for managing investigation graph in Neo4j.

    Provides methods for creating nodes, relationships, and querying the graph.
    """

    def __init__(self):
        """Initialize Graph Service."""
        self._driver: Optional[Driver] = None

    @staticmethod
    def _convert_neo4j_types(obj: Any) -> Any:
        """
        Convert Neo4j types to JSON-serializable Python types.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable version of the object
        """
        if isinstance(obj, (Date, DateTime)):
            # Convert Neo4j Date/DateTime to ISO string
            return obj.iso_format()
        elif isinstance(obj, Time):
            # Convert Neo4j Time to ISO string
            return obj.iso_format()
        elif isinstance(obj, Duration):
            # Convert Duration to total seconds
            return obj.months * 2592000 + obj.days * 86400 + obj.seconds + obj.nanoseconds / 1e9
        elif isinstance(obj, dict):
            # Recursively convert dictionary values
            return {key: GraphService._convert_neo4j_types(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            # Recursively convert list/tuple items
            return [GraphService._convert_neo4j_types(item) for item in obj]
        else:
            # Return as-is for basic types
            return obj

    def _get_driver(self) -> Driver:
        """
        Get or create Neo4j driver.

        Returns:
            Neo4j driver instance

        Raises:
            ServiceUnavailable: If Neo4j is not accessible
            AuthError: If authentication fails
        """
        if self._driver is None:
            uri = current_app.config.get('NEO4J_URI', 'bolt://neo4j:7687')
            user = current_app.config.get('NEO4J_USER', 'neo4j')
            password = current_app.config.get('NEO4J_PASSWORD', 'password')

            try:
                self._driver = GraphDatabase.driver(uri, auth=(user, password))
                # Verify connectivity
                self._driver.verify_connectivity()
            except Exception as e:
                current_app.logger.error(f'Failed to connect to Neo4j: {e}')
                raise

        return self._driver

    def close(self):
        """Close Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def create_constraints(self):
        """
        Create Neo4j constraints and indexes.

        Ensures unique identifiers and improves query performance.
        """
        driver = self._get_driver()

        constraints = [
            # Person constraints
            "CREATE CONSTRAINT person_dni IF NOT EXISTS FOR (p:Person) REQUIRE p.dni_cif IS UNIQUE",

            # Company constraints
            "CREATE CONSTRAINT company_cif IF NOT EXISTS FOR (c:Company) REQUIRE c.cif IS UNIQUE",

            # Phone constraints
            "CREATE CONSTRAINT phone_number IF NOT EXISTS FOR (ph:Phone) REQUIRE ph.number IS UNIQUE",

            # Email constraints
            "CREATE CONSTRAINT email_address IF NOT EXISTS FOR (e:Email) REQUIRE e.address IS UNIQUE",

            # Vehicle constraints
            "CREATE CONSTRAINT vehicle_plate IF NOT EXISTS FOR (v:Vehicle) REQUIRE v.plate IS UNIQUE",

            # Evidence constraints
            "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (ev:Evidence) REQUIRE ev.evidence_id IS UNIQUE",
        ]

        indexes = [
            # Indexes for common queries
            "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
            "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
            "CREATE INDEX address_city IF NOT EXISTS FOR (a:Address) ON (a.city)",
            "CREATE INDEX social_username IF NOT EXISTS FOR (s:SocialProfile) ON (s.username)",
            # Indexes for case_id filtering (critical for multi-tenant isolation)
            "CREATE INDEX person_case_id IF NOT EXISTS FOR (p:Person) ON (p.case_id)",
            "CREATE INDEX company_case_id IF NOT EXISTS FOR (c:Company) ON (c.case_id)",
            "CREATE INDEX phone_case_id IF NOT EXISTS FOR (ph:Phone) ON (ph.case_id)",
            "CREATE INDEX email_case_id IF NOT EXISTS FOR (e:Email) ON (e.case_id)",
            "CREATE INDEX vehicle_case_id IF NOT EXISTS FOR (v:Vehicle) ON (v.case_id)",
            "CREATE INDEX address_case_id IF NOT EXISTS FOR (a:Address) ON (a.case_id)",
            "CREATE INDEX evidence_case_id IF NOT EXISTS FOR (ev:Evidence) ON (ev.case_id)",
            "CREATE INDEX social_case_id IF NOT EXISTS FOR (s:SocialProfile) ON (s.case_id)",
        ]

        with driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    current_app.logger.warning(f'Constraint creation warning: {e}')

            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    current_app.logger.warning(f'Index creation warning: {e}')

        current_app.logger.info('Neo4j constraints and indexes created')

    @staticmethod
    def _sanitize_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize properties for Neo4j storage.

        Neo4j only accepts primitive types (str, int, float, bool) or arrays thereof.
        This method filters out None values and converts dicts to JSON strings.

        Args:
            properties: Dictionary of properties

        Returns:
            Sanitized properties dictionary
        """
        import json
        sanitized = {}
        for key, value in properties.items():
            if value is None:
                continue  # Skip None values
            elif isinstance(value, dict):
                # Convert dicts to JSON strings
                sanitized[key] = json.dumps(value) if value else None
                if sanitized[key] is None:
                    del sanitized[key]
            elif isinstance(value, (list, tuple)):
                # For lists, ensure all elements are primitives
                if all(isinstance(v, (str, int, float, bool)) for v in value):
                    sanitized[key] = list(value)
                else:
                    # Convert complex lists to JSON
                    sanitized[key] = json.dumps(value)
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            else:
                # Convert other types to string
                sanitized[key] = str(value)
        return sanitized

    def create_node(self, node: GraphNode, case_id: int) -> str:
        """
        Create a node in the graph.

        Args:
            node: GraphNode instance
            case_id: Case ID this node belongs to

        Returns:
            Neo4j node ID
        """
        driver = self._get_driver()

        # Add case_id to properties
        node.properties['case_id'] = case_id
        node.properties['updated_at'] = datetime.utcnow().isoformat()

        # Sanitize properties for Neo4j compatibility
        sanitized_props = self._sanitize_properties(node.properties)

        query = f"""
        CREATE (n:{node.node_type.value} $properties)
        RETURN elementId(n) as node_id
        """

        with driver.session() as session:
            result = session.run(query, properties=sanitized_props)
            record = result.single()
            return str(record['node_id'])

    def get_node(self, node_id: str, node_type: NodeType) -> Optional[GraphNode]:
        """
        Get a node by ID.

        Args:
            node_id: Neo4j node ID
            node_type: Type of node

        Returns:
            GraphNode instance or None
        """
        driver = self._get_driver()

        query = f"""
        MATCH (n:{node_type.value})
        WHERE elementId(n) = $node_id
        RETURN n
        """

        with driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()

            if record:
                return GraphNode.from_neo4j(record['n'], node_type)
            return None

    def update_node(self, node_id: str, node_type: NodeType, properties: Dict[str, Any]) -> bool:
        """
        Update node properties.

        Args:
            node_id: Neo4j node ID
            node_type: Type of node
            properties: Properties to update

        Returns:
            True if successful
        """
        driver = self._get_driver()

        # Add updated timestamp
        properties['updated_at'] = datetime.utcnow().isoformat()

        # Sanitize properties for Neo4j compatibility
        sanitized_props = self._sanitize_properties(properties)

        query = f"""
        MATCH (n:{node_type.value})
        WHERE elementId(n) = $node_id
        SET n += $properties
        RETURN n
        """

        with driver.session() as session:
            result = session.run(query, node_id=node_id, properties=sanitized_props)
            return result.single() is not None

    def delete_node(self, node_id: str, node_type: NodeType) -> bool:
        """
        Delete a node and all its relationships.

        Args:
            node_id: Neo4j node ID
            node_type: Type of node

        Returns:
            True if successful
        """
        driver = self._get_driver()

        query = f"""
        MATCH (n:{node_type.value})
        WHERE elementId(n) = $node_id
        DETACH DELETE n
        """

        with driver.session() as session:
            result = session.run(query, node_id=node_id)
            return result.consume().counters.nodes_deleted > 0

    def create_relationship(self, relationship: GraphRelationship) -> str:
        """
        Create a relationship between two nodes.

        Args:
            relationship: GraphRelationship instance

        Returns:
            Neo4j relationship ID
        """
        driver = self._get_driver()

        relationship.properties['updated_at'] = datetime.utcnow().isoformat()

        # Handle both enum and string relationship types
        from app.models.graph import RelationshipType
        if isinstance(relationship.relationship_type, RelationshipType):
            rel_type_str = relationship.relationship_type.value
        else:
            rel_type_str = relationship.relationship_type

        # Sanitize properties for Neo4j compatibility
        sanitized_props = self._sanitize_properties(relationship.properties)

        query = f"""
        MATCH (from_node), (to_node)
        WHERE elementId(from_node) = $from_id AND elementId(to_node) = $to_id
        CREATE (from_node)-[r:{rel_type_str} $properties]->(to_node)
        RETURN elementId(r) as rel_id
        """

        with driver.session() as session:
            result = session.run(
                query,
                from_id=relationship.from_node_id,
                to_id=relationship.to_node_id,
                properties=sanitized_props
            )
            record = result.single()
            return str(record['rel_id'])

    def get_relationships(self, node_id: str, relationship_type: Optional[RelationshipType] = None) -> List[GraphRelationship]:
        """
        Get all relationships for a node.

        Args:
            node_id: Neo4j node ID
            relationship_type: Optional filter by relationship type

        Returns:
            List of GraphRelationship instances
        """
        driver = self._get_driver()

        if relationship_type:
            query = f"""
            MATCH (n)-[r:{relationship_type.value}]-(m)
            WHERE elementId(n) = $node_id
            RETURN r, elementId(startNode(r)) as from_id, elementId(endNode(r)) as to_id
            """
        else:
            query = """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $node_id
            RETURN r, type(r) as rel_type, elementId(startNode(r)) as from_id, elementId(endNode(r)) as to_id
            """

        relationships = []
        with driver.session() as session:
            result = session.run(query, node_id=node_id)

            for record in result:
                if relationship_type:
                    rel_type = relationship_type
                else:
                    rel_type = RelationshipType(record['rel_type'])

                rel = GraphRelationship.from_neo4j(
                    record['r'],
                    rel_type,
                    str(record['from_id']),
                    str(record['to_id'])
                )
                relationships.append(rel)

        return relationships

    def update_relationship(self, relationship_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update relationship properties.

        Args:
            relationship_id: Neo4j relationship ID
            properties: Properties to update

        Returns:
            True if successful
        """
        driver = self._get_driver()

        # Add updated timestamp
        properties['updated_at'] = datetime.utcnow().isoformat()

        # Sanitize properties for Neo4j compatibility
        sanitized_props = self._sanitize_properties(properties)

        query = """
        MATCH ()-[r]->()
        WHERE elementId(r) = $rel_id
        SET r += $properties
        RETURN r
        """

        with driver.session() as session:
            result = session.run(query, rel_id=relationship_id, properties=sanitized_props)
            return result.single() is not None

    def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.

        Args:
            relationship_id: Neo4j relationship ID

        Returns:
            True if successful
        """
        driver = self._get_driver()

        query = """
        MATCH ()-[r]->()
        WHERE elementId(r) = $rel_id
        DELETE r
        """

        with driver.session() as session:
            result = session.run(query, rel_id=relationship_id)
            return result.consume().counters.relationships_deleted > 0

    def get_case_graph(self, case_id: int, max_depth: int = 3) -> Dict[str, Any]:
        """
        Get the complete graph for a case.

        Args:
            case_id: Case ID
            max_depth: Maximum traversal depth

        Returns:
            Dictionary with nodes and relationships
        """
        driver = self._get_driver()

        query = f"""
        MATCH (n)
        WHERE n.case_id = $case_id
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE m.case_id = $case_id
        RETURN
            collect(DISTINCT {{id: elementId(n), labels: labels(n), properties: n}}) as nodes,
            collect(DISTINCT {{id: elementId(r), type: type(r), from: elementId(startNode(r)), to: elementId(endNode(r)), properties: r}}) as relationships
        """

        with driver.session() as session:
            result = session.run(query, case_id=case_id)
            record = result.single()

            if not record:
                return {'nodes': [], 'relationships': []}

            # Format nodes
            nodes = []
            for node_data in record['nodes']:
                if node_data['id'] is not None:  # Skip null nodes
                    # Convert Neo4j types in properties to JSON-serializable types
                    properties = self._convert_neo4j_types(dict(node_data['properties']))
                    nodes.append({
                        'id': str(node_data['id']),
                        'label': node_data['labels'][0] if node_data['labels'] else 'Unknown',
                        'properties': properties
                    })

            # Format relationships
            relationships = []
            for rel_data in record['relationships']:
                if rel_data['id'] is not None:  # Skip null relationships
                    # Convert Neo4j types in properties to JSON-serializable types
                    properties = self._convert_neo4j_types(dict(rel_data['properties'])) if rel_data['properties'] else {}
                    relationships.append({
                        'id': str(rel_data['id']),
                        'type': rel_data['type'],
                        'from': str(rel_data['from']),
                        'to': str(rel_data['to']),
                        'properties': properties
                    })

            return {
                'nodes': nodes,
                'relationships': relationships
            }

    def find_shortest_path(self, from_node_id: str, to_node_id: str, max_hops: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Find shortest path between two nodes.

        Args:
            from_node_id: Source node ID
            to_node_id: Target node ID
            max_hops: Maximum number of hops

        Returns:
            List of nodes in path or None if no path exists
        """
        driver = self._get_driver()

        query = f"""
        MATCH path = shortestPath(
            (from_node)-[*..{max_hops}]-(to_node)
        )
        WHERE elementId(from_node) = $from_id AND elementId(to_node) = $to_id
        RETURN [node in nodes(path) | {{id: elementId(node), labels: labels(node), properties: node}}] as path_nodes,
               [rel in relationships(path) | {{type: type(rel), properties: rel}}] as path_rels
        """

        with driver.session() as session:
            result = session.run(
                query,
                from_id=from_node_id,
                to_id=to_node_id
            )
            record = result.single()

            if not record:
                return None

            return {
                'nodes': record['path_nodes'],
                'relationships': record['path_rels']
            }

    def find_common_connections(self, node_id_1: str, node_id_2: str) -> List[Dict[str, Any]]:
        """
        Find common connections between two nodes.

        Args:
            node_id_1: First node ID
            node_id_2: Second node ID

        Returns:
            List of common connected nodes
        """
        driver = self._get_driver()

        query = """
        MATCH (n1)--(common)--(n2)
        WHERE elementId(n1) = $node_1 AND elementId(n2) = $node_2 AND elementId(common) <> $node_1 AND elementId(common) <> $node_2
        RETURN DISTINCT elementId(common) as id, labels(common) as labels, common
        """

        common_nodes = []
        with driver.session() as session:
            result = session.run(query, node_1=node_id_1, node_2=node_id_2)

            for record in result:
                common_nodes.append({
                    'id': str(record['id']),
                    'label': record['labels'][0] if record['labels'] else 'Unknown',
                    'properties': dict(record['common'])
                })

        return common_nodes

    def search_nodes(self, case_id: int, query: str, node_type: Optional[NodeType] = None) -> List[Dict[str, Any]]:
        """
        Search nodes by properties.

        Args:
            case_id: Case ID
            query: Search query
            node_type: Optional filter by node type

        Returns:
            List of matching nodes
        """
        driver = self._get_driver()

        if node_type:
            cypher_query = f"""
            MATCH (n:{node_type.value})
            WHERE n.case_id = $case_id AND (
                toLower(toString(n.name)) CONTAINS toLower($query) OR
                toLower(toString(n.dni_cif)) CONTAINS toLower($query) OR
                toLower(toString(n.cif)) CONTAINS toLower($query) OR
                toLower(toString(n.number)) CONTAINS toLower($query) OR
                toLower(toString(n.address)) CONTAINS toLower($query) OR
                toLower(toString(n.plate)) CONTAINS toLower($query) OR
                toLower(toString(n.username)) CONTAINS toLower($query)
            )
            RETURN elementId(n) as id, labels(n) as labels, n
            LIMIT 50
            """
        else:
            cypher_query = """
            MATCH (n)
            WHERE n.case_id = $case_id AND (
                toLower(toString(n.name)) CONTAINS toLower($query) OR
                toLower(toString(n.dni_cif)) CONTAINS toLower($query) OR
                toLower(toString(n.cif)) CONTAINS toLower($query) OR
                toLower(toString(n.number)) CONTAINS toLower($query) OR
                toLower(toString(n.address)) CONTAINS toLower($query) OR
                toLower(toString(n.plate)) CONTAINS toLower($query) OR
                toLower(toString(n.username)) CONTAINS toLower($query)
            )
            RETURN elementId(n) as id, labels(n) as labels, n
            LIMIT 50
            """

        results = []
        with driver.session() as session:
            result = session.run(cypher_query, case_id=case_id, query=query)

            for record in result:
                results.append({
                    'id': str(record['id']),
                    'label': record['labels'][0] if record['labels'] else 'Unknown',
                    'properties': dict(record['n'])
                })

        return results

    def get_node_degree(self, node_id: str) -> Dict[str, int]:
        """
        Get the degree (number of connections) for a node.

        Args:
            node_id: Neo4j node ID

        Returns:
            Dictionary with in_degree, out_degree, and total_degree
        """
        driver = self._get_driver()

        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        OPTIONAL MATCH (n)<-[r_in]-()
        OPTIONAL MATCH (n)-[r_out]->()
        RETURN count(DISTINCT r_in) as in_degree, count(DISTINCT r_out) as out_degree
        """

        with driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()

            in_deg = record['in_degree'] or 0
            out_deg = record['out_degree'] or 0

            return {
                'in_degree': in_deg,
                'out_degree': out_deg,
                'total_degree': in_deg + out_deg
            }

    def get_graph_statistics(self, case_id: int) -> Dict[str, Any]:
        """
        Get statistics for a case graph.

        Args:
            case_id: Case ID

        Returns:
            Dictionary with graph statistics
        """
        driver = self._get_driver()

        query = """
        MATCH (n)
        WHERE n.case_id = $case_id
        OPTIONAL MATCH (n)-[r]-()
        WHERE r.case_id = $case_id OR startNode(r).case_id = $case_id
        RETURN
            count(DISTINCT n) as node_count,
            count(DISTINCT r) as relationship_count,
            collect(DISTINCT labels(n)) as node_types
        """

        with driver.session() as session:
            result = session.run(query, case_id=case_id)
            record = result.single()

            # Count nodes by type
            node_type_counts = {}
            for node_type_list in record['node_types']:
                if node_type_list:
                    node_type = node_type_list[0]
                    node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1

            return {
                'total_nodes': record['node_count'] or 0,
                'total_relationships': record['relationship_count'] or 0,
                'node_types': node_type_counts
            }

    def clear_case_graph(self, case_id: int) -> bool:
        """
        Delete all nodes and relationships for a case.

        Args:
            case_id: Case ID

        Returns:
            True if successful
        """
        driver = self._get_driver()

        query = """
        MATCH (n)
        WHERE n.case_id = $case_id
        DETACH DELETE n
        """

        with driver.session() as session:
            result = session.run(query, case_id=case_id)
            counters = result.consume().counters

            current_app.logger.info(
                f'Deleted {counters.nodes_deleted} nodes and '
                f'{counters.relationships_deleted} relationships for case {case_id}'
            )

            return counters.nodes_deleted > 0
