use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};

use crate::error::{RegistryError, Result};
use crate::types::*;

/// The registry DAG: nodes, edges, transitive closure, connected components.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RegistryDag {
    pub nodes: BTreeMap<NodeId, Node>,
    pub edges: Vec<Edge>,
    /// Transitive closure: for each node, the set of all reachable nodes.
    pub closure: BTreeMap<NodeId, BTreeSet<NodeId>>,
    /// Connected components (undirected): groups of nodes connected by any path.
    pub components: BTreeMap<String, Vec<NodeId>>,
    /// Next component ID counter
    #[serde(skip)]
    next_component_id: u32,
}

impl RegistryDag {
    pub fn new() -> Self {
        Self {
            nodes: BTreeMap::new(),
            edges: Vec::new(),
            closure: BTreeMap::new(),
            components: BTreeMap::new(),
            next_component_id: 0,
        }
    }

    /// Add a node to the DAG.
    pub fn add_node(&mut self, node: Node) -> Result<()> {
        let id = node.id.clone();
        self.nodes.insert(id.clone(), node);
        self.closure.entry(id).or_default();
        self.recompute_components();
        Ok(())
    }

    /// Add an edge to the DAG. Rejects cycles.
    pub fn add_edge(&mut self, edge: Edge) -> Result<()> {
        // Verify both endpoints exist
        if !self.nodes.contains_key(&edge.from) {
            return Err(RegistryError::NodeNotFound(edge.from.clone()));
        }
        if !self.nodes.contains_key(&edge.to) {
            return Err(RegistryError::NodeNotFound(edge.to.clone()));
        }

        // Self-loops are cycles
        if edge.from == edge.to {
            return Err(RegistryError::CycleDetected {
                from: edge.from.clone(),
                to: edge.to.clone(),
            });
        }

        // Check if adding this edge would create a cycle:
        // A cycle exists if `to` can already reach `from` in the current graph.
        if self.can_reach(&edge.to, &edge.from) {
            return Err(RegistryError::CycleDetected {
                from: edge.from.clone(),
                to: edge.to.clone(),
            });
        }

        // Check for duplicate
        if self.edges.contains(&edge) {
            return Ok(());
        }

        self.edges.push(edge);
        self.recompute_closure();
        self.recompute_components();
        Ok(())
    }

    /// Check if `from` can reach `to` following directed edges.
    fn can_reach(&self, from: &NodeId, to: &NodeId) -> bool {
        if let Some(reachable) = self.closure.get(from) {
            return reachable.contains(to);
        }
        // Fallback: BFS
        let mut visited = HashSet::new();
        let mut queue = VecDeque::new();
        queue.push_back(from.clone());
        while let Some(current) = queue.pop_front() {
            if &current == to {
                return true;
            }
            if !visited.insert(current.clone()) {
                continue;
            }
            for edge in &self.edges {
                if edge.from == current {
                    queue.push_back(edge.to.clone());
                }
            }
        }
        false
    }

    /// Recompute the full transitive closure using BFS from each node.
    fn recompute_closure(&mut self) {
        let adjacency = self.build_adjacency();
        self.closure.clear();

        for node_id in self.nodes.keys() {
            let mut reachable = BTreeSet::new();
            let mut queue = VecDeque::new();

            // Start from all direct successors
            if let Some(successors) = adjacency.get(node_id) {
                for succ in successors {
                    queue.push_back(succ.clone());
                }
            }

            while let Some(current) = queue.pop_front() {
                if !reachable.insert(current.clone()) {
                    continue;
                }
                if let Some(successors) = adjacency.get(&current) {
                    for succ in successors {
                        if !reachable.contains(succ) {
                            queue.push_back(succ.clone());
                        }
                    }
                }
            }

            self.closure.insert(node_id.clone(), reachable);
        }
    }

    /// Recompute connected components using union-find on undirected edges.
    fn recompute_components(&mut self) {
        let mut parent: HashMap<NodeId, NodeId> = HashMap::new();

        // Initialize each node as its own parent
        for id in self.nodes.keys() {
            parent.insert(id.clone(), id.clone());
        }

        fn find(parent: &HashMap<NodeId, NodeId>, x: &NodeId) -> NodeId {
            let mut current = x.clone();
            while parent[&current] != current {
                current = parent[&current].clone();
            }
            current
        }

        // Union all edge endpoints (undirected)
        for edge in &self.edges {
            let root_a = find(&parent, &edge.from);
            let root_b = find(&parent, &edge.to);
            if root_a != root_b {
                parent.insert(root_a, root_b);
            }
        }

        // Group by root
        let mut groups: BTreeMap<NodeId, Vec<NodeId>> = BTreeMap::new();
        for id in self.nodes.keys() {
            let root = find(&parent, id);
            groups.entry(root).or_default().push(id.clone());
        }

        // Assign component IDs
        self.components.clear();
        self.next_component_id = 0;
        for (_root, members) in groups {
            let comp_id = format!("component-{}", self.next_component_id);
            self.next_component_id += 1;
            self.components.insert(comp_id, members);
        }
    }

