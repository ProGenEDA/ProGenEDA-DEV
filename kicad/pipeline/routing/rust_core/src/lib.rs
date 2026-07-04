use pyo3::prelude::*;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

mod catalogue;
mod connectivity;
mod geometry;
mod legalization;
mod occupancy;
mod parallel;
mod pin_resolver;
mod placement;
mod routing;
mod scoring;
mod types;
mod validation;

use catalogue::{generic_component, normalize_type_id, ComponentCatalogue};
use geometry::{body_rect, inflate, rotate_point, rotate_side, round3, snap};
use types::{LiveComponent, LiveNet, Point};
use validation::{component_overlaps, out_of_sheet};

fn parse_json(input_json: &str) -> PyResult<Value> {
    serde_json::from_str(input_json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))
}

fn value_object(value: Option<&Value>) -> BTreeMap<String, Value> {
    value
        .and_then(Value::as_object)
        .map(|object| {
            object
                .iter()
                .map(|(key, item)| (key.clone(), item.clone()))
                .collect()
        })
        .unwrap_or_default()
}

fn point_from_value(value: Option<&Value>, fallback: (f64, f64)) -> (f64, f64) {
    if let Some(items) = value.and_then(Value::as_array) {
        if items.len() >= 2 {
            return (
                items[0].as_f64().unwrap_or(fallback.0),
                items[1].as_f64().unwrap_or(fallback.1),
            );
        }
    }
    fallback
}

fn string_value(value: Option<&Value>, fallback: &str) -> String {
    value
        .and_then(Value::as_str)
        .unwrap_or(fallback)
        .to_string()
}

fn bool_value(value: Option<&Value>, fallback: bool) -> bool {
    value.and_then(Value::as_bool).unwrap_or(fallback)
}

fn f64_value(value: Option<&Value>, fallback: f64) -> f64 {
    value.and_then(Value::as_f64).unwrap_or(fallback)
}

fn i32_value(value: Option<&Value>, fallback: i32) -> i32 {
    value
        .and_then(Value::as_i64)
        .map(|item| item as i32)
        .or_else(|| value.and_then(Value::as_f64).map(|item| item as i32))
        .unwrap_or(fallback)
}

fn classify_net(net: &str) -> &'static str {
    let upper = net.to_ascii_uppercase();
    const POWER: &[&str] = &["+5V", "+3V3", "VCC", "VDD", "VIN", "REG_OUT"];
    const GROUND: &[&str] = &["GND", "GROUND", "0V"];
    const CLOCK: &[&str] = &["CLK", "CLOCK", "SHCP", "STCP", "RESET", "LATCH"];
    const BUS: &[&str] = &[
        "SPI", "I2C", "UART", "SEG", "DATA", "ADDRESS", "SHIFT", "CAN", "RS485", "MOSI", "MISO",
        "SCK",
    ];
    if POWER.contains(&upper.as_str()) {
        "power"
    } else if GROUND.contains(&upper.as_str()) {
        "ground"
    } else if CLOCK.iter().any(|token| upper.contains(token)) {
        "clock_control"
    } else if BUS.iter().any(|token| upper.contains(token)) {
        "bus"
    } else if upper.starts_with("SEG_")
        || ["A", "B", "C", "D", "E", "F", "G", "DP"].contains(&upper.as_str())
    {
        "display_segment"
    } else {
        "ordinary_signal"
    }
}

fn net_weight(net_class: &str) -> f64 {
    match net_class {
        "clock_control" => 10.0,
        "bus" => 6.0,
        "display_segment" => 5.0,
        "ordinary_signal" => 3.0,
        "power" | "ground" => 0.5,
        _ => 3.0,
    }
}

