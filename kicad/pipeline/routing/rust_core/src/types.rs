use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BodyRect {
    pub left: f64,
    pub top: f64,
    pub right: f64,
    pub bottom: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct RouteSegment {
    pub net: String,
    pub start: Point,
    pub end: Point,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LiveComponent {
    pub type_id: String,
    pub kind: String,
    pub name: String,
    pub category: String,
    pub at: Vec<f64>,
    pub rotation: i32,
    pub locked: bool,
    pub legal_rotations: Vec<i32>,
    pub catalogue_body: Value,
    pub pin_defs: BTreeMap<String, Value>,
    pub routing_hints: Value,
    pub placement_hints: Value,
    pub priority: f64,
    pub body: BodyRect,
    pub keepout: BodyRect,
    pub pins: BTreeMap<String, Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LiveNet {
    pub class: String,
    pub weight: f64,
    pub endpoint_refs: Vec<Value>,
    pub endpoints: Vec<Value>,
    pub fanout: usize,
    pub criticality: i32,
}
