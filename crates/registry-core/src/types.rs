use serde::{Deserialize, Serialize};
use std::fmt;

/// A node identifier in the registry DAG.
/// Format: `<prefix>-<suffix>` where prefix is 2-3 chars, suffix is 4 chars base36.
/// Examples: `db-b7r2`, `api-m5g7`, `gwt-0001`, `req-0001`
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize, PartialOrd, Ord)]
pub struct NodeId(pub String);

impl NodeId {
    pub fn new(id: impl Into<String>) -> Self {
        Self(id.into())
    }

    pub fn prefix(&self) -> &str {
        self.0.split('-').next().unwrap_or("")
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for NodeId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl From<&str> for NodeId {
    fn from(s: &str) -> Self {
        Self(s.to_string())
    }
}

/// The kind of node in the registry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NodeKind {
    /// A resource from the schema files (the 41 existing resources)
    Resource,
    /// A requirement (natural language user intent)
    Requirement,
    /// A behavior (GWT: given/when/then)
    Behavior,
    /// A constraint (techstack, perf, security)
    Constraint,
    /// A TLA+ spec fragment
    Spec,
    /// A test derived from a spec
    Test,
    /// An implementation module
    Module,
}

/// A node in the registry DAG.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    pub id: NodeId,
    pub kind: NodeKind,
    pub name: String,
    pub description: String,
    /// Schema prefix for resource nodes (db, api, mq, ui, cfg, fs)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub schema: Option<String>,
    /// Path in the source schema
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    /// Source schema file
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_schema: Option<String>,
    /// Source key within the schema file
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_key: Option<String>,
    /// Monotonic version counter
    pub version: u32,
    /// GWT fields for behavior nodes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub given: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub when: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub then: Option<String>,
    /// Free-form text for requirements
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
}

impl Node {
    pub fn resource(id: impl Into<NodeId>, name: impl Into<String>, desc: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            kind: NodeKind::Resource,
            name: name.into(),
            description: desc.into(),
            schema: None,
            path: None,
            source_schema: None,
            source_key: None,
            version: 1,
            given: None,
            when: None,
            then: None,
            text: None,
        }
    }

    pub fn behavior(
        id: impl Into<NodeId>,
        name: impl Into<String>,
        given: impl Into<String>,
        when: impl Into<String>,
        then: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            kind: NodeKind::Behavior,
            name: name.into(),
            description: String::new(),
            schema: None,
            path: None,
            source_schema: None,
            source_key: None,
            version: 1,
            given: Some(given.into()),
            when: Some(when.into()),
            then: Some(then.into()),
            text: None,
        }
    }

    pub fn requirement(id: impl Into<NodeId>, text: impl Into<String>) -> Self {
        let text_val = text.into();
        Self {
            id: id.into(),
            kind: NodeKind::Requirement,
            name: String::new(),
            description: String::new(),
            schema: None,
            path: None,
            source_schema: None,
            source_key: None,
            version: 1,
            given: None,
            when: None,
            then: None,
            text: Some(text_val),
        }
    }
}

/// Edge type describing the relationship between two nodes.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EdgeType {
    /// Module imports another module
    Imports,
    /// Service/handler calls a DAO/processor function
    Calls,
    /// Named dependency relationship
    DependsOn,
    /// Endpoint delegates to a request handler
    Handles,
    /// Endpoint applies filters
    Filters,
    /// Frontend data_loader/api_contract references backend endpoint
    References,
    /// Interceptor implements a shared interface
    ImplementsInterface,
    /// Process chain chains interceptors/processors
    Chains,
    /// Verifier validates a structure/field
    Validates,
    /// Data structure has a relation to another
    RelatesTo,
    /// Transformer reads from input type
    TransformsFrom,
    /// Transformer writes to output type
    TransformsTo,
    /// Module contains a component
    Contains,
    /// Navigation loads data via a data loader
    Loads,
    /// Navigation is guarded by access control
    Guards,
    /// Requirement decomposes into behaviors
    Decomposes,
    /// Spec models a behavior
    Models,
    /// Test verifies a spec
    Verifies,
    /// Module implements a test
    Implements,
    /// Constraint limits a behavior
    Constrains,
}

impl fmt::Display for EdgeType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Imports => write!(f, "imports"),
            Self::Calls => write!(f, "calls"),
            Self::DependsOn => write!(f, "depends_on"),
            Self::Handles => write!(f, "handles"),
            Self::Filters => write!(f, "filters"),
            Self::References => write!(f, "references"),
            Self::ImplementsInterface => write!(f, "implements_interface"),
            Self::Chains => write!(f, "chains"),
            Self::Validates => write!(f, "validates"),
            Self::RelatesTo => write!(f, "relates_to"),
            Self::TransformsFrom => write!(f, "transforms_from"),
            Self::TransformsTo => write!(f, "transforms_to"),
            Self::Contains => write!(f, "contains"),
            Self::Loads => write!(f, "loads"),
            Self::Guards => write!(f, "guards"),
            Self::Decomposes => write!(f, "decomposes"),
            Self::Models => write!(f, "models"),
            Self::Verifies => write!(f, "verifies"),
            Self::Implements => write!(f, "implements"),
            Self::Constrains => write!(f, "constrains"),
        }
    }
}

/// A directed edge in the registry DAG.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Edge {
    pub from: NodeId,
    pub to: NodeId,
    pub edge_type: EdgeType,
}

impl Edge {
    pub fn new(from: impl Into<NodeId>, to: impl Into<NodeId>, edge_type: EdgeType) -> Self {
        Self {
            from: from.into(),
            to: to.into(),
            edge_type,
        }
    }
}

/// A connected component in the graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Component {
    pub id: String,
    pub members: Vec<NodeId>,
}

/// Result of a context query.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    /// The queried node
    pub root: NodeId,
    /// All transitive dependencies (nodes reachable from root)
    pub transitive_deps: Vec<NodeId>,
    /// Direct edges from the root
    pub direct_edges: Vec<Edge>,
    /// All edges within the transitive closure
    pub all_edges: Vec<Edge>,
    /// The connected component this node belongs to
    pub component_id: Option<String>,
}