fn extract_nets(circuit: &Value) -> BTreeMap<String, Vec<(String, String)>> {
    let mut nets: BTreeMap<String, Vec<(String, String)>> = BTreeMap::new();
    if let Some(raw_nets) = circuit.get("nets").and_then(Value::as_object) {
        for (net_name, endpoints) in raw_nets {
            if let Some(endpoint_items) = endpoints.as_array() {
                for endpoint in endpoint_items {
                    if let Some(text) = endpoint.as_str() {
                        if let Some((reference, pin)) = text.split_once('.') {
                            nets.entry(net_name.clone())
                                .or_default()
                                .push((reference.to_string(), pin.to_string()));
                        }
                    } else if let Some(object) = endpoint.as_object() {
                        let reference = object
                            .get("ref")
                            .or_else(|| object.get("component"))
                            .and_then(Value::as_str);
                        let pin = object.get("pin").and_then(Value::as_str);
                        if let (Some(reference), Some(pin)) = (reference, pin) {
                            nets.entry(net_name.clone())
                                .or_default()
                                .push((reference.to_string(), pin.to_string()));
                        }
                    }
                }
            }
        }
    }
    if nets.is_empty() {
        if let Some(components) = circuit.get("components").and_then(Value::as_array) {
            for component in components {
                let reference = component
                    .get("id")
                    .or_else(|| component.get("ref"))
                    .and_then(Value::as_str)
                    .unwrap_or("");
                if reference.is_empty() {
                    continue;
                }
                if let Some(pins) = component.get("pins").and_then(Value::as_object) {
                    for (pin, net) in pins {
                        if let Some(net_name) = net.as_str() {
                            nets.entry(net_name.to_string())
                                .or_default()
                                .push((reference.to_string(), pin.clone()));
                        }
                    }
                }
            }
        }
    }
    nets
}

fn pin_lookup(pin_defs: &BTreeMap<String, Value>) -> BTreeMap<String, (String, Value)> {
    let mut lookup = BTreeMap::new();
    for (name, pin) in pin_defs {
        let number = pin.get("number").and_then(Value::as_str).unwrap_or("");
        for key in [
            name.as_str(),
            number,
            normalize_type_id(name).as_str(),
            normalize_type_id(number).as_str(),
        ] {
            if !key.is_empty() {
                lookup.insert(key.to_string(), (name.clone(), pin.clone()));
            }
        }
    }
    lookup
}

fn fallback_pin_def(
    pin_name: &str,
    index: usize,
    total: usize,
    width: f64,
    height: f64,
    net: &str,
) -> Value {
    let net_class = classify_net(net);
    if net_class == "power" {
        return json!({"number": pin_name, "local": [0.0, -height / 2.0], "side": "top", "type": "power", "roles": ["power"]});
    }
    if net_class == "ground" {
        return json!({"number": pin_name, "local": [0.0, height / 2.0], "side": "bottom", "type": "ground", "roles": ["ground"]});
    }
    let side = if index % 2 == 0 { "left" } else { "right" };
    let rows = ((total + 1) / 2).max(1);
    let row = index / 2;
    let y = if rows == 1 {
        0.0
    } else {
        -height * 0.35 + (height * 0.7 * row as f64 / (rows - 1) as f64)
    };
    let x = if side == "left" {
        -width / 2.0
    } else {
        width / 2.0
    };
    json!({"number": pin_name, "local": [round3(x), round3(y)], "side": side, "type": "passive", "roles": [net_class]})
}

fn component_priority(component: &Value, connected_weight: f64) -> f64 {
    let hints = component.get("placement_hints").unwrap_or(&Value::Null);
    let mut base = f64_value(hints.get("push_priority"), 30.0);
    let role = string_value(hints.get("role").or_else(|| component.get("category")), "");
    if ["controller", "middle_logic", "power_block"].contains(&role.as_str()) {
        base += 30.0;
    }
    if ["connector", "ground", "source"].contains(&role.as_str()) {
        base -= 10.0;
    }
    round3(base + connected_weight)
}

fn fallback_component_from_payload(type_id: &str, fallback: Option<&Value>) -> Option<Value> {
    let fallback = fallback?;
    let width = fallback.get("width")?.as_f64()?;
    let height = fallback.get("height")?.as_f64()?;
    let category = fallback
        .get("category")
        .and_then(Value::as_str)
        .unwrap_or("generic");
    let mut component = generic_component(type_id, width, height, category);
    if let Some(object) = component.as_object_mut() {
        object.insert("aliases".to_string(), json!([type_id]));
        if let Some(hints) = object
            .get_mut("placement_hints")
            .and_then(Value::as_object_mut)
        {
            hints.insert("role".to_string(), Value::String(category.to_string()));
            let priority = if category.contains("connector") || category.contains("power_symbol") {
                20
            } else {
                35
            };
            hints.insert("push_priority".to_string(), json!(priority));
        }
    }
    Some(component)
}

