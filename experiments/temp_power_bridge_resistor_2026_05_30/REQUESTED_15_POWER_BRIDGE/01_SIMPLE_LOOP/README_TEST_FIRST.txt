01_SIMPLE_LOOP

Temporary power-bridge resistor generator output.

Endpoint rules under test:
- Powered resistor endpoints remain normal $TERINPUT(V0) terminals.
- One donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge connects the power node.
- G0/ground nodes on component.nodes[1] become $TERGROUND endpoints with the normal short wire.
