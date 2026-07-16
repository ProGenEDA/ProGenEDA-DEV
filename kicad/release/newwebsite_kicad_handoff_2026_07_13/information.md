        # ProGenEDA KiCad Information

        ## Current Product Scope

        ProGenEDA KiCad consumes one canonical ProGenEDA main JSON. The same
        input first produces a validated native KiCad schematic and then, when
        the physical subset is supported and routes cleanly, a native two-layer
        KiCad PCB. There is no parallel PCB-specific input schema.

        - Schematic vocabulary: 103 canonical words and aliases in `KC-A.json`.
        - Default generation mode: `combination`.
        - Public schematic artifact: `PROGEN_KICAD_PROJECT.zip`.
        - Direct PCB artifact: a native `.kicad_pcb` exposed only after hosted
          PCB validation passes.
        - PCB-only command: `progen-kicad run-pcb main.json --output-root OUT`.

        ## Architecture

        ```text
        canonical main JSON
        -> input JSON fixer and validator
        -> component selection and source-backed schematic placement
        -> arrangement decision and coordinate beautifier
        -> wire/terminal/combination planner and wire maker
        -> value and final schematic validators
        -> physical-design compiler
        -> embedded KiCad 10.0.4 footprint catalogue
        -> square-fill footprint placement
        -> two-layer router with retained deterministic variants
        -> native PCB writer and independent parser/validator
        -> user project / direct PCB / private internal bundle
        ```

        The public download receives only the requested project or direct PCB.
        The private internal bundle retains the original/fixed input, every
        generated JSON, placement and route variants, accepted-variant marker,
        validation reports, and project artifacts for database reconstruction.

        ## Embedded Source and Validation

        PCB generation and primary validation do not require KiCad installed on
        the hosting server. The portable executable embeds 34
        audited KiCad 10.0.4 footprint records, their
        source text, pad geometry, bounds, SHA-256 digests, mapping catalogue,
        and source-reference material. An installed KiCad 10 CLI is an optional
        external DRC oracle, never a runtime generator dependency.

        PCB acceptance requires source digest verification, native file parsing,
        component/reference/value checks, exact pad-net comparison, copper graph
        connectivity, clearance checks, non-overlapping placement, and a closed
        outline. A board that fails any hosted check is never offered as a user
        artifact.

        ## KiCad PCB Supported Physical Mappings

        - `74HC595_DIP16` -> `Package_DIP:DIP-16_W7.62mm`
- `ArduinoNano_Module` -> `Module:Arduino_Nano`
- `Capacitor_Electrolytic` -> `Capacitor_THT:CP_Radial_D6.3mm_P2.50mm`
- `Capacitor_Generic` -> `Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm`
- `Connector_Generic` -> `TerminalBlock_Altech:Altech_AK100_1x02_P5.00mm`
- `Diode_Axial` -> `Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal`
- `ESP32_WROOM_Module` -> `RF_Module:ESP32-WROOM-32`
- `GND_Symbol` -> `no physical footprint`
- `LED_Generic` -> `LED_THT:LED_D5.0mm`
- `LM358_DualOpAmp` -> `Package_DIP:DIP-8_W7.62mm`
- `MAX485_SO8` -> `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`
- `NMOS_3Pin` -> `Package_TO_SOT_THT:TO-92_Inline`
- `NPN_3Pin` -> `Package_TO_SOT_THT:TO-92_Inline`
- `Power_Symbol` -> `no physical footprint`
- `Regulator_3Pin` -> `Package_TO_SOT_THT:TO-220-3_Vertical`
- `Resistor_Axial` -> `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal`
- `VSource_DC` -> `no physical footprint`
- `W25Q64_SOIC8` -> `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`

        The footprint source pack also includes axial resistor/diode, ceramic
        and electrolytic capacitors, LED, DIP/SOIC/TO packages, terminals,
        Arduino Nano, ESP32-WROOM, and 1x01 through 1x20 pin-header records.
        Generic connectors select an audited header by required numeric pad
        count, up to 20 positions.

        ## Current PCB Limits

        - No output board is produced for unsupported physical pin-to-pad mappings.
- No output board is produced when bounded two-layer routing leaves a net unrouted.
- No copper pours, differential-pair constraints, impedance control, length matching, thermal design, or universal dense-board autorouting.

        ## Future Direction

        Next physical iterations can add audited footprint mappings, more board
        stackups and rule profiles, copper pours, class-aware constraints,
        differential pairs, controlled impedance, length matching, stronger
        dense-board routing, manufacturing-output policies, and native Altium
        backends. The canonical main JSON and backend-neutral stage contracts
        are intentionally retained so those additions do not replace the input
        model.
