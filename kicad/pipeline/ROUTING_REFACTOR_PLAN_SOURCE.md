# ProGenEDA KiCad Routing Engine Refactor Plan - Extracted Source


- Source PDF: `/home/zaruka/Downloads/ProGenEDA_KiCad_Routing_Refactor_Plan.pdf`
- Extracted with: `pypdf 6.14.2`
- Pages: 21

This file preserves the extracted plan text used as the implementation source for the KiCad routing refactor.

## Page 1

ProGenEDA KiCad Routing Engine Refactor Plan
Page 1
 ProGenEDA KiCad Routing Engine Refactor
 Plan
 Full architecture plan combining the original refactor + revised catalogue, legalization, mathematical,
 rotation, crossing, and Rust-parallel improvements
Core goal: stop mutating coordinates through beautifier during optimization. Build a mathematical
LiveRoutingState, move and rotate components in memory, recompute pins/bodies/keepouts/routes, score
variants in parallel, and export only the final winning state to KiCad.
Prepared for direct handoff to Codex / coding-agent implementation. This document intentionally avoids pasting proprietary source
code and only describes the engineering plan.

## Page 2

ProGenEDA KiCad Routing Engine Refactor Plan
Page 2
0. Table of Contents
- 1. Current code diagnosis

- 2. New target architecture

- 3. Correct folder structure

- 4. Permanent component catalogue

- 5. KiCad mapping catalogues

- 6. Temporary catalogue / LiveRoutingState

- 7. Mathematical foundations and deterministic pruning laws

- 8. Pin resolver and rotation math

- 9. Connectivity graph, pivot, and component priority

- 10. Cluster-growth placement flow

- 11. Rotation-aware location scoring

- 12. Priority-aware legalization

- 13. Routing engine and crossing policy

- 14. Optional KiCad netclass colors

- 15. Rust/Python split

- 16. Rust module design

- 17. Python orchestration design

- 18. Rust API exposed to Python

- 19. Parallel multi-instance compute model

- 20. Output contracts

- 21. Validation/reporting

- 22. Migration plan

- 23. Acceptance tests and benchmarks

- 24. Codex implementation prompt

- 25. Final checklist

## Page 3

ProGenEDA KiCad Routing Engine Refactor Plan
Page 3
1. Current code diagnosis
The current planner is already valuable. It is not throwaway code. It already separates routing from the target EDA file
format and uses JSON contracts. The uploaded wire planner consumes placement JSON and CircuitIR-style JSON,
builds endpoint points, tries lane candidates and A* routes, scores route quality, selects routeable arrangements, and
writes JSON plans. The uploaded geometry validator separately checks orthogonality and component-body touch
violations.
- Good: EDA-agnostic wire-plan design; the router emits JSON instead of directly mutating KiCad files.

- Good: existing use of lane candidates plus A* fallback is the right routing skeleton.

- Good: separate geometry validator is exactly the kind of pure deterministic module that should move to Rust first.

- Weakness: component state is not centralized enough. Pins are sometimes exact, sometimes estimated from body
 sides, and coordinate edits are repeatedly applied through the beautifier.
- Weakness: rotations are not first-class. Without exact local pin geometry and rotation transforms, the planner cannot
 know whether a component is truly well oriented for routing.
- Weakness: placement improvement currently looks too much like edit -> re-read -> estimate -> route. The new system
 must become state -> transform -> recompute -> score -> choose.
Refactor target: keep the current output contracts, but replace the internal engine with a catalogue-backed
LiveRoutingState and Rust geometry/routing core.
2. New target architecture
Python layer
  - JSON orchestration
  - component catalogue loading
  - KiCad symbol/footprint adapter maps
  - KiCad/Proteus exporter calls
  - benchmark runner
  - validation report writer
  - AI/model routing integration
Rust core
  - pin coordinate transformation
  - rotation-side transformation
  - body/keepout recomputation
  - HPWL and routeability scoring
  - component connectivity graph
  - pivot and priority calculations
  - placement candidate generation
  - priority-aware legalization
  - occupancy grid
  - Hanan-grid lane generation
  - A* routing
  - crossing counting
  - geometry validation
  - parallel variant evaluation
The Rust core must remain EDA-agnostic. It should never write .kicad_sch or .kicad_pcb. It receives
catalogue/state/circuit JSON and returns coordinate plans, routing placements, wire plans, metrics, and warnings.
3. Correct folder structure
kicad/
  pipeline/
    catelogues/
      __init__.py
      component_catalogue.schema.json
      component_catalogue.json
      component_catalogue_loader.py
      kicad_symbol_map.json
      kicad_footprint_map.json
    routing/
      __init__.py

## Page 4

ProGenEDA KiCad Routing Engine Refactor Plan
Page 4
      python/
        routing_orchestrator.py
        live_routing_state.py
        routing_config.py
        validation_report.py
        old_wire_planner_adapter.py
      rust_core/
        Cargo.toml
        pyproject.toml
        src/
          lib.rs
          types.rs
          geometry.rs
          catalogue.rs
          pin_resolver.rs
          connectivity.rs
          placement.rs
          legalization.rs
          occupancy.rs
          routing.rs
          scoring.rs
          validation.rs
          parallel.rs