fn recompute_pins(component: &mut LiveComponent) {
    let at = Point {
        x: component.at[0],
        y: component.at[1],
    };
    let mut pins = BTreeMap::new();
    for (pin_name, pin) in component.pin_defs.iter() {
        let (local_x, local_y) = point_from_value(pin.get("local"), (0.0, 0.0));
        let rotated = rotate_point(
            &Point {
                x: local_x,
                y: local_y,
            },
            component.rotation,
        );
        let point = vec![round3(at.x + rotated.x), round3(at.y + rotated.y)];
        let side = rotate_side(
            pin.get("side").and_then(Value::as_str).unwrap_or("right"),
            component.rotation,
        );
        pins.insert(
            pin_name.clone(),
            json!({
                "number": pin.get("number").and_then(Value::as_str).unwrap_or(pin_name),
                "point": point,
                "side": side,
                "type": pin.get("type").and_then(Value::as_str).unwrap_or("passive"),
                "roles": pin.get("roles").and_then(Value::as_array).cloned().unwrap_or_default(),
                "source": pin.get("source").and_then(Value::as_str).unwrap_or("component_catalogue")
            }),
        );
    }
    component.pins = pins;
}

fn build_state(payload: &Value) -> Result<Value, String> {
    let catalogue_value = payload
        .get("catalogue")
        .ok_or_else(|| "payload.catalogue is required".to_string())?;
    let catalogue = ComponentCatalogue::from_value(catalogue_value)?;
    let placement = payload.get("placement").unwrap_or(&Value::Null);
    let circuit = payload.get("circuit").unwrap_or(&Value::Null);
    let config = payload.get("config").unwrap_or(&Value::Null);
    let placement_fallbacks = payload
        .get("placement_fallbacks")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let sheet = config
        .get("sheet")
        .cloned()
        .unwrap_or_else(|| json!({"width": 420.0, "height": 297.0, "margin": 15.24}));
    let raw_nets = extract_nets(circuit);

    let mut components_by_ref: BTreeMap<String, Value> = BTreeMap::new();
    if let Some(components) = circuit.get("components").and_then(Value::as_array) {
        for component in components {
            if let Some(reference) = component
                .get("id")
                .or_else(|| component.get("ref"))
                .and_then(Value::as_str)
            {
                components_by_ref.insert(reference.to_string(), component.clone());
            }
        }
    }
    let placement_components = value_object(placement.get("components"));
    let mut refs: BTreeSet<String> = components_by_ref.keys().cloned().collect();
    refs.extend(placement_components.keys().cloned());

    let mut connected_weight_by_ref: BTreeMap<String, f64> = refs
        .iter()
        .map(|reference| (reference.clone(), 0.0))
        .collect();
    for (net_name, endpoints) in raw_nets.iter() {
        let weight = net_weight(classify_net(net_name));
        for (reference, _) in endpoints {
            *connected_weight_by_ref
                .entry(reference.clone())
                .or_insert(0.0) += weight;
        }
    }

    let mut components: BTreeMap<String, LiveComponent> = BTreeMap::new();
    for reference in refs {
        let raw_component = components_by_ref
            .get(&reference)
            .cloned()
            .unwrap_or(Value::Null);
        let placed = placement_components
            .get(&reference)
            .cloned()
            .unwrap_or(Value::Null);
        let kind = string_value(
            raw_component
                .get("kind")
                .or_else(|| placed.get("kind"))
                .or_else(|| raw_component.get("name"))
                .or_else(|| placed.get("name")),
            "GENERIC_COMPONENT",
        );
        let type_id = catalogue.resolve_type_id(&kind);
        let normalized_kind = normalize_type_id(&kind);
        let type_def = if catalogue.has_type(&type_id) {
            catalogue.get(&kind)
        } else {
            fallback_component_from_payload(
                &type_id,
                placement_fallbacks
                    .get(&normalized_kind)
                    .or_else(|| placement_fallbacks.get(&type_id)),
            )
            .unwrap_or_else(|| catalogue.get(&kind))
        };
        let body = type_def.get("body").cloned().unwrap_or_else(|| json!({"width": 10.0, "height": 8.0, "keepout": {"left": 2.54, "right": 2.54, "top": 2.54, "bottom": 2.54}}));
        let width = f64_value(body.get("width"), 10.0);
        let height = f64_value(body.get("height"), 8.0);
        let at_raw = point_from_value(placed.get("at"), (0.0, 0.0));
        let mut rotation = i32_value(
            placed
                .get("rotation")
                .or_else(|| raw_component.get("rotation"))
                .or_else(|| type_def.get("default_rotation")),
            0,
        )
        .rem_euclid(360);
        let legal_rotations: Vec<i32> = type_def
            .get("legal_rotations")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(|item| item.as_i64().map(|value| value as i32))
                    .collect()
            })
            .unwrap_or_else(|| vec![0, 90, 180, 270]);
        if !legal_rotations.contains(&rotation) {
            rotation = i32_value(type_def.get("default_rotation"), 0).rem_euclid(360);
        }
        let mut pin_defs =
            value_object(type_def.get("pin_model").and_then(|item| item.get("pins")));
        if let Some(raw_pins) = raw_component.get("pins").and_then(Value::as_object) {
            let lookup = pin_lookup(&pin_defs);
            let total = raw_pins.len().max(1);
            for (index, (pin_name, net_value)) in raw_pins.iter().enumerate() {
                let normalized = normalize_type_id(pin_name);
                if pin_defs.contains_key(pin_name) || pin_defs.contains_key(&normalized) {
                    continue;
                }
                if let Some((matched_name, matched_pin)) =
                    lookup.get(pin_name).or_else(|| lookup.get(&normalized))
                {
                    let mut alias_pin = matched_pin.clone();
                    if let Some(object) = alias_pin.as_object_mut() {
                        object.insert(
                            "source".to_string(),
                            Value::String(format!("alias:{matched_name}")),
                        );
                    }
                    pin_defs.insert(pin_name.clone(), alias_pin);
                } else {
                    let mut fallback = fallback_pin_def(
                        pin_name,
                        index,
                        total,
                        width,
                        height,
                        net_value.as_str().unwrap_or(""),
                    );
                    if let Some(object) = fallback.as_object_mut() {
                        object.insert(
                            "source".to_string(),
                            Value::String("circuit_pin_fallback".to_string()),
                        );
                    }
                    pin_defs.insert(pin_name.clone(), fallback);
                }
            }
        }
        let at = vec![
            snap(at_raw.0, catalogue.grid),
            snap(at_raw.1, catalogue.grid),
        ];
        let center = Point { x: at[0], y: at[1] };
        let body_rect = body_rect(&center, width, height, rotation);
        let keepout = body.get("keepout").unwrap_or(&Value::Null);
        let keepout_rect = inflate(
            &body_rect,
            f64_value(keepout.get("left"), 0.0),
            f64_value(keepout.get("right"), 0.0),
            f64_value(keepout.get("top"), 0.0),
            f64_value(keepout.get("bottom"), 0.0),
        );
        let mut component = LiveComponent {
            type_id,
            kind: kind.clone(),
            name: string_value(
                placed.get("name").or_else(|| raw_component.get("name")),
                &kind,
            ),
            category: string_value(type_def.get("category"), "generic"),
            at,
            rotation,
            locked: bool_value(raw_component.get("locked"), false)
                || bool_value(placed.get("manual"), false),
            legal_rotations,
            catalogue_body: body.clone(),
            pin_defs,
            routing_hints: type_def
                .get("routing_hints")
                .cloned()
                .unwrap_or(Value::Null),
            placement_hints: type_def
                .get("placement_hints")
                .cloned()
                .unwrap_or(Value::Null),
            priority: component_priority(
                &type_def,
                *connected_weight_by_ref.get(&reference).unwrap_or(&0.0),
            ),
            body: body_rect,
            keepout: keepout_rect,
            pins: BTreeMap::new(),
        };
        recompute_pins(&mut component);
        components.insert(reference, component);
    }

    let mut nets: BTreeMap<String, LiveNet> = BTreeMap::new();
    for (net_name, refs) in raw_nets {
        let net_class = classify_net(&net_name).to_string();
        let endpoint_refs: Vec<Value> = refs
            .iter()
            .map(|(reference, pin)| json!({"ref": reference, "pin": pin}))
            .collect();
        let mut endpoints = Vec::new();
        for (reference, pin) in refs.iter() {
            if let Some(component) = components.get(reference) {
                let pin_data = component
                    .pins
                    .get(pin)
                    .or_else(|| component.pins.get(&normalize_type_id(pin)));
                if let Some(pin_data) = pin_data {
                    endpoints.push(json!({
                        "ref": reference,
                        "pin": pin,
                        "point": pin_data.get("point").cloned().unwrap_or(Value::Null),
                        "side": pin_data.get("side").cloned().unwrap_or(Value::Null),
                        "type": pin_data.get("type").cloned().unwrap_or(Value::Null),
                        "roles": pin_data.get("roles").cloned().unwrap_or(Value::Array(vec![]))
                    }));
                }
            }
        }
        let weight = net_weight(&net_class);
        nets.insert(
            net_name,
            LiveNet {
                class: net_class,
                weight,
                endpoint_refs,
                fanout: endpoints.len(),
                endpoints,
                criticality: weight as i32,
            },
        );
    }
    let metrics = score_fast(&components, &nets, &sheet);
    Ok(json!({
        "schema": "progen-live-routing-state/v0.2",
        "engine": "rust_core_v0.1_temp_geometry",
        "implemented": true,
        "unit": "mm",
        "grid": catalogue.grid,
        "sheet": sheet,
        "components": components,
        "nets": nets,
        "routes": {},
        "metrics": metrics,
        "source_placement": placement,
        "catalogue_schema": catalogue.raw.get("schema").cloned().unwrap_or(Value::Null)
    }))
}

