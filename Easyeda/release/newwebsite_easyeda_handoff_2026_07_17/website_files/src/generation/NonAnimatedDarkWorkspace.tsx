import {
  Activity,
  DocumentText,
  Edit2,
  Export,
  ShieldTick,
  Warning2,
} from 'iconsax-react';
import {
  CSSProperties,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
  useEffect,
  useRef,
  useState,
} from 'react';

type BoardPin = {
  id: string;
  label: string;
  x: number;
  y: number;
  side: 'left' | 'right' | 'top' | 'bottom';
};

type BoardPart = {
  id: string;
  label: string;
  kind: 'ic' | 'logic' | 'opamp' | 'resistor' | 'capacitor' | 'source' | 'diode' | 'connector' | 'ground';
  x: number;
  y: number;
  w: number;
  h: number;
  note: string;
  pins: BoardPin[];
};

type BoardWire = {
  id: string;
  from: { partId: string; pinId: string };
  to: { partId: string; pinId: string };
  speed: number;
};

const initialBoardParts: BoardPart[] = [
  {
    id: 'V1',
    label: '12V DC',
    kind: 'source',
    x: 92,
    y: 234,
    w: 72,
    h: 72,
    note: 'regulated input',
    pins: [
      { id: 'P', label: '+', x: 36, y: -8, side: 'right' },
      { id: 'N', label: '-', x: 12, y: 36, side: 'bottom' },
    ],
  },
  {
    id: 'F1',
    label: '500mA',
    kind: 'resistor',
    x: 198,
    y: 232,
    w: 88,
    h: 34,
    note: 'input fuse',
    pins: [
      { id: 'IN', label: 'IN', x: -44, y: 0, side: 'left' },
      { id: 'OUT', label: 'OUT', x: 44, y: 0, side: 'right' },
    ],
  },
  {
    id: 'U1',
    label: '74HC08',
    kind: 'logic',
    x: 340,
    y: 162,
    w: 150,
    h: 122,
    note: 'quad AND gate',
    pins: [
      { id: 'A1', label: 'A1', x: -75, y: -42, side: 'left' },
      { id: 'B1', label: 'B1', x: -75, y: -18, side: 'left' },
      { id: 'A2', label: 'A2', x: -75, y: 6, side: 'left' },
      { id: 'GND', label: 'GND', x: -75, y: 42, side: 'left' },
      { id: 'Y1', label: 'Y1', x: 75, y: -42, side: 'right' },
      { id: 'Y2', label: 'Y2', x: 75, y: -18, side: 'right' },
      { id: 'VCC', label: 'VCC', x: 75, y: 18, side: 'right' },
      { id: 'Y3', label: 'Y3', x: 75, y: 42, side: 'right' },
    ],
  },
  {
    id: 'R1',
    label: '4.7k',
    kind: 'resistor',
    x: 528,
    y: 118,
    w: 96,
    h: 32,
    note: 'pull-up bank',
    pins: [
      { id: 'A', label: 'A', x: -48, y: 0, side: 'left' },
      { id: 'B', label: 'B', x: 48, y: 0, side: 'right' },
    ],
  },
  {
    id: 'D1',
    label: 'LED',
    kind: 'diode',
    x: 658,
    y: 118,
    w: 72,
    h: 44,
    note: 'status diode',
    pins: [
      { id: 'A', label: 'A', x: -36, y: 0, side: 'left' },
      { id: 'K', label: 'K', x: 36, y: 0, side: 'right' },
    ],
  },
  {
    id: 'U2',
    label: 'NE555',
    kind: 'ic',
    x: 824,
    y: 164,
    w: 154,
    h: 128,
    note: 'timing core',
    pins: [
      { id: 'GND', label: 'GND', x: -77, y: -45, side: 'left' },
      { id: 'TRIG', label: 'TRIG', x: -77, y: -15, side: 'left' },
      { id: 'OUT', label: 'OUT', x: -77, y: 15, side: 'left' },
      { id: 'RESET', label: 'RESET', x: -77, y: 45, side: 'left' },
      { id: 'CTRL', label: 'CTRL', x: 77, y: -45, side: 'right' },
      { id: 'THRS', label: 'THRS', x: 77, y: -15, side: 'right' },
      { id: 'DISC', label: 'DISC', x: 77, y: 15, side: 'right' },
      { id: 'VCC', label: 'VCC', x: 77, y: 45, side: 'right' },
    ],
  },
  {
    id: 'C1',
    label: '10uF',
    kind: 'capacitor',
    x: 1002,
    y: 220,
    w: 62,
    h: 76,
    note: 'timing cap',
    pins: [
      { id: 'P', label: '+', x: -31, y: -16, side: 'left' },
      { id: 'N', label: '-', x: 0, y: 38, side: 'bottom' },
    ],
  },
  {
    id: 'U3',
    label: 'LM741',
    kind: 'opamp',
    x: 556,
    y: 306,
    w: 120,
    h: 88,
    note: 'op amp buffer',
    pins: [
      { id: 'NONINV', label: '+', x: -60, y: -22, side: 'left' },
      { id: 'INV', label: '-', x: -60, y: 22, side: 'left' },
      { id: 'OUT', label: 'OUT', x: 60, y: 0, side: 'right' },
      { id: 'V+', label: 'V+', x: 0, y: -44, side: 'top' },
      { id: 'V-', label: 'V-', x: 0, y: 44, side: 'bottom' },
    ],
  },
  {
    id: 'R2',
    label: '22k',
    kind: 'resistor',
    x: 378,
    y: 320,
    w: 98,
    h: 32,
    note: 'feedback',
    pins: [
      { id: 'A', label: 'A', x: -49, y: 0, side: 'left' },
      { id: 'B', label: 'B', x: 49, y: 0, side: 'right' },
    ],
  },
  {
    id: 'J1',
    label: 'OUT',
    kind: 'connector',
    x: 1044,
    y: 104,
    w: 74,
    h: 64,
    note: 'Proteus header',
    pins: [
      { id: 'SIG', label: 'SIG', x: -37, y: 0, side: 'left' },
      { id: 'RET', label: 'RET', x: 0, y: 32, side: 'bottom' },
    ],
  },
  {
    id: 'GND',
    label: 'GND',
    kind: 'ground',
    x: 1030,
    y: 352,
    w: 86,
    h: 44,
    note: 'common return',
    pins: [{ id: 'NODE', label: 'NODE', x: 0, y: -22, side: 'top' }],
  },
];

