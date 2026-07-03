use crate::types::Point;

pub fn manhattan(left: &Point, right: &Point) -> f64 {
    (left.x - right.x).abs() + (left.y - right.y).abs()
}

pub fn rotate_point(point: &Point, rotation: i32) -> Point {
    match rotation.rem_euclid(360) {
        0 => Point { x: point.x, y: point.y },
        90 => Point { x: -point.y, y: point.x },
        180 => Point { x: -point.x, y: -point.y },
        270 => Point { x: point.y, y: -point.x },
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