fn score_fast(
    components: &BTreeMap<String, LiveComponent>,
    nets: &BTreeMap<String, LiveNet>,
    sheet: &Value,
) -> Value {
    let mut hpwl = 0.0;
    let mut weighted_hpwl = 0.0;
    for net in nets.values() {
        let points: Vec<(f64, f64)> = net
            .endpoints
            .iter()
            .filter_map(|endpoint| {
                let point = endpoint.get("point")?.as_array()?;
                if point.len() < 2 {
                    return None;
                }
                Some((
                    point[0].as_f64().unwrap_or(0.0),
                    point[1].as_f64().unwrap_or(0.0),
                ))
            })
            .collect();
        if points.len() < 2 {
            continue;
        }
        let min_x = points
            .iter()
            .map(|point| point.0)
            .fold(f64::INFINITY, f64::min);
        let max_x = points
            .iter()
            .map(|point| point.0)
            .fold(f64::NEG_INFINITY, f64::max);
        let min_y = points
            .iter()
            .map(|point| point.1)
            .fold(f64::INFINITY, f64::min);
        let max_y = points
            .iter()
            .map(|point| point.1)
            .fold(f64::NEG_INFINITY, f64::max);
        let raw = (max_x - min_x) + (max_y - min_y);
        hpwl += raw;
        weighted_hpwl += raw * net.weight;
    }
    let overlap_count = component_overlaps(components).len();
    let out_of_sheet_count = out_of_sheet(components, sheet).len();
    let score = weighted_hpwl
        + overlap_count as f64 * 1_000_000.0
        + out_of_sheet_count as f64 * 1_000_000.0;
    json!({
        "hpwl": round3(hpwl),
        "weighted_hpwl": round3(weighted_hpwl),
        "component_overlap_count": overlap_count,
        "out_of_sheet_count": out_of_sheet_count,
        "score": round3(score)
    })
}