const boardWires: BoardWire[] = [
  { id: 'wire-a', from: { partId: 'V1', pinId: 'P' }, to: { partId: 'F1', pinId: 'IN' }, speed: 3.2 },
  { id: 'wire-b', from: { partId: 'F1', pinId: 'OUT' }, to: { partId: 'U1', pinId: 'A2' }, speed: 4.1 },
  { id: 'wire-c', from: { partId: 'U1', pinId: 'Y1' }, to: { partId: 'R1', pinId: 'A' }, speed: 3.6 },
  { id: 'wire-d', from: { partId: 'R1', pinId: 'B' }, to: { partId: 'D1', pinId: 'A' }, speed: 2.9 },
  { id: 'wire-e', from: { partId: 'D1', pinId: 'K' }, to: { partId: 'U2', pinId: 'TRIG' }, speed: 3.7 },
  { id: 'wire-f', from: { partId: 'U2', pinId: 'THRS' }, to: { partId: 'C1', pinId: 'P' }, speed: 3.4 },
  { id: 'wire-g', from: { partId: 'U2', pinId: 'OUT' }, to: { partId: 'J1', pinId: 'SIG' }, speed: 4.4 },
  { id: 'wire-h', from: { partId: 'U1', pinId: 'Y2' }, to: { partId: 'U3', pinId: 'NONINV' }, speed: 4.6 },
  { id: 'wire-i', from: { partId: 'R2', pinId: 'B' }, to: { partId: 'U3', pinId: 'INV' }, speed: 3.5 },
  { id: 'wire-j', from: { partId: 'U3', pinId: 'OUT' }, to: { partId: 'U2', pinId: 'CTRL' }, speed: 4.2 },
  { id: 'wire-k', from: { partId: 'C1', pinId: 'N' }, to: { partId: 'GND', pinId: 'NODE' }, speed: 4.8 },
  { id: 'wire-l', from: { partId: 'U2', pinId: 'GND' }, to: { partId: 'GND', pinId: 'NODE' }, speed: 5.0 },
  { id: 'wire-m', from: { partId: 'V1', pinId: 'N' }, to: { partId: 'GND', pinId: 'NODE' }, speed: 5.4 },
];

