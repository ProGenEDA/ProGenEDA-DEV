use crate::geometry::rect_overlap;
use crate::types::LiveComponent;
use serde_json::json;
use std::collections::BTreeMap;

pub fn component_overlaps(components: &BTreeMap<String, LiveComponent>) -> Vec<serde_json::Value> {
    let refs: Vec<&String> = components.keys().collect();
    let mut out = Vec::new();
    for (left_index, left_ref) in refs.iter().enumerate() {
        for right_ref in refs.iter().skip(left_index + 1) {
            let left = &components[*left_ref].keepout;
            let right = &components[*right_ref].keepout;
            if rect_overlap(left, right) {
                out.push(json!({"left": left_ref, "right": right_ref}));
            }
        }
    }
    out
}

pub fn out_of_sheet(
    components: &BTreeMap<String, LiveComponent>,
    sheet: &serde_json::Value,
) -> Vec<String> {
    let width = sheet
        .get("width")
        .and_then(serde_json::Value::as_f64)
        .unwrap_or(420.0);
    let height = sheet
        .get("height")
        .and_then(serde_json::Value::as_f64)
        .unwrap_or(297.0);
    let margin = sheet
        .get("margin")
        .and_then(serde_json::Value::as_f64)
        .unwrap_or(15.24);
    components
        .iter()
        .filter_map(|(reference, component)| {
            let keepout = &component.keepout;
            if keepout.left < margin
                || keepout.top < margin
                || keepout.right > width - margin
                || keepout.bottom > height - margin
            {
                Some(reference.clone())
            } else {
                None
            }
        })
        .collect()
}