fn temp_not_full(function_name: &str, input_json: &str) -> PyResult<String> {
    let parsed = parse_json(input_json)?;
    Ok(json!({
        "schema": "progen-routing-core-result/v0.1",
        "engine": "rust_core_v0.1_temp_geometry",
        "function": function_name,
        "implemented": false,
        "input_keys": parsed.as_object().map(|item| item.keys().cloned().collect::<Vec<_>>()).unwrap_or_default(),
        "warnings": [
            "Rust temp core has geometry/pin-state functions only; Python LiveRoutingState remains authoritative for full routing until comparison tests prove parity."
        ]
    })
    .to_string())
}

#[pyfunction]
fn build_live_state(input_json: &str) -> PyResult<String> {
    let payload = parse_json(input_json)?;
    let state = build_state(&payload).map_err(pyo3::exceptions::PyValueError::new_err)?;
    Ok(state.to_string())
}

#[pyfunction]
fn resolve_pins(input_json: &str) -> PyResult<String> {
    let payload = parse_json(input_json)?;
    let state = build_state(&payload).map_err(pyo3::exceptions::PyValueError::new_err)?;
    let components = state.get("components").cloned().unwrap_or(Value::Null);
    Ok(json!({
        "schema": "progen-routing-pin-resolution/v0.1",
        "engine": "rust_core_v0.1_temp_geometry",
        "implemented": true,
        "components": components
    })
    .to_string())
}

#[pyfunction]
fn score_rotations(input_json: &str) -> PyResult<String> {
    temp_not_full("score_rotations", input_json)
}