    /// Build adjacency list from edges.
    fn build_adjacency(&self) -> HashMap<NodeId, Vec<NodeId>> {
        let mut adj: HashMap<NodeId, Vec<NodeId>> = HashMap::new();
        for edge in &self.edges {
            adj.entry(edge.from.clone()).or_default().push(edge.to.clone());
        }
        adj
    }

    /// Query all relevant context for a given resource.
    /// Returns transitive dependencies, direct edges, and component membership.
    pub fn query_relevant(&self, resource_id: &NodeId) -> Result<QueryResult> {
        if !self.nodes.contains_key(resource_id) {
            return Err(RegistryError::NodeNotFound(resource_id.clone()));
        }

        let transitive_deps: Vec<NodeId> = self
            .closure
            .get(resource_id)
            .map(|s| s.iter().cloned().collect())
            .unwrap_or_default();

        let direct_edges: Vec<Edge> = self
            .edges
            .iter()
            .filter(|e| &e.from == resource_id)
            .cloned()
            .collect();

        // All edges within the transitive closure (including root)
        let relevant_nodes: HashSet<&NodeId> = {
            let mut s: HashSet<&NodeId> = transitive_deps.iter().collect();
            s.insert(resource_id);
            s
        };

        let all_edges: Vec<Edge> = self
            .edges
            .iter()
            .filter(|e| relevant_nodes.contains(&e.from) && relevant_nodes.contains(&e.to))
            .cloned()
            .collect();

        // Find component
        let component_id = self
            .components
            .iter()
            .find(|(_, members)| members.contains(resource_id))
            .map(|(id, _)| id.clone());

        Ok(QueryResult {
            root: resource_id.clone(),
            transitive_deps,
            direct_edges,
            all_edges,
            component_id,
        })
    }

    /// Get all nodes in the same connected component as the given node.
    pub fn component_members(&self, resource_id: &NodeId) -> Vec<NodeId> {
        for members in self.components.values() {
            if members.contains(resource_id) {
                return members.clone();
            }
        }
        vec![]
    }

    /// Return the number of nodes.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Return the number of edges.
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    /// Return the number of connected components.
    pub fn component_count(&self) -> usize {
        self.components.len()
    }

    /// Serialize the DAG to JSON.
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string_pretty(self).map_err(RegistryError::Serialization)
    }

    /// Deserialize a DAG from JSON.
    pub fn from_json(json: &str) -> Result<Self> {
        let mut dag: Self = serde_json::from_str(json).map_err(RegistryError::Serialization)?;
        dag.recompute_closure();
        dag.recompute_components();
        Ok(dag)
    }

    /// Load from a JSON file.
    pub fn load(path: &std::path::Path) -> Result<Self> {
        let content = std::fs::read_to_string(path).map_err(RegistryError::Io)?;
        Self::from_json(&content)
    }

    /// Save to a JSON file.
    pub fn save(&self, path: &std::path::Path) -> Result<()> {
        let json = self.to_json()?;
        std::fs::write(path, json).map_err(RegistryError::Io)
    }
}

impl Default for RegistryDag {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_node(id: &str) -> Node {
        Node::resource(NodeId::new(id), id, format!("Test node {}", id))
    }

