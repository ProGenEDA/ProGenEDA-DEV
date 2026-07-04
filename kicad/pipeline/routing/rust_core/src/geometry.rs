use crate::types::{BodyRect, Point};

pub fn snap(value: f64, grid: f64) -> f64 {
    ((value / grid).round() * grid * 1000.0).round() / 1000.0
}

#[allow(dead_code)]
pub fn manhattan(left: &Point, right: &Point) -> f64 {
    (left.x - right.x).abs() + (left.y - right.y).abs()
}

pub fn rotate_point(point: &Point, rotation: i32) -> Point {
    match rotation.rem_euclid(360) {
        0 => Point {
            x: point.x,
            y: point.y,
        },
        90 => Point {
            x: -point.y,
            y: point.x,
        },
        180 => Point {
            x: -point.x,
            y: -point.y,
        },
        270 => Point {
            x: point.y,
            y: -point.x,
        },
        _ => panic!("rotation must be 0/90/180/270"),
    }
}

pub fn rotate_side(side: &str, rotation: i32) -> &'static str {
    let index = match side {
        "left" => 0,
        "top" => 1,
        "right" => 2,
        "bottom" => 3,
        _ => 2,
    };
    match (index + rotation.rem_euclid(360) / 90) % 4 {
        0 => "left",
        1 => "top",
        2 => "right",
        _ => "bottom",
    }
}

pub fn body_rect(center: &Point, width: f64, height: f64, rotation: i32) -> BodyRect {
    let normalized = rotation.rem_euclid(360);
    let (body_width, body_height) = if normalized == 90 || normalized == 270 {
        (height, width)
    } else {
        (width, height)
    };
    BodyRect {
        left: round3(center.x - body_width / 2.0),
        top: round3(center.y - body_height / 2.0),
        right: round3(center.x + body_width / 2.0),
        bottom: round3(center.y + body_height / 2.0),
    }
}

pub fn inflate(rect: &BodyRect, left: f64, right: f64, top: f64, bottom: f64) -> BodyRect {
    BodyRect {
        left: round3(rect.left - left),
        top: round3(rect.top - top),
        right: round3(rect.right + right),
        bottom: round3(rect.bottom + bottom),
    }
}

pub fn rect_overlap(left: &BodyRect, right: &BodyRect) -> bool {
    left.left < right.right
        && left.right > right.left
        && left.top < right.bottom
        && left.bottom > right.top
}

pub fn round3(value: f64) -> f64 {
    (value * 1000.0).round() / 1000.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rotation_matches_python_live_state_contract() {
        let point = Point {
            x: -10.16,
            y: -2.54,
        };
        assert_eq!(rotate_point(&point, 90).x, 2.54);
        assert_eq!(rotate_point(&point, 90).y, -10.16);
        assert_eq!(rotate_point(&point, 180).x, 10.16);
        assert_eq!(rotate_point(&point, 180).y, 2.54);
        assert_eq!(rotate_side("left", 90), "top");
        assert_eq!(rotate_side("left", 180), "right");
        assert_eq!(rotate_side("left", 270), "bottom");
    }
}