const assemblyParts = [
  { label: 'U1', className: 'part-u1', delay: '0s', dx: '-110px' },
  { label: 'R1', className: 'part-r1', delay: '.35s', dx: '90px' },
  { label: 'C1', className: 'part-c1', delay: '.7s', dx: '-70px' },
  { label: 'D1', className: 'part-d1', delay: '1s', dx: '120px' },
  { label: 'J1', className: 'part-j1', delay: '1.3s', dx: '-140px' },
  { label: 'GND', className: 'part-gnd', delay: '1.65s', dx: '70px' },
];

export type StaticGenerationState = 'processing' | 'ready' | 'failed';
const STATIC_SUCCESS_WAIT_SECONDS = 25;

function useElapsedCounter(active: boolean, cap = 20) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) return undefined;
    setElapsed(0);
    const id = window.setInterval(() => setElapsed((value) => Math.min(cap, value + 1)), 1000);
    return () => window.clearInterval(id);
  }, [active, cap]);

  return elapsed;
}

export function NonAnimatedRoutingBoard() {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [parts, setParts] = useState(initialBoardParts);
  const [selectedId, setSelectedId] = useState('U2');
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const selectedPart = parts.find((part) => part.id === selectedId) ?? parts[0];

  const toSvgPoint = (event: ReactPointerEvent<SVGSVGElement | SVGGElement>) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };

    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;

    const matrix = svg.getScreenCTM();
    if (!matrix) return { x: 0, y: 0 };

    return point.matrixTransform(matrix.inverse());
  };

  const pinPoint = (partId: string, pinId: string) => {
    const part = parts.find((item) => item.id === partId) ?? parts[0];
    const pin = part.pins.find((item) => item.id === pinId) ?? part.pins[0];
    return { x: part.x + pin.x, y: part.y + pin.y, side: pin.side };
  };

  const wirePath = (wire: BoardWire) => {
    const start = pinPoint(wire.from.partId, wire.from.pinId);
    const end = pinPoint(wire.to.partId, wire.to.pinId);
    const startKick = start.side === 'right' ? 24 : start.side === 'left' ? -24 : 0;
    const endKick = end.side === 'right' ? 24 : end.side === 'left' ? -24 : 0;
    const syKick = start.side === 'bottom' ? 24 : start.side === 'top' ? -24 : 0;
    const eyKick = end.side === 'bottom' ? 24 : end.side === 'top' ? -24 : 0;
    const a = { x: start.x + startKick, y: start.y + syKick };
    const b = { x: end.x + endKick, y: end.y + eyKick };
    const midX = Math.round((a.x + b.x) / 2);

    return `M ${start.x} ${start.y} L ${a.x} ${a.y} L ${midX} ${a.y} L ${midX} ${b.y} L ${b.x} ${b.y} L ${end.x} ${end.y}`;
  };

  const startDrag = (part: BoardPart, event: ReactPointerEvent<SVGGElement>) => {
    event.stopPropagation();
    const point = toSvgPoint(event);
    setSelectedId(part.id);
    setDrag({ id: part.id, dx: point.x - part.x, dy: point.y - part.y });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveDrag = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!drag) return;

    const point = toSvgPoint(event);
    setParts((current) => current.map((part) => {
      if (part.id !== drag.id) return part;
      return {
        ...part,
        x: Math.max(48, Math.min(1072, Math.round(point.x - drag.dx))),
        y: Math.max(54, Math.min(376, Math.round(point.y - drag.dy))),
      };
    }));
  };

  const endDrag = () => setDrag(null);

  const renderPinNodes = (part: BoardPart, selected: boolean) => part.pins.map((pin) => {
    const px = part.x + pin.x;
    const py = part.y + pin.y;
    const lineX = pin.side === 'left' ? -12 : pin.side === 'right' ? 12 : 0;
    const lineY = pin.side === 'top' ? -12 : pin.side === 'bottom' ? 12 : 0;

    return (
      <g key={pin.id}>
        <line className="static-board__pin-line" x1={px} y1={py} x2={px + lineX} y2={py + lineY} />
        <circle className={selected ? 'static-board__pin is-selected' : 'static-board__pin'} cx={px} cy={py} r="4" />
        {selected && (
          <text
            x={px + (pin.side === 'left' ? -10 : pin.side === 'right' ? 10 : 0)}
            y={py + (pin.side === 'top' ? -10 : pin.side === 'bottom' ? 18 : 3)}
            textAnchor={pin.side === 'left' ? 'end' : pin.side === 'right' ? 'start' : 'middle'}
            className="static-board__pin-label"
          >
            {pin.label}
          </text>
        )}
      </g>
    );
  });

  const renderPart = (part: BoardPart) => {
    const selected = part.id === selectedId;
    const x = part.x - part.w / 2;
    const y = part.y - part.h / 2;
    const radius = part.kind === 'ic' || part.kind === 'logic' || part.kind === 'opamp' ? 8 : 4;
    const isPackage = part.kind === 'ic' || part.kind === 'logic' || part.kind === 'opamp';
    const groupClass = `static-board__part ${selected ? 'is-selected' : ''} ${drag?.id === part.id ? 'is-dragging' : ''}`;
    const pinNodes = renderPinNodes(part, selected);

    if (part.kind === 'ground') {
      return (
        <g key={part.id} onPointerDown={(event) => startDrag(part, event)} className={groupClass}>
          <path className="static-board__ground" d={`M${part.x - 34} ${part.y} H${part.x + 34} M${part.x - 23} ${part.y + 11} H${part.x + 23} M${part.x - 12} ${part.y + 22} H${part.x + 12}`} />
          <text x={part.x} y={part.y - 12} textAnchor="middle" className="static-board__label">{part.label}</text>
          {pinNodes}
        </g>
      );
    }

    if (part.kind === 'source') {
      return (
        <g key={part.id} onPointerDown={(event) => startDrag(part, event)} className={groupClass}>
          <circle className="static-board__component" cx={part.x} cy={part.y} r={part.w / 2} />
          <text x={part.x} y={part.y - 2} textAnchor="middle" className="static-board__label">{part.label}</text>
          <text x={part.x} y={part.y + 16} textAnchor="middle" className="static-board__note">{part.id}</text>
          {pinNodes}
        </g>
      );
    }

    return (
      <g key={part.id} onPointerDown={(event) => startDrag(part, event)} className={groupClass}>
        <rect className="static-board__component" x={x} y={y} width={part.w} height={part.h} rx={radius} filter={selected ? 'url(#staticSoftGlow)' : undefined} />
        <text x={part.x} y={part.y + (isPackage ? -3 : 4)} textAnchor="middle" className="static-board__label">{part.label}</text>
        {isPackage && <text x={part.x} y={part.y + 17} textAnchor="middle" className="static-board__note">{part.kind === 'opamp' ? 'OP AMP' : 'DIP PACKAGE'}</text>}
        <text x={part.x} y={y - 8} textAnchor="middle" className="static-board__note">{part.id}</text>
        {pinNodes}
      </g>
    );
  };

  return (
    <section className="static-routing-board" aria-label="Interactive circuit routing board">
      <div className="static-routing-board__bar">
        <span><i /> Live Routing Board</span>
        <strong><i /> Signal Flow Active</strong>
      </div>
      <div className="static-routing-board__canvas">
        <svg
          ref={svgRef}
          viewBox="0 0 1120 430"
          className="static-routing-board__svg"
          role="img"
          aria-label="Interactive circuit board"
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerLeave={endDrag}
        >
          <defs>
            <filter id="staticElectronGlow" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="staticSoftGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#2487ff" floodOpacity="0.5" />
            </filter>
            <linearGradient id="staticTraceGradient" x1="0" x2="1">
              <stop offset="0" stopColor="var(--static-trace-start)" />
              <stop offset="0.52" stopColor="var(--gen-accent)" />
              <stop offset="1" stopColor="var(--static-trace-end)" />
            </linearGradient>
          </defs>
          <rect className="static-board__plate" x="28" y="24" width="1064" height="378" />
          <g className="static-board__aux-wires" aria-hidden="true">
            <path d="M120 50 H1048 V374 H154 V88 H252" />
            <path d="M226 66 H456 V96 H612" />
            <path d="M692 86 H920 V130 H1006" />
            <path d="M164 374 H436 V350 H594" />
            <path d="M760 358 H1006 V330" />
          </g>
          {boardWires.map((wire) => {
            const d = wirePath(wire);
            return <path key={wire.id} id={`static-${wire.id}`} d={d} className="static-board__wire" />;
          })}
          {boardWires.map((wire, index) => (
            <g key={`${wire.id}-electron`}>
              <circle r="4.5" className="static-board__electron" filter="url(#staticElectronGlow)">
                <animateMotion dur={`${wire.speed}s`} begin={`${index * -0.42}s`} repeatCount="indefinite" rotate="auto">
                  <mpath href={`#static-${wire.id}`} />
                </animateMotion>
              </circle>
              <circle r="1.8" className="static-board__electron-core">
                <animateMotion dur={`${wire.speed}s`} begin={`${index * -0.42}s`} repeatCount="indefinite" rotate="auto">
                  <mpath href={`#static-${wire.id}`} />
                </animateMotion>
              </circle>
            </g>
          ))}
          {parts.map(renderPart)}
        </svg>
        <div className="static-routing-board__selection">
          <span>{selectedPart.id}</span>
          <strong>{selectedPart.label}</strong>
          <small>{selectedPart.note}</small>
        </div>
      </div>
    </section>
  );
}

