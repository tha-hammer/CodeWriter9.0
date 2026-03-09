use crate::types::NodeId;

#[derive(Debug, thiserror::Error)]
pub enum RegistryError {
    #[error("node not found: {0}")]
    NodeNotFound(NodeId),

    #[error("adding edge {from} -> {to} would create a cycle")]
    CycleDetected { from: NodeId, to: NodeId },

    #[error("serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, RegistryError>;
