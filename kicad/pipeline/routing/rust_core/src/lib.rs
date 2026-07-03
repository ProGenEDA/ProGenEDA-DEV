use pyo3::prelude::*;
use serde_json::json;

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

fn not_implemented(function_name: &str, input_json: &str) -> PyResult<String> {
    let parsed: serde_json::Value = serde_json::from_str(input_json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;
    Ok(json!({
        "schema": "progen-routing-core-result/v0.1",
        "engine": "rust_core_v0.1_skeleton",
        "function": function_name,
        "implemented": false,
        "input_keys": parsed.as_object().map(|item| item.keys().cloned().collect::<Vec<_>>()).unwrap_or_default(),
        "warnings": ["Rust core skeleton is present; Python LiveRoutingState fallback is authoritative until this module is implemented."]
    })
    .to_string())
}

#[pyfunction]
fn build_live_state(input_json: &str) -> PyResult<String> {
    not_implemented("build_live_state", input_json)
}

#[pyfunction]
fn resolve_pins(input_json: &str) -> PyResult<String> {
    not_implemented("resolve_pins", input_json)
}

#[pyfunction]
fn score_rotations(input_json: &str) -> PyResult<String> {
    not_implemented("score_rotations", input_json)
}

#[pyfunction]
fn legalize_candidate(input_json: &str) -> PyResult<String> {
    not_implemented("legalize_candidate", input_json)
}

#[pyfunction]
fn score_placement_variants(input_json: &str) -> PyResult<String> {
    not_implemented("score_placement_variants", input_json)
}

#[pyfunction]
fn route_variants(input_json: &str) -> PyResult<String> {
    not_implemented("route_variants", input_json)
}

#[pyfunction]
fn validate_geometry(input_json: &str) -> PyResult<String> {
    not_implemented("validate_geometry", input_json)
}

#[pyfunction]
fn plan_full(input_json: &str) -> PyResult<String> {
    not_implemented("plan_full", input_json)
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