Reason for moving catalogues outside routing: the same component geometry, pin roles, symbol mapping,
footprint mapping, and validation metadata will be used by schematic generation, routing, PCB generation,
KiCad validation, Proteus adapters, and future exporters.
4. Permanent component catalogue
The permanent catalogue is the source of truth for component routing geometry. It is mostly EDA-agnostic. It should
describe the abstract physical/routing behavior of each component, not raw KiCad syntax.
Path:
  kicad/pipeline/catelogues/component_catalogue.json
Purpose:
  - define abstract component type ids
  - define body geometry
  - define local pin coordinates
  - define legal rotations
  - define pin type, role, side, and bus groups
  - define movement/push priority
  - define routing hints
4.1 Example catalogue entry
{
  "schema": "progen-component-catalogue/v0.2",
  "unit": "mm",
  "grid": 2.54,
  "components": {
    "74HC595_DIP16": {
      "category": "logic_ic",
      "body": {
        "width": 20.32,
        "height": 7.62,
        "origin": "center",
        "keepout": {
          "left": 2.54,
          "right": 2.54,
          "top": 2.54,
          "bottom": 2.54
        }
      },
      "legal_rotations": [0, 90, 180, 270],
      "default_rotation": 0,
      "pin_model": {
        "coordinate_system": "local_center_origin",
        "pins": {
          "SER": {
            "number": "14",
            "local": [-10.16, -2.54],
            "side": "left",
            "type": "input",
            "roles": ["serial_data_in"]

## Page 5

ProGenEDA KiCad Routing Engine Refactor Plan
Page 5
          },
          "SHCP": {
            "number": "11",
            "local": [-10.16, 0.0],
            "side": "left",
            "type": "input",
            "roles": ["clock", "shift_clock"]
          },
          "STCP": {
            "number": "12",
            "local": [-10.16, 2.54],
            "side": "left",
            "type": "input",
            "roles": ["latch"]
          },
          "Q0": {
            "number": "15",
            "local": [10.16, -3.81],
            "side": "right",
            "type": "output",
            "roles": ["parallel_output", "bus_output"]
          }
        }
      },
      "routing_hints": {
        "input_side_preference": "left",
        "output_side_preference": "right",
        "power_side_preference": "top",
        "ground_side_preference": "bottom",
        "bus_groups": [
          {
            "name": "parallel_outputs",
            "pins": ["Q0", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"],
            "preferred_order": "preserve",
            "preferred_alignment": "vertical"
          }
        ],
        "critical_pins": ["SER", "SHCP", "STCP", "MR", "OE"],
        "power_pins": ["VCC"],
        "ground_pins": ["GND"]
      },
      "placement_hints": {
        "role": "middle_logic",
        "can_be_pushed": true,
        "push_priority": 50,
        "default_spacing": 7.62
      }
    }
  }
}
4.2 What counts as all information
- Abstract component type id, e.g. 74HC595_DIP16, ArduinoNano_Module, SevenSeg_CommonCathode,
 Resistor_Axial.
- Body width and height in mm, with origin convention. Use center origin for simple transforms.

- Keepout margin around the body. This is not the pin; it is routing/readability clearance.

- Legal rotations: usually 0/90/180/270, but some components may be locked to 0/180 for readability.

- Local pin coordinates relative to component center at rotation 0.

- Pin side at rotation 0: left/right/top/bottom.

- Pin electrical type: input, output, bidirectional, passive, power, ground, no_connect.

- Pin roles: clock, reset, latch, data, bus_output, segment, power, ground, enable, etc.

- Bus groups and ordering rules: preserve order, reverse allowed, or arbitrary.

- Preferred sides: inputs left, outputs right, power top, ground bottom, displays on output side, connectors near sheet
 edge.
- Placement priority and push priority. Some components are easier to move than others.

- Locked/movable/fixed behavior. User-placed components or major pivots may become locked.

## Page 6

ProGenEDA KiCad Routing Engine Refactor Plan
Page 6
- Readability role: source, controller, middle_logic, display_output, connector, power_block, testpoint.

- Optional symmetry or mirror rules for symbols that can be visually mirrored without hurting understanding.

5. KiCad mapping catalogues
Keep KiCad-specific details separate from the abstract component catalogue. This keeps routing reusable and prevents
KiCad file syntax from leaking into the engine.
kicad_symbol_map.json
{
  "74HC595_DIP16": {
    "symbol": "74xx:74HC595"
  },
  "Resistor_Axial": {
    "symbol": "Device:R"
  }
}
kicad_footprint_map.json
{
  "74HC595_DIP16": {
    "footprint": "Package_DIP:DIP-16_W7.62mm"
  },
  "Resistor_Axial": {
    "footprint": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
  }
}
Rule: routing core consumes abstract component ids and geometry. KiCad exporter consumes abstract ids plus
KiCad symbol/footprint maps.
6. Temporary catalogue / LiveRoutingState
Your 'temporary cataloguer' should be implemented as LiveRoutingState. It stores the current mathematical state of the
design after placement, rotation, pin resolution, legalization, and routing attempts. It is the engine's scratchpad. It is not
KiCad.
{
  "schema": "progen-live-routing-state/v0.2",
  "unit": "mm",
  "grid": 2.54,
  "components": {
    "U2": {
      "type_id": "74HC595_DIP16",
      "at": [120.0, 80.0],
      "rotation": 90,
      "locked": false,
      "priority": 80,
      "body": {
        "left": 116.19,
        "top": 69.84,
        "right": 123.81,
        "bottom": 90.16
      },
      "keepout": {
        "left": 113.65,
        "top": 67.30,
        "right": 126.35,
        "bottom": 92.70
      },
      "pins": {
        "SER": {
          "point": [122.54, 69.84],
          "side": "top",
          "type": "input",
          "roles": ["serial_data_in"]
        }
      }
    }
  },
  "nets": {
    "SHIFT_CLK": {
      "class": "clock",
      "endpoints": ["U1.D13", "U2.SHCP", "U3.SHCP"],

## Page 7

ProGenEDA KiCad Routing Engine Refactor Plan
Page 7
      "fanout": 3,
      "criticality": 10
    }
  },
  "routes": {},
  "metrics": {}
}
6.1 Required LiveRoutingState operations
clone_state()
apply_move(ref, x, y)
apply_rotation(ref, rotation)
apply_move_rotation(ref, x, y, rotation)
recompute_component_body(ref)
recompute_component_keepout(ref)
recompute_component_pin_anchors(ref)
find_overlaps(ref)
find_blockers(ref)
legalize_after_move(ref)
score_fast()
score_routeability()
All optimization happens in LiveRoutingState. The exporter touches KiCad only after the best state is selected.
7. Mathematical foundations and deterministic pruning laws
The new planner should not brute force every route. Use cheap mathematical lower bounds and pruning rules first, then
run expensive routing only on survivors.
7.1 HPWL lower bound
For a rectilinear net, half-perimeter wire length is a lower bound on any route connecting all terminals because any
connected rectilinear route must span the full x-range and y-range of the terminals.
HPWL(net) = (max_x - min_x) + (max_y - min_y)
Weighted HPWL:
  clock/control nets       HPWL * 8
  bus nets                 HPWL * 5
  display segment nets     HPWL * 4
  ordinary signal nets     HPWL * 2
  power/ground nets        HPWL * 0.5
Use HPWL before full routing. If a candidate cannot beat the current best lower bound, skip deep routing.
7.2 Hanan-grid routing candidates
For rectilinear routing, important candidate branch/lane points can be restricted to grid lines passing through terminals,
plus obstacle escape lines. This is the practical value of the Hanan-grid idea.
For each net:
  terminal_xs = x coordinates of all pin anchors
  terminal_ys = y coordinates of all pin anchors
Add obstacle escape lines:
  body.left   - clearance
  body.right  + clearance
  body.top    - clearance
  body.bottom + clearance
Candidate lanes = terminal lines + obstacle escape lines + sheet edge lanes
This improves the current lane generation because lanes become mathematically meaningful instead of only heuristic
around bodies and edges.
7.3 Rectilinear MST upper bound
For multi-terminal nets, build a complete graph between terminals using Manhattan distance, then compute a minimum
spanning tree. It is not always optimal, but it gives a cheap skeleton and upper-bound style estimate before detailed
routing.
For each multi-terminal net:

## Page 8

ProGenEDA KiCad Routing Engine Refactor Plan
Page 8
  endpoints = pins
  edge_weight(a,b) = Manhattan(a,b)
  tree = MST(endpoints)
  route MST edges using lane candidates/A*
7.4 A* with Manhattan heuristic
In a four-direction rectilinear grid, Manhattan distance is an admissible lower-bound heuristic when costs are
nonnegative. Use A* only for top candidates, not for every approximate placement.
priority = cost_so_far + manhattan(current_cell, goal_cell)
7.5 Coordinate-wise median for cluster center
For Manhattan distance, the coordinate-wise median minimizes total absolute distance. Use it to estimate local cluster
centers quickly.
ideal_x = median(all connected pin x values)
ideal_y = median(all connected pin y values)
7.6 Pareto dominance pruning
Before expensive scoring, remove candidates that are obviously worse. Candidate A dominates B if A is no worse in
every cheap metric and better in at least one.
A dominates B if:
  A.hpwl <= B.hpwl
  A.overlap_count <= B.overlap_count
  A.pin_facing_penalty <= B.pin_facing_penalty
  A.bus_misalignment <= B.bus_misalignment
  A.out_of_sheet == false
and at least one value is strictly better.
7.7 Branch-and-bound
Keep the best complete routed score so far. For new candidates, compute a cheap lower bound. If the lower bound is
already worse than the best full score, skip deep routing.
candidate_lower_bound =
  HPWL_score
  + minimum_possible_turns
  + overlap_penalty
  + out_of_sheet_penalty
  + pin_facing_lower_bound
if candidate_lower_bound > current_best_full_score:
  skip expensive routing
7.8 Orthogonal segment indexing
Do not compare every wire against every other wire for crossing counts once designs grow. Use an orthogonal segment
index.
horizontal segments indexed by y
vertical segments indexed by x
crossing exists if:
  vertical.x lies inside horizontal.x_range
  horizontal.y lies inside vertical.y_range
8. Pin resolver and rotation math
Rotation support is not optional. The router cannot make intelligent decisions until pin anchors are exact after rotation.
8.1 Coordinate transform
Given local pin point (x, y) around component center:
rotation 0:
  x' = x
  y' = y
rotation 90:

## Page 9

ProGenEDA KiCad Routing Engine Refactor Plan
Page 9
  x' = -y
  y' = x
rotation 180:
  x' = -x
  y' = -y
rotation 270:
  x' = y
  y' = -x
absolute:
  abs_x = component_center_x + x'
  abs_y = component_center_y + y'
8.2 Side transform
rotation 0:
  left -> left, right -> right, top -> top, bottom -> bottom
rotation 90:
  left -> top, top -> right, right -> bottom, bottom -> left
rotation 180:
  left -> right, right -> left, top -> bottom, bottom -> top
rotation 270:
  left -> bottom, bottom -> right, right -> top, top -> left
8.3 What Rust pin resolver returns
{
  "ref": "U2",
  "type_id": "74HC595_DIP16",
  "at": [120.0, 80.0],
  "rotation": 90,
  "pins": {
    "SER": {
      "point": [122.54, 69.84],
      "side": "top",
      "type": "input",
      "roles": ["serial_data_in"]
    }
  }
}
9. Connectivity graph, pivot, and component priority
The placement engine should grow from a high-value pivot. Priority should be based on component role, graph
connectivity, and current pivot context.
9.1 Net weights
Net class
Examples
Suggested weight
clock/control
CLK, CLOCK, SHCP, STCP, RESET, LATCH
10
bus
SPI, I2C, UART, SEG_A-G, DATA, ADDRESS, SHIFT
6
display segment
SEG_A, SEG_B, Q0->A
5
ordinary signal
button, enable, local nets
3
power/ground
+5V, +3V3, VCC, GND
0.25 to 1
9.2 Pivot selection
pivot_score =
  weighted_degree * 10
  + bus_endpoint_count * 6
  + clock_endpoint_count * 8
  + large_fanout_control_count * 5
  + fixed_anchor_bonus
  + user_primary_component_bonus

## Page 10

ProGenEDA KiCad Routing Engine Refactor Plan
Page 10
  - power_only_connection_penalty
9.3 Live component priority
live_priority =
  base_catalogue_priority
  + pivot_connection_weight
  + critical_net_bonus
  + bus_group_bonus
  + already_routed_cluster_bonus
  + user_fixed_bonus
  - low_importance_connector_penalty
active_component_priority = live_priority + active_component_priority_boost
The active component gets a temporary boost because it was selected as important to the current pivot/cluster. This
matters for legalization: low-priority blockers must move.
10. Cluster-growth placement flow
1. Build weighted component connectivity graph.
2. Select pivot component.
3. Initialize placed cluster with pivot.
4. Select next component strongly connected to placed cluster.
5. Generate candidate locations around connected placed anchors.
6. For each candidate location, estimate all legal rotations cheaply.
7. Keep top 1-2 rotations per location.
8. Run priority-aware legalization.
9. Score candidate state cheaply.
10. Keep top beam states.
11. Repeat until all components are placed.
12. Fully route top N final states.
13. Select best final state.
10.1 Beam search configuration
{
  "placement": {
    "beam_width": 12,
    "candidate_locations_per_component": 24,
    "rotations_per_location_keep": 2,
    "deep_route_top_n": 4,
    "max_candidate_states_per_step": 128
  }
}
11. Rotation-aware location scoring
Do not score a location alone. Score (location, rotation). A location that looks bad at rotation 0 may become excellent at
rotation 90 or 180.
11.1 Cheap approximate rotation score
rotation_score =
  weighted_HPWL_after_rotation
  + pin_facing_penalty
  + bus_order_penalty
  + power_ground_side_penalty
  + estimated_crossing_penalty
  + rotation_cost
11.2 Rotation pruning
For each candidate location:
  evaluate all legal rotations using pin math only
  keep top 1-2 rotations
  discard the rest before legalization/routing
11.3 Pin-facing score
For each connection endpoint pair:
  if source pin side faces target component:
    subtract bonus
  if source pin points away from target:

## Page 11

ProGenEDA KiCad Routing Engine Refactor Plan
Page 11
    add penalty
Examples:
  74HC595 Q0-Q7 should face LED/seven-segment display.
  74HC595 SER should face previous shift-register/controller.
  74HC595 Q7S should face next shift register.
  Power pins prefer top.
  Ground pins prefer bottom.
11.4 Bus order score
Good:
  Q0 -> A, Q1 -> B, Q2 -> C, ... with monotonic order.
Bad:
  Q0 -> G, Q1 -> A, Q2 -> F, ... causing braided wires.
Penalty:
  count order inversions between source bus pin order and target pin order.
12. Priority-aware legalization
The old Level A idea of rejecting a placement because it overlaps is unacceptable for your engine. The active component
is being moved because it is important to the current pivot/cluster. If its location is high quality, lower-priority blockers
should be moved out of the way.
12.1 New legalization principle
The selected target location is treated as a high-priority placement request. Reject only if fixed, locked, or
higher-priority blockers make local legalization impossible after bounded attempts.
12.2 Legalization algorithm
Input:
  active component A
  desired position P
  desired rotation R
  current LiveRoutingState
Algorithm:
  1. Place A virtually at (P, R).
  2. Find all blockers overlapping A.keepout.
  3. If no blockers: accept.
  4. If blocker is locked/fixed: try next best nearby slot for A.
  5. If blocker.priority >= A.priority:
       compare A target quality vs blocker displacement cost.
       If blocker is more important, try nearby slot for A.
  6. If blocker.priority < A.priority:
       keep A at target.
       move blocker to nearest legal slot.
  7. If moved blocker creates new blocker:
       recursively legalize up to max depth.
  8. If recursion fails:
       expand legalization window.
  9. If still impossible:
       try next candidate location for A.
12.3 Legalization config
{
  "legalization": {
    "max_depth": 3,
    "window_initial_radius": 25.4,
    "window_max_radius": 101.6,
    "slot_grid": 2.54,
    "max_slots_per_component": 64,
    "active_component_priority_boost": 1000,
    "locked_component_infinite_cost": true
  }
}
12.4 Minimum-cost local assignment
When multiple blockers exist, do not push randomly. Treat it as a small local assignment problem.

## Page 12

ProGenEDA KiCad Routing Engine Refactor Plan
Page 12
components_to_place = active component + blockers
slots = legal grid positions inside local window
cost(component, slot) =
  priority_weight * displacement
  + HPWL_delta
  + pin_facing_delta
  + routeability_delta
Constraint:
  active component is forced into selected target slot unless impossible.
Solve:
  minimum-cost assignment for blockers around active component.
12.5 Fast good-enough acceptance
Accept without deep route if:
  1. no locked blocker
  2. local assignment feasible
  3. weighted HPWL improves by threshold
  4. pin-facing improves or stays same
  5. bus alignment improves or stays same
  6. crossing density estimate below threshold
  7. no component outside sheet
  8. no keepout overlap after legalization
Deep route only if:
  - HPWL improvement is small
  - pin-facing is mixed
  - bus alignment is risky
  - component fanout is high
  - local density is high
  - critical net crosses dense region
13. Routing engine and crossing policy
Schematic routing is not PCB routing. Different-net 90-degree crossings can be allowed as readability penalties, not hard
failures. This is especially useful in KiCad schematics, where net names/labels and schematic readability matter more
than physical copper constraints.
13.1 Routing order
1. Clock/control nets
2. Bus nets
3. Short local nets
4. Ordinary signal nets
5. Display/segment nets
6. Power nets
7. Ground nets
13.2 Multi-terminal net routing
For each multi-terminal net:
  endpoints = all pins
  if power/ground/global and terminal mode is allowed:
    prefer labels/rails
  root = best root endpoint
  connected = {root}
  unconnected = rest
  while unconnected:
    choose endpoint with smallest routeability distance to connected tree
    route from nearest connected point/tree node to endpoint
    add path to tree
13.3 Allowed crossings
- Different-net 90-degree crossings.

- Short crossings in open whitespace.

- Crossings far from symbol pins.

## Page 13

ProGenEDA KiCad Routing Engine Refactor Plan
Page 13
- Crossings on low-criticality ordinary nets.

13.4 Strongly penalized crossings
- Crossings near pins or labels.

- Crossings inside dense component clusters.

- Many crossings in the same small tile/region.

- Crossings on clock/control nets.

- Crossings that make bus wires visually braid.

13.5 Forbidden contacts
- Different-net collinear overlap.

- Different-net T-touch.

- Wire passing through component body.

- Wire endpoint touching wrong net.

- Wire crossing exactly on a pin point unless that pin is the intended endpoint.

- Unintentional junction/dot behavior between different nets.

13.6 Crossing score
{
  "crossing": {
    "base_crossing_weight": 2.0,
    "clock_crossing_weight": 25.0,
    "bus_crossing_weight": 4.0,
    "near_pin_crossing_weight": 50.0,
    "density_tile_size": 25.4,
    "max_crossings_per_tile_soft": 6,
    "tile_overflow_weight": 30.0,
    "forbid_collinear_overlap": true,
    "forbid_t_touch_different_net": true
  }
}
14. Optional KiCad netclass colors
Netclass/color support should be optional. Use it only if it is easy in your KiCad exporter. Do not let color block the routing
engine.
{
  "CLOCK_CONTROL": {
    "color": "#ff4d4d",
    "priority": 100
  },
  "BUS": {
    "color": "#4d79ff",
    "priority": 80
  },
  "POWER": {
    "color": "#cc33cc",
    "priority": 70
  },
  "GROUND": {
    "color": "#333333",
    "priority": 70
  },
  "DISPLAY_SEGMENT": {
    "color": "#ffaa00",
    "priority": 60
  },
  "ORDINARY_SIGNAL": {
    "color": "#00aa66",
    "priority": 40

## Page 14

ProGenEDA KiCad Routing Engine Refactor Plan
Page 14
  }
}
If KiCad wire coloring becomes annoying: ignore it for MVP. Keep the relaxed crossing policy and use labels/net
names/readability scoring instead.
15. Rust/Python split
Keep in Python
Move to Rust
JSON orchestration
pin transform and side transform
config loading
body/keepout recomputation
catalogue loading
HPWL calculation
KiCad adapter/exporter
connectivity graph scoring
Proteus adapter/exporter
pivot selection and live priority
validation report writer
rotation scoring
benchmark runner
candidate placement scoring
AI planner/model router
priority-aware legalization
debug artifact saving
occupancy grid and A* routing
old planner compatibility wrapper
crossing counting and geometry validation
16. Rust module design
types.rs
  ComponentType, ComponentInstance, PinDef, PinAnchor, Net, Endpoint,
  BodyRect, KeepoutRect, RouteSegment, LiveRoutingState,
  CandidatePlacement, LegalizationResult, ScoreReport
geometry.rs
  snap_to_grid, manhattan, rotate_point, rotate_side, aabb_overlap,
  segment_rect_contact, orthogonal_segment_cross, compress_path
catalogue.rs
  parse_component_catalogue, get_component_type, validate_catalogue
pin_resolver.rs
  resolve_component_pins, resolve_all_pins, resolve_after_move_rotation
connectivity.rs
  classify_net, build_component_graph, calculate_component_priority,
  select_pivot, select_next_component
placement.rs
  generate_candidate_locations, estimate_rotation_scores,
  pareto_prune_candidates, beam_search_cluster_growth
legalization.rs
  find_blockers, generate_legal_slots, solve_local_assignment,
  push_lower_priority_blockers, legalize_candidate
occupancy.rs
  build_occupancy_grid, update_component_occupancy,
  update_wire_occupancy, segment_density_query
routing.rs
  generate_hanan_lanes, route_lane_candidates, route_astar,
  route_multiterminal_tree, route_all_nets
scoring.rs
  score_hpwl, score_pin_facing, score_bus_alignment, score_crossings,
  score_density, score_readability, score_total
validation.rs
  validate_wire_geometry, validate_no_component_overlap,
  validate_no_forbidden_wire_contacts, validate_no_out_of_sheet

## Page 15

ProGenEDA KiCad Routing Engine Refactor Plan
Page 15
parallel.rs
  evaluate_candidates_parallel, evaluate_beam_states_parallel,
  route_final_states_parallel
17. Python orchestration design
def plan_wiring_v2(placement, circuit, component_catalogue, config):
    catalogue = load_component_catalogue(component_catalogue)
    payload = {
        "catalogue": catalogue,
        "placement": placement,
        "circuit": circuit,
        "config": config,
    }
    result_json = progen_routing_core.plan_full(json.dumps(payload))
    result = json.loads(result_json)
    return {
        "schema": "progen-kicad-wire-planner-output/v0.2",
        "coordinate_plan": result["coordinate_plan"],
        "routing_placement": result["routing_placement"],
        "wire_plan": result["wire_plan"],
        "arrangement_selection": result["arrangement_selection"],
        "engine": "rust_core_v0.1",
        "metrics": result.get("metrics", {}),
        "warnings": result.get("warnings", []),
    }
18. Rust API exposed to Python
#[pyfunction]
fn build_live_state(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn resolve_pins(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn score_rotations(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn legalize_candidate(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn score_placement_variants(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn route_variants(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn validate_geometry(input_json: &str) -> PyResult<String>;
#[pyfunction]
fn plan_full(input_json: &str) -> PyResult<String>;
Use JSON first. Do not prematurely optimize into binary structs. JSON is easier to debug and keeps compatibility with the
existing planner artifacts.
19. Parallel multi-instance compute model
Do not spawn many Python threads. Python should call Rust once. Rust should control the thread pool and evaluate
candidates/variants internally.
Python:
  result = progen_routing_core.plan_full(json.dumps(payload))
Rust internal parallelism:
  - evaluate candidate rotations in parallel
  - evaluate legalization candidates in parallel
  - score beam states in parallel
  - route top final states in parallel
Config:
{
  "parallel": {

## Page 16

ProGenEDA KiCad Routing Engine Refactor Plan
Page 16
    "threads": 8,
    "beam_width": 12,
    "max_candidate_states_per_step": 128,
    "deep_route_top_n": 4,
    "debug_parallel": false
  }
}
19.1 Rules for safe parallelism
- Each candidate state must be immutable or cloned before parallel scoring.

- Avoid nested parallelism. One Rust thread pool controls the heavy work.

- Return compact result JSON by default. Full debug payloads only when debug=true.

- Do not mutate global catalogue data. Catalogue should be read-only after load.

- Use deterministic sorting after parallel results return so output is stable across runs.

20. Output contracts
Final output must remain compatible with the existing planner contract so your KiCad exporter and tests do not break
immediately.
{
  "schema": "progen-kicad-wire-planner-output/v0.2",
  "coordinate_plan": {
    "coordinate_edits": []
  },
  "routing_placement": {
    "components": {},
    "pin_points": {},
    "obstacles": []
  },
  "wire_plan": {
    "schema": "progen-kicad-wire-plan/v0.2",
    "nets": {},
    "routes": [],
    "metrics": {},
    "warnings": []
  },
  "arrangement_selection": {
    "selected_variant": "beam_state_7",
    "selected_score": {},
    "variants": []
  },
  "metrics": {},
  "warnings": []
}
21. Validation/reporting
Generate a validation report for every output. This is how you avoid manually tracing every wire.
{
  "schema": "progen-routing-validation-report/v0.2",
  "project": "example_clock_level_1",
  "engine": "rust_core_v0.1",
  "checks": {
    "component_overlap": "pass",
    "out_of_sheet": "pass",
    "pin_resolution": "pass",
    "wire_geometry": "pass",
    "forbidden_contacts": "pass",
    "netlist_equivalence_ready": true
  },
  "metrics": {
    "component_count": 84,
    "net_count": 62,
    "route_count": 58,
    "wire_length": 1200.5,
    "turn_count": 88,
    "different_net_crossing_count": 12,
    "crossing_density_overflow": 0,
    "unroutable_net_count": 0,

## Page 17

ProGenEDA KiCad Routing Engine Refactor Plan
Page 17
    "partial_wire_net_count": 0,
    "body_hit_count": 0
  },
  "accepted_warnings": [
    "different-net 90-degree schematic crossings accepted as readability penalties"
  ],
  "blocking_failures": []
}
22. Migration plan
Phase 1: Catalogue foundation
  1. Move catalogues to kicad/pipeline/catelogues.
  2. Create component_catalogue.schema.json.
  3. Add 10-20 high-value components first.
  4. Add kicad_symbol_map and kicad_footprint_map.
Phase 2: LiveRoutingState
  1. Build Python LiveRoutingState builder.
  2. Use catalogue geometry to compute bodies/keepouts.
  3. Keep current wire_planner output contract unchanged.
Phase 3: Rust pin resolver
  1. Create Rust PyO3/maturin module.
  2. Implement rotate_point and rotate_side.
  3. Implement resolve_pins.
  4. Compare Rust pin output against old exact pin_points.
Phase 4: Rust geometry validator
  1. Port wire_geometry_validator.py rules.
  2. Match old validator outputs on test cases.
  3. Add forbidden T-touch/overlap checks.
Phase 5: Rust collision and legalization
  1. Implement body/keepout overlap.
  2. Implement blocker detection.
  3. Implement priority-aware legalization.
  4. Implement local slot assignment.
Phase 6: Rust placement scoring
  1. Implement HPWL.
  2. Implement connectivity graph.
  3. Implement pivot and next-component selection.
  4. Implement rotation-aware candidate scoring.
  5. Implement Pareto and branch-and-bound pruning.
Phase 7: Rust routing
  1. Implement Hanan lane candidates.
  2. Port lane scoring.
  3. Port A*.
  4. Implement multi-terminal tree routing.
  5. Implement relaxed crossing policy.
Phase 8: Parallel beam search
  1. Implement parallel candidate evaluation.
  2. Keep deterministic sorting.
  3. Route only top N final states.
Phase 9: Replace old planner internals
  1. old_wire_planner_adapter.py calls new plan_wiring_v2.
  2. Keep fallback flag to old Python planner.
  3. Run regression benchmarks.
23. Acceptance tests and benchmarks
23.1 Unit tests
- Pin transform: local pin at left rotates correctly through 0/90/180/270.

- Side transform: left -> top at 90, left -> right at 180, left -> bottom at 270.

- Body recompute: width/height swap correctly at 90/270 if body is rectangular.

- Overlap: moving U1 onto U2 detects blocker.

- Legalization: active high-priority component keeps target and pushes lower-priority blocker.

## Page 18

ProGenEDA KiCad Routing Engine Refactor Plan
Page 18
- Locked blocker: active component cannot push locked component and must choose alternative.

- Wire validation: orthogonal route passes; non-orthogonal route fails.

- Forbidden contact: different-net T-touch fails; 90-degree crossing in open space passes with penalty.

23.2 Regression metrics
Compare old Python planner vs new Rust engine:
  - runtime
  - component_overlap_count
  - unresolved_blocker_count
  - unroutable_net_count
  - partial_wire_net_count
  - body_hit_count
  - forbidden_contact_count
  - different_net_crossing_count
  - crossing_density_overflow
  - total_wire_length
  - turn_count
  - KiCad file open success
  - KiCad netlist equivalence success
  - ERC blocker count
23.3 Pass criteria
Required:
  component_overlap_count == 0
  body_hit_count == 0
  forbidden_contact_count == 0
  unresolved_blocker_count == 0
  KiCad project opens
  exported netlist matches expected netlist
Allowed:
  different_net_crossing_count > 0 if density controlled
  visual crossings if not near pins and not on critical nets
  accepted ERC warnings if categorized
Not allowed:
  wire through component body
  collinear overlap of different nets
  T-touch of different nets
  missing pin anchor
  component stacked on component
  route that depends on manual correction
24. Codex implementation prompt
You are refactoring ProGenEDA's KiCad routing/placement pipeline.
Use this folder structure:
kicad/pipeline/catelogues/
  component_catalogue.schema.json
  component_catalogue.json
  component_catalogue_loader.py
  kicad_symbol_map.json
  kicad_footprint_map.json
kicad/pipeline/routing/
  python/
    routing_orchestrator.py
    live_routing_state.py
    routing_config.py
    validation_report.py
    old_wire_planner_adapter.py
  rust_core/
    Cargo.toml
    pyproject.toml
    src/lib.rs
    src/types.rs
    src/geometry.rs
    src/catalogue.rs
    src/pin_resolver.rs
    src/connectivity.rs
    src/placement.rs

## Page 19

ProGenEDA KiCad Routing Engine Refactor Plan
Page 19
    src/legalization.rs
    src/occupancy.rs
    src/routing.rs
    src/scoring.rs
    src/validation.rs
    src/parallel.rs
Catalogues live outside routing because they will also be used by schematic
  generation, validation, PCB generation, and future exporters.
Goal:
Replace repeated beautifier-coordinate mutation with a mathematical
  LiveRoutingState.
The LiveRoutingState must store:
- component refs
- type_id
- current position
- current rotation
- priority
- locked/movable status
- body rectangle
- keepout rectangle
- absolute pin anchors
- net endpoints
- routed segments
- metrics
The permanent component catalogue must store:
- abstract component type id
- body width/height
- keepout
- legal rotations
- default rotation
- local pin coordinates relative to component center
- pin side at rotation 0
- pin type
- pin roles
- bus groups
- preferred input/output/power/ground sides
- placement priority
- push priority
- readability hints
Keep the Rust core EDA-agnostic. Do not write KiCad files from Rust.
Implement mathematically grounded routing/placement rules:
1. HPWL lower-bound scoring for rectilinear nets.
2. Hanan-grid lane generation for multi-terminal rectilinear routing.
3. Rectilinear MST as a cheap route-tree upper-bound estimate.
4. A* with Manhattan heuristic for grid fallback.
5. Coordinate-wise median for cluster center estimation.
6. Pareto dominance pruning of placement candidates.
7. Branch-and-bound pruning using cheap lower-bound score.
8. Fast orthogonal crossing counting using segment indexing.
Placement algorithm:
- Build weighted component connectivity graph.
- Downweight power/ground nets.
- Upweight clock/control/bus/display-segment nets.
- Select pivot by weighted degree, critical nets, bus nets, and user-primary
  hints.
- Grow placement cluster from pivot.
- Select next component by strongest weighted connection to already placed
  cluster.
- Generate candidate locations around connected placed anchors.
- For each location, estimate all legal rotations using cheap pin math.
- Keep the best 1-2 rotations per location.
- Only deep-route top candidates.
Rotation scoring:
- Score (location, rotation), not location alone.
- Use weighted HPWL after rotation, pin-facing score, bus-order score,
  power/ground side score, estimated crossing score, and rotation penalty.
- Do not run full A* for every rotation.
Legalization:
- Do not reject a high-quality target just because another component is there.
- The active component is high priority with respect to the current pivot.
- Give the active component a large temporary priority boost.
- Place active component at the desired target if possible.

## Page 20

ProGenEDA KiCad Routing Engine Refactor Plan
Page 20
- Identify blockers.
- Locked/fixed blockers are hard constraints.
- Lower-priority blockers must be moved to nearby legal slots.
- Use a bounded local legalization window.
- Use minimum-cost local assignment for active component + blockers.
- Cost = priority-weighted displacement + HPWL delta + pin-facing delta +
  routeability delta.
- Active component is forced into the chosen target unless impossible.
- Recursively legalize pushed blockers with max depth 3.
- Expand window if needed.
- Reject only if local legalization is impossible after bounded expansion.
Crossing policy:
- Different-net 90-degree crossings are allowed as quality penalties, not hard
  failures.
- Strongly penalize crossings near pins, in dense regions, and on
  clock/control nets.
- Forbid different-net collinear overlap.
- Forbid different-net T-touch.
- Forbid wire through component body.
- Forbid wire endpoint touching wrong net.
- Count crossing density by tiles so output does not become a mesh of
  insanity.
Optional KiCad visual enhancement:
- Add netclass assignment/colors for CLOCK_CONTROL, BUS, POWER, GROUND,
  DISPLAY_SEGMENT, ORDINARY_SIGNAL.
- Treat color as visual only. Do not make it required for correctness.
Move these from Python to Rust:
- pin transform
- side transform
- body/keepout recomputation
- HPWL calculation
- component graph scoring
- pivot selection
- rotation scoring
- candidate placement scoring
- legalization
- collision detection
- occupancy grid
- Hanan lane generation
- A*
- route scoring
- crossing counting
- geometry validation
- parallel candidate evaluation
Keep in Python:
- JSON orchestration
- config loading
- catalogue loading
- KiCad adapter/exporter
- Proteus adapter/exporter
- validation report writer
- benchmark runner
- AI planner interface
Expose Rust functions:
- build_live_state(input_json: str) -> str
- resolve_pins(input_json: str) -> str
- score_rotations(input_json: str) -> str
- legalize_candidate(input_json: str) -> str
- score_placement_variants(input_json: str) -> str
- route_variants(input_json: str) -> str
- validate_geometry(input_json: str) -> str
- plan_full(input_json: str) -> str
Use Rust internal parallelism for candidate/variant evaluation. Python should
  call Rust once with a JSON payload and receive JSON back.
Final output must remain compatible with the current planner contract:
- coordinate_plan
- routing_placement
- wire_plan
- arrangement_selection
- metrics
- warnings
Do not break existing tests. Add regression tests comparing old planner vs new
  engine for:

## Page 21

ProGenEDA KiCad Routing Engine Refactor Plan
Page 21
- component overlap count
- unroutable net count
- body-hit count
- forbidden contact count
- crossing count
- route length
- runtime
25. Final checklist
- Catalogue lives at kicad/pipeline/catelogues, not inside routing.

- Catalogue is abstract/EDA-agnostic; KiCad symbol/footprint maps are separate.

- LiveRoutingState is the only optimization scratchpad.

- Pin anchors are resolved mathematically from local catalogue coordinates plus rotation.

- Placement scores (location, rotation), not location alone.

- Active component gets temporary priority boost during pivot/cluster placement.

- Legalization pushes lower-priority blockers instead of rejecting top locations.

- Locked/fixed/high-priority blockers still constrain placement.

- Use HPWL, Hanan-grid lanes, MST estimate, A*, median, Pareto pruning, and branch-and-bound.

- Different-net 90-degree crossings are allowed but density-controlled.

- T-touch, collinear overlap, wrong pin touch, and body crossings are forbidden.

- Color/netclass support is optional visual enhancement, not a blocker.

- Rust owns heavy geometry/routing; Python owns orchestration/exporters/reports.

- Final output stays compatible with coordinate_plan, routing_placement, wire_plan, arrangement_selection.

- Regression tests must prove no component overlap, no body hits, no forbidden contacts, no worse unroutable count,
 and acceptable runtime.