    #[test]
    fn test_add_nodes_and_edges() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("db-0001")).unwrap();
        dag.add_node(make_node("db-0002")).unwrap();
        dag.add_edge(Edge::new("db-0001", "db-0002", EdgeType::Calls)).unwrap();

        assert_eq!(dag.node_count(), 2);
        assert_eq!(dag.edge_count(), 1);
    }

    #[test]
    fn test_closure_updates_on_edge_add() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();
        dag.add_node(make_node("b")).unwrap();
        dag.add_node(make_node("c")).unwrap();

        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();
        dag.add_edge(Edge::new("b", "c", EdgeType::Calls)).unwrap();

        // a should transitively reach c
        let closure_a = dag.closure.get(&NodeId::new("a")).unwrap();
        assert!(closure_a.contains(&NodeId::new("b")));
        assert!(closure_a.contains(&NodeId::new("c")));

        // b should reach c but not a
        let closure_b = dag.closure.get(&NodeId::new("b")).unwrap();
        assert!(closure_b.contains(&NodeId::new("c")));
        assert!(!closure_b.contains(&NodeId::new("a")));

        // c reaches nothing
        let closure_c = dag.closure.get(&NodeId::new("c")).unwrap();
        assert!(closure_c.is_empty());
    }

    #[test]
    fn test_cycle_rejection() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();
        dag.add_node(make_node("b")).unwrap();
        dag.add_node(make_node("c")).unwrap();

        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();
        dag.add_edge(Edge::new("b", "c", EdgeType::Calls)).unwrap();

        // c -> a would create a cycle
        let result = dag.add_edge(Edge::new("c", "a", EdgeType::Calls));
        assert!(result.is_err());
        match result.unwrap_err() {
            RegistryError::CycleDetected { from, to } => {
                assert_eq!(from, NodeId::new("c"));
                assert_eq!(to, NodeId::new("a"));
            }
            other => panic!("Expected CycleDetected, got {:?}", other),
        }
    }

    #[test]
    fn test_self_loop_rejection() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();

        let result = dag.add_edge(Edge::new("a", "a", EdgeType::Calls));
        assert!(result.is_err());
    }

    #[test]
    fn test_connected_components() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();
        dag.add_node(make_node("b")).unwrap();
        dag.add_node(make_node("c")).unwrap();
        dag.add_node(make_node("d")).unwrap();

        // a -> b and c -> d: two components
        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();
        dag.add_edge(Edge::new("c", "d", EdgeType::Calls)).unwrap();

        // Should have at least 2 components (isolated nodes don't count as separate here,
        // but since all 4 are connected in pairs, we have 2 multi-node components)
        let comp_with_a = dag.component_members(&NodeId::new("a"));
        let comp_with_c = dag.component_members(&NodeId::new("c"));

        assert!(comp_with_a.contains(&NodeId::new("a")));
        assert!(comp_with_a.contains(&NodeId::new("b")));
        assert!(!comp_with_a.contains(&NodeId::new("c")));

        assert!(comp_with_c.contains(&NodeId::new("c")));
        assert!(comp_with_c.contains(&NodeId::new("d")));
    }

    #[test]
    fn test_query_relevant() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("api-0001")).unwrap();
        dag.add_node(make_node("db-0001")).unwrap();
        dag.add_node(make_node("db-0002")).unwrap();
        dag.add_node(make_node("cfg-0001")).unwrap();

        dag.add_edge(Edge::new("api-0001", "db-0001", EdgeType::Handles)).unwrap();
        dag.add_edge(Edge::new("db-0001", "db-0002", EdgeType::Calls)).unwrap();
        dag.add_edge(Edge::new("db-0001", "cfg-0001", EdgeType::Imports)).unwrap();

        let result = dag.query_relevant(&NodeId::new("api-0001")).unwrap();
        assert_eq!(result.root, NodeId::new("api-0001"));
        assert_eq!(result.transitive_deps.len(), 3); // db-0001, db-0002, cfg-0001
        assert_eq!(result.direct_edges.len(), 1); // api -> db-0001
    }

    #[test]
    fn test_json_roundtrip() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();
        dag.add_node(make_node("b")).unwrap();
        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();

        let json = dag.to_json().unwrap();
        let restored = RegistryDag::from_json(&json).unwrap();

        assert_eq!(restored.node_count(), 2);
        assert_eq!(restored.edge_count(), 1);
        assert!(restored.closure.get(&NodeId::new("a")).unwrap().contains(&NodeId::new("b")));
    }

    #[test]
    fn test_component_merging() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();
        dag.add_node(make_node("b")).unwrap();
        dag.add_node(make_node("c")).unwrap();
        dag.add_node(make_node("d")).unwrap();

        // Two separate components
        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();
        dag.add_edge(Edge::new("c", "d", EdgeType::Calls)).unwrap();

        let comp_count_before = dag.component_count();

        // Bridge them: b -> c merges the components
        dag.add_edge(Edge::new("b", "c", EdgeType::Calls)).unwrap();

        // Now all should be in one component
        let comp_with_a = dag.component_members(&NodeId::new("a"));
        assert!(comp_with_a.contains(&NodeId::new("d")));
        assert!(dag.component_count() < comp_count_before);
    }

    #[test]
    fn test_duplicate_edge_idempotent() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();
        dag.add_node(make_node("b")).unwrap();
        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();
        dag.add_edge(Edge::new("a", "b", EdgeType::Calls)).unwrap();
        assert_eq!(dag.edge_count(), 1);
    }

    #[test]
    fn test_node_not_found() {
        let mut dag = RegistryDag::new();
        dag.add_node(make_node("a")).unwrap();

        let result = dag.add_edge(Edge::new("a", "nonexistent", EdgeType::Calls));
        assert!(matches!(result, Err(RegistryError::NodeNotFound(_))));
    }
}