function CircuitAssemblyAnimation() {
  return (
    <div className="static-assembly" aria-hidden="true">
      <div className="static-assembly__scan"><span /></div>
      <div className="static-assembly__perspective">
        <div className="static-assembly__board">
          <svg viewBox="0 0 520 172">
            <path className="static-assembly__trace" d="M65 86 H142 V56 H226 V91 H340 V62 H454" />
            <path className="static-assembly__trace is-secondary" d="M112 112 H206 V126 H282 V102 H405" />
            <path className="static-assembly__trace is-muted" d="M246 42 V126 M330 42 V132" />
            {['M65 86 H142 V56 H226 V91 H340 V62 H454', 'M112 112 H206 V126 H282 V102 H405'].map((path, index) => (
              <circle key={path} r="4" className={index === 0 ? 'static-assembly__dot' : 'static-assembly__dot is-secondary'}>
                <animateMotion dur={index === 0 ? '2.8s' : '3.6s'} repeatCount="indefinite" rotate="auto">
                  <mpath href={`#static-assembly-path-${index}`} />
                </animateMotion>
              </circle>
            ))}
            <path id="static-assembly-path-0" d="M65 86 H142 V56 H226 V91 H340 V62 H454" />
            <path id="static-assembly-path-1" d="M112 112 H206 V126 H282 V102 H405" />
          </svg>
          {assemblyParts.map((part) => (
            <div
              key={part.label}
              className={`static-assembly__part ${part.className}`}
              style={{ '--dx': part.dx, animationDelay: part.delay } as CSSProperties}
            >
              {part.label}
            </div>
          ))}
        </div>
      </div>
      <div className="static-assembly__steps">
        <span />
        <span className="is-active" />
        <span />
      </div>
    </div>
  );
}