#[pyfunction]
fn legalize_candidate(input_json: &str) -> PyResult<String> {
    temp_not_full("legalize_candidate", input_json)
}

#[pyfunction]
fn score_placement_variants(input_json: &str) -> PyResult<String> {
    temp_not_full("score_placement_variants", input_json)
}

#[pyfunction]
fn route_variants(input_json: &str) -> PyResult<String> {
    temp_not_full("route_variants", input_json)
}

#[pyfunction]
fn validate_geometry(input_json: &str) -> PyResult<String> {
    let payload = parse_json(input_json)?;
    let state = build_state(&payload).map_err(pyo3::exceptions::PyValueError::new_err)?;
    let components: BTreeMap<String, LiveComponent> =
        serde_json::from_value(state.get("components").cloned().unwrap_or(Value::Null))
            .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;
    let sheet = state
        .get("sheet")
        .cloned()
        .unwrap_or_else(|| json!({"width": 420.0, "height": 297.0, "margin": 15.24}));
    let overlaps = component_overlaps(&components);
    let out_of_sheet_refs = out_of_sheet(&components, &sheet);
    Ok(json!({
        "schema": "progen-routing-geometry-validation/v0.1",
        "engine": "rust_core_v0.1_temp_geometry",
        "implemented": true,
        "ok": overlaps.is_empty() && out_of_sheet_refs.is_empty(),
        "component_overlaps": overlaps,
        "out_of_sheet_refs": out_of_sheet_refs,
        "metrics": {
            "component_overlap_count": overlaps.len(),
            "out_of_sheet_count": out_of_sheet_refs.len()
        }
    })
    .to_string())
}

#[pyfunction]
fn plan_full(input_json: &str) -> PyResult<String> {
    temp_not_full("plan_full", input_json)
}

#[pymodule]
fn progen_routing_core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(build_live_state, module)?)?;
    module.add_function(wrap_pyfunction!(resolve_pins, module)?)?;
    module.add_function(wrap_pyfunction!(score_rotations, module)?)?;
    module.add_function(wrap_pyfunction!(legalize_candidate, module)?)?;
    module.add_function(wrap_pyfunction!(score_placement_variants, module)?)?;
    module.add_function(wrap_pyfunction!(route_variants, module)?)?;
    module.add_function(wrap_pyfunction!(validate_geometry, module)?)?;
    module.add_function(wrap_pyfunction!(plan_full, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn catalogue() -> Value {
        serde_json::from_str(include_str!("../../../catelogues/component_catalogue.json")).unwrap()
    }

    #[test]
    fn build_live_state_resolves_rotated_74hc595_pin_like_python() {
        let payload = json!({
            "catalogue": catalogue(),
            "placement": {"components": {"U1": {"kind": "74HC595_SHIFT_REGISTER", "at": [100.0, 100.0], "rotation": 90}}, "obstacles": []},
            "circuit": {
                "components": [{"id": "U1", "kind": "74HC595_SHIFT_REGISTER", "pins": {"SER": "DATA"}}],
                "nets": {"DATA": ["U1.SER"]}
            },
            "config": {}
        });
        let state = build_state(&payload).unwrap();
        let pin = &state["components"]["U1"]["pins"]["SER"];
        assert_eq!(pin["side"], "top");
        assert_eq!(pin["point"], json!([101.6, 88.9]));
        let body = &state["components"]["U1"]["body"];
        assert_eq!(
            round3(body["right"].as_f64().unwrap() - body["left"].as_f64().unwrap()),
            7.62
        );
    }

    #[test]
    fn validate_geometry_reports_component_overlap() {
        let payload = json!({
            "catalogue": catalogue(),
            "placement": {
                "components": {
                    "R1": {"kind": "RES", "at": [50.0, 50.0]},
                    "R2": {"kind": "RES", "at": [50.0, 50.0]}
                }
            },
            "circuit": {
                "components": [
                    {"id": "R1", "kind": "RES", "pins": {"1": "A", "2": "B"}},
                    {"id": "R2", "kind": "RES", "pins": {"1": "C", "2": "D"}}
                ],
                "nets": {"A": ["R1.1"], "B": ["R1.2"], "C": ["R2.1"], "D": ["R2.2"]}
            },
            "config": {}
        });
        let state = build_state(&payload).unwrap();
        let components: BTreeMap<String, LiveComponent> =
            serde_json::from_value(state["components"].clone()).unwrap();
        assert_eq!(component_overlaps(&components).len(), 1);
    }
}
