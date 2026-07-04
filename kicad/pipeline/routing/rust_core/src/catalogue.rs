use serde_json::{json, Value};
use std::collections::BTreeMap;

pub fn normalize_type_id(value: &str) -> String {
    let mut out = String::new();
    let mut last_was_sep = true;
    for ch in value.trim().chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch.to_ascii_uppercase());
            last_was_sep = false;
        } else if !last_was_sep {
            out.push('_');
            last_was_sep = true;
        }
    }
    while out.ends_with('_') {
        out.pop();
    }
    out
}

#[derive(Debug, Clone)]
pub struct ComponentCatalogue {
    pub raw: Value,
    pub grid: f64,
    components: BTreeMap<String, Value>,
    aliases: BTreeMap<String, String>,
}

impl ComponentCatalogue {
    pub fn from_value(raw: &Value) -> Result<Self, String> {
        let grid = raw.get("grid").and_then(Value::as_f64).unwrap_or(2.54);
        let raw_components = raw
            .get("components")
            .and_then(Value::as_object)
            .ok_or_else(|| "catalogue.components must be an object".to_string())?;
        let mut components = BTreeMap::new();
        let mut aliases = BTreeMap::new();
        for (type_id, component) in raw_components {
            components.insert(type_id.clone(), component.clone());
            aliases.insert(normalize_type_id(type_id), type_id.clone());
            if let Some(items) = component.get("aliases").and_then(Value::as_array) {
                for alias in items {
                    if let Some(alias_text) = alias.as_str() {
                        aliases.insert(normalize_type_id(alias_text), type_id.clone());
                    }
                }
            }
        }
        Ok(Self {
            raw: raw.clone(),
            grid,
            components,
            aliases,
        })
    }

    pub fn resolve_type_id(&self, value: &str) -> String {
        let normalized = normalize_type_id(value);
        if self.components.contains_key(&normalized) {
            return normalized;
        }
        self.aliases.get(&normalized).cloned().unwrap_or(normalized)
    }

    pub fn has_type(&self, type_id: &str) -> bool {
        self.components.contains_key(type_id)
    }

    pub fn get(&self, value: &str) -> Value {
        let type_id = self.resolve_type_id(value);
        self.components
            .get(&type_id)
            .cloned()
            .unwrap_or_else(|| generic_component(&type_id, 10.0, 8.0, "generic"))
    }
}

pub fn generic_component(type_id: &str, width: f64, height: f64, category: &str) -> Value {
    let half_w = (width.max(2.54) / 2.0 * 1000.0).round() / 1000.0;
    json!({
        "aliases": [type_id],
        "category": category,
        "body": {
            "width": width,
            "height": height,
            "origin": "center",
            "keepout": {"left": 2.54, "right": 2.54, "top": 2.54, "bottom": 2.54}
        },
        "legal_rotations": [0, 90, 180, 270],
        "default_rotation": 0,
        "pin_model": {
            "coordinate_system": "local_center_origin",
            "pins": {
                "1": {"number": "1", "local": [-half_w, 0.0], "side": "left", "type": "passive", "roles": ["generic"]},
                "2": {"number": "2", "local": [half_w, 0.0], "side": "right", "type": "passive", "roles": ["generic"]}
            }
        },
        "placement_hints": {"role": category, "can_be_pushed": true, "push_priority": 30, "default_spacing": 7.62}
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn resolves_aliases_like_python_catalogue() {
        let catalogue = ComponentCatalogue::from_value(&json!({
            "grid": 2.54,
            "components": {
                "Capacitor_Electrolytic": {"aliases": ["CAP-ELEC"], "body": {}, "pin_model": {"pins": {}}},
                "74HC595_DIP16": {"aliases": ["74HC595_SHIFT_REGISTER"], "body": {}, "pin_model": {"pins": {}}}
            }
        }))
        .unwrap();
        assert_eq!(
            catalogue.resolve_type_id("CAP-ELEC"),
            "Capacitor_Electrolytic"
        );
        assert_eq!(
            catalogue.resolve_type_id("74HC595_SHIFT_REGISTER"),
            "74HC595_DIP16"
        );
    }
}