export function NonAnimatedWorkspaceStates({
  state,
  errorMessage,
  onBack,
  onDownload,
  downloadHref,
  downloadName,
  targetService,
  stageLabel,
  isDelayed,
  serial,
  onEdit,
}: {
  state: StaticGenerationState;
  errorMessage: string;
  onBack: () => void;
  onDownload: (event: ReactMouseEvent<HTMLAnchorElement>) => void;
  downloadHref: string;
  downloadName: string;
  targetService: 'PR' | 'KC' | 'LT' | 'EA';
  stageLabel: string;
  isDelayed: boolean;
  serial?: string | null;
  onEdit: (serial: string) => void;
}) {
  const elapsed = useElapsedCounter(state === 'processing', STATIC_SUCCESS_WAIT_SECONDS);
  const hasError = state === 'failed';
  const isReady = state === 'ready';
  const progress = hasError || isReady ? 100 : Math.min(100, (elapsed / STATIC_SUCCESS_WAIT_SECONDS) * 100);
  const remaining = Math.max(0, STATIC_SUCCESS_WAIT_SECONDS - elapsed);
  const targetName = targetService === 'KC' ? 'KiCad' : targetService === 'LT' ? 'LTspice' : targetService === 'EA' ? 'EasyEDA Pro' : 'Proteus';
  const exportLabel = targetService === 'KC' ? '.zip' : targetService === 'LT' ? '.asc' : targetService === 'EA' ? '.eprj' : '.pdsprj';
  const processingDetail = isDelayed
    ? 'Generation is taking longer than expected. The executable is still working; please hold on.'
    : stageLabel;
  const statusRows = [
    { label: 'Prompt filter', value: hasError ? 'Blocked' : 'Cleared' },
    { label: 'Instruction boundary', value: 'Locked' },
    { label: 'Quota transaction', value: hasError ? 'Not used' : 'Committed' },
    { label: 'Schema guard', value: hasError ? 'Held' : isReady ? 'Packed' : 'Watching' },
  ];
  const compileSteps = [
    {
      id: 'plan',
      label: 'Planning CircuitIR',
      detail: isReady ? 'Topology resolved' : 'Routing graph prepared',
      className: 'is-complete',
      marker: '✓',
    },
    {
      id: 'validate',
      label: 'Validating topology',
      detail: hasError ? 'Request rejected' : isReady ? 'Validation complete' : 'Auto-resolving nodes',
      className: hasError ? 'is-error' : isReady ? 'is-complete' : 'is-active',
      marker: hasError ? '!' : isReady ? '✓' : '',
    },
    {
      id: 'pack',
      label: `Compiling ${exportLabel}`,
      detail: hasError ? 'Stopped before export' : isReady ? 'Export ready' : 'Packing export schema',
      className: hasError ? 'is-error is-held' : isReady ? 'is-complete' : 'is-pending',
      marker: hasError ? '!' : isReady ? '✓' : '',
    },
  ];
  const exportStages = [
    { label: 'CircuitIR', className: 'is-complete' },
    { label: 'Validate', className: hasError ? 'is-error' : isReady ? 'is-complete' : 'is-active' },
    { label: exportLabel, className: hasError ? 'is-held' : isReady ? 'is-complete' : 'is-pending' },
  ];

  return (
    <section className={`static-workspace-state ${hasError ? 'is-error' : ''} ${isReady ? 'is-ready' : ''}`} aria-live="polite">
      <div className="static-workspace-state__intro">
        <h1>Workspace States</h1>
        <p>
          {hasError
            ? 'The request stopped before export so the error can be corrected immediately.'
            : isReady
              ? `${targetName} project export is ready. Download the generated file to return to the workspace.`
              : processingDetail}
        </p>
      </div>

      <div className="static-workspace-state__grid">
        <div className="static-terminal">
          <div className="static-terminal__bar">
            <span><i /> Live Engineering Terminal</span>
            <strong>SYS. STATE: {hasError ? 'ERROR' : isReady ? 'READY' : isDelayed ? 'EXTENDED RUN' : 'PROCESSING'}</strong>
          </div>

          <div className="static-terminal__body">
            <aside className="static-compile-rail">
              <h2><Activity size={22} /> <span>Compiling<br />Topology</span></h2>
              <ol className="static-compile-flow">
                <li className="static-compile-flow__rail" aria-hidden="true">
                  <span className="static-compile-flow__track" />
                  <span className="static-compile-flow__beam" />
                </li>
                {compileSteps.map((step) => (
                  <li className={step.className} key={step.id}>
                    <span className="static-compile-node" aria-hidden="true">
                      <i />
                      <b>{step.marker}</b>
                    </span>
                    <strong>{step.label}<small>{step.detail}</small></strong>
                  </li>
                ))}
              </ol>
            </aside>

            <div className="static-terminal__main">
              <section className="static-report">
                <h3>{hasError && <Warning2 size={20} />}{hasError ? 'Compilation Error' : isReady ? 'Export Package Ready' : 'Structural Validation Report'}</h3>
                <p>
                  {hasError
                    ? 'The generation service returned an error before the packer sequence completed.'
                    : isReady
                      ? `The generated ${targetName} project file passed packing and is ready for download.`
                      : processingDetail}
                </p>
                {hasError ? (
                  <div className="static-report__error">{errorMessage}</div>
                ) : (
                  <div className="static-report__log">
                    <span>{isReady ? `[EXPORT] ${targetName} ${exportLabel} file packaged successfully.` : `[STAGE] ${processingDetail}`}</span>
                    <span>{isReady ? '[READY] Waiting for user download confirmation...' : `[PACKER] Bundling topology layers into ${targetName} project format...`}</span>
                  </div>
                )}
              </section>

              <section className="static-assembly-card">
                {isReady && (
                  <div className="static-ready-card">
                    <Export size={25} />
                    <h2>{targetName} export ready</h2>
                    <p>Download the generated project file. The workspace will reopen after the download starts.</p>
                    <a href={downloadHref} download={downloadName} onClick={onDownload}>
                      Download generated {exportLabel}
                    </a>
                    {(targetService === 'KC' || targetService === 'LT' || targetService === 'EA') && serial && (
                      <button type="button" onClick={() => onEdit(serial)}>
                        <Edit2 size={17} /> Edit JSON
                      </button>
                    )}
                  </div>
                )}
                <CircuitAssemblyAnimation />
                <h3>{hasError ? 'Compilation Held' : isReady ? 'Download Ready' : 'Compilation Imminent'}</h3>
                <p>
                  {hasError
                    ? 'The project was not sent into the timed packing sequence. Adjust the prompt and retry.'
                    : isReady
                      ? `The generated ${targetName} project is staged as a ${exportLabel} export.`
                      : 'Stand by. Schematic topology is being validated, assembled, disassembled, and packed into standard format.'}
                </p>
                <div className="static-progress">
                  <span>{hasError ? 'Request stopped' : isReady ? `Ready ${exportLabel}` : `Awaiting ${exportLabel}`}</span>
                  <span>{hasError ? '0s' : isReady ? 'ready' : `${remaining}s`}</span>
                  <i style={{ width: `${progress}%` }} />
                </div>
                {hasError && <button type="button" onClick={onBack}>Back to prompt</button>}
              </section>
            </div>
          </div>
        </div>

        <aside className="static-state-aside">
          <section>
            <h2><ShieldTick size={19} /> Prompt Security Layer</h2>
            {statusRows.map((row) => (
              <p key={row.label}><span>{row.label}</span><strong>{row.value}</strong></p>
            ))}
          </section>
          <section className="static-export-card">
            <h2><Export size={19} /> Export Monitor</h2>
            <div className="static-export-stages">
              {exportStages.map((stage) => <span className={stage.className} key={stage.label}>{stage.label}</span>)}
            </div>
            <div className="static-export-monitor" aria-hidden="true">
              <div className="static-export-monitor__rail">
                <span className="static-export-monitor__path" />
                <span className="static-export-monitor__packet packet-a" />
                <span className="static-export-monitor__packet packet-b" />
                <span className="static-export-monitor__packet packet-c" />
                <span className="static-export-monitor__gate gate-a" />
                <span className="static-export-monitor__gate gate-b" />
                <span className="static-export-monitor__gate gate-c" />
              </div>
              <div className="static-export-monitor__readout">
                <span>{hasError ? 'Error held' : isReady ? 'Ready' : 'Processing'}</span>
                <strong>{hasError ? 'Validation stopped' : isReady ? `${targetName} export staged` : `${remaining}s remaining`}</strong>
              </div>
            </div>
          </section>
          <section>
            <h2><DocumentText size={19} /> Runtime Notes</h2>
            <ul>
              <li>Provider request is isolated from interface state and staged only after validation checks.</li>
              <li>Compiler output stays locked to the {targetName} project export path.</li>
            </ul>
          </section>
        </aside>
      </div>
    </section>
  );
}
