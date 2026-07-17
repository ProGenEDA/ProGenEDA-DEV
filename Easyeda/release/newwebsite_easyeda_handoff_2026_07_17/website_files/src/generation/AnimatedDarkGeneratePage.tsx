import {
  Activity,
  Add,
  ArrowUp,
  ArrowDown2,
  CloseCircle,
  DocumentDownload,
  DocumentUpload,
  Edit2,
  Element4,
  Flash,
  Forbidden2,
  Link21,
  MagicStar,
  MoreCircle,
  Notification,
  SearchNormal1,
  ShieldTick,
  SliderHorizontal,
} from 'iconsax-react';
import {
  FormEvent,
  ClipboardEvent as ReactClipboardEvent,
  DragEvent as ReactDragEvent,
  forwardRef,
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent as ReactMouseEvent,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { AuthSession } from '../auth/authProvider';
import { PageMeta } from '../contentPages';
import {
  NonAnimatedRoutingBoard,
  NonAnimatedWorkspaceStates,
  StaticGenerationState,
} from './NonAnimatedDarkWorkspace';
import {
  GenerationSidebar,
} from './GenerationSidebar';
import {
  GenerationMode,
  readStoredGenerationMode,
  writeStoredGenerationMode,
} from './generationModeStorage';
import { SidebarRevealZone } from './SidebarRevealZone';
import { useSidebarAutoHide } from './sidebarAutoHide';
import { KiCadJsonLab } from './KiCadJsonLab';
import {
  generateCircuit,
  generateWithExecutableProgress,
  generateJsonBatch,
  DirectJsonBatchItem,
  GenerationTargetService,
} from '../backend/generationClient';
import { apiBaseUrl, apiFetch } from '../backend/apiClient';
import { ParticlesSwarm } from '../vendor/tesseract/src/ParticlesSwarm.js';
import directorSettings from '../vendor/tesseract/src/director-settings.json';

const FALLBACK_DOWNLOAD_FILE = '/downloads/CONTROL_original_source.pdsprj';
const FALLBACK_DOWNLOAD_NAME = 'CONTROL_original_source.pdsprj';
const MOBILE_SUCCESS_WAIT_MS = 1000;
const NON_ANIMATED_SUCCESS_WAIT_MS = 25_000;
const ANIMATED_SUCCESS_WAIT_MS = 34_000;
const NON_ANIMATED_TIMEOUT_MS = NON_ANIMATED_SUCCESS_WAIT_MS * 2;
const ANIMATED_TIMEOUT_MS = ANIMATED_SUCCESS_WAIT_MS * 2;
const NON_ANIMATED_FAILURE_MIN_WAIT_MS = 10_000;
const FAILURE_TRIGGER_DELAY_MS = 1100;
const FAILURE_POLL_MS = 140;
const TEMP_SESSION_KEY = 'progeneda.tempSession';

type GenerationStatus = 'idle' | 'generating' | 'failing' | 'failed' | 'ready' | 'reversing';
type GenerationStage = string;
type DownloadFile = {
  href: string;
  name: string;
  objectUrl: boolean;
  serial?: string | null;
};

type GenerationInputMode = 'Balanced' | 'Complex' | 'Fast' | 'JSON';
type CircuitMultiplicity = 'Solo' | 'Multiple';
type JsonAttachment = DirectJsonBatchItem & { id: string };
type ExampleCircuit = {
  id: string;
  title: string;
  service: GenerationTargetService;
};
type ExampleCircuitLibrary = {
  service: GenerationTargetService;
  total: number;
  featured: ExampleCircuit[];
  remaining: ExampleCircuit[];
};
type GenerationRequestWatch = {
  runId: number;
  startedAt: number;
  resolved: boolean;
  timedOut: boolean;
  controller: AbortController;
};

const MAX_JSON_ATTACHMENTS = 50;

const TARGET_DETAILS: Record<GenerationTargetService, {
  label: string;
  projectLabel: string;
  extension: string;
  editable: boolean;
}> = {
  PR: {
    label: 'Proteus',
    projectLabel: 'Proteus circuit file',
    extension: '.pdsprj',
    editable: false,
  },
  KC: {
    label: 'KiCad',
    projectLabel: 'KiCad project archive',
    extension: '.zip',
    editable: true,
  },
  LT: {
    label: 'LTspice',
    projectLabel: 'LTspice .asc schematic',
    extension: '.asc',
    editable: true,
  },
  EA: {
    label: 'EasyEDA Pro',
    projectLabel: 'EasyEDA Pro native project',
    extension: '.eprj',
    editable: true,
  },
};

const EXECUTABLE_STAGE_LABELS: Record<string, string> = {
  select_verified_example: 'Retrieving verified LTspice example',
  canonicalize_input: 'Validating canonical CircuitIR',
  resolve_donor_catalogue: 'Resolving LTspice donor catalogue',
  place_stock_symbols: 'Placing LTspice stock symbols',
  beautify_layout: 'Beautifying schematic layout',
  route_physical_wires: 'Routing physical wires',
  write_native_asc: 'Writing native .asc schematic',
  validate_native_asc: 'Validating native .asc schematic',
  package_artifacts: 'Packing verified .asc artifact',
  fix_and_validate_input: 'Repairing and validating EasyEDA CircuitIR',
  normalize_values: 'Normalizing component references and values',
  place_components: 'Placing donor-native EasyEDA symbols',
  route_schematic: 'Routing compact wires and native terminals',
  write_native_eprj: 'Writing native .eprj schematic and PCB records',
  validate_native_eprj: 'Validating netlist, geometry, source records, and PCB',
};

function targetDetails(service: GenerationTargetService) {
  return TARGET_DETAILS[service];
}

function initialTargetService(): GenerationTargetService {
  if (typeof window === 'undefined') return 'PR';
  const requested = new URLSearchParams(window.location.search).get('target')?.trim().toUpperCase();
  return requested === 'KC' || requested === 'LT' || requested === 'EA' || requested === 'PR' ? requested : 'PR';
}

function hasAdvancedGenerationAccess(session: AuthSession | null) {
  return session?.role === 'admin'
    || session?.role === 'demo'
    || session?.email.endsWith('@progeneda.local') === true;
}

function parseJsonAttachments(text: string, sourceName: string): JsonAttachment[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`${sourceName} is not valid JSON.`);
  }

  const values = Array.isArray(parsed) ? parsed : [parsed];
  if (values.length === 0) throw new Error(`${sourceName} contains no circuits.`);

  return values.map((value, index) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new Error(`${sourceName} must contain JSON objects only.`);
    }
    const project = (value as Record<string, unknown>).project;
    const projectName = project && typeof project === 'object'
      ? String((project as Record<string, unknown>).title || (project as Record<string, unknown>).name || '')
      : '';
    const name = values.length > 1 ? `${sourceName} #${index + 1}` : sourceName;
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}-${index}`,
      name,
      prompt: projectName || name,
      mainJson: value as Record<string, unknown>,
    };
  });
}

type SharedCircuit = {
  serial: string;
  title: string;
  description: string;
  service: string;
  status: string;
  canDownload: boolean;
};

const FALLBACK_DOWNLOAD: DownloadFile = {
  href: FALLBACK_DOWNLOAD_FILE,
  name: FALLBACK_DOWNLOAD_NAME,
  objectUrl: false,
};

type StageHandle = {
  playForward: () => boolean;
  failToRed: () => boolean;
  reverseToBlue: () => boolean;
  isForwardComplete: () => boolean;
  isSettledRed: () => boolean;
  isSettledBlue: () => boolean;
};

function readStoredSession(): AuthSession | null {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    const rawSession = storage.getItem(TEMP_SESSION_KEY);

    if (!rawSession) continue;

    try {
      return JSON.parse(rawSession) as AuthSession;
    } catch {
      storage.removeItem(TEMP_SESSION_KEY);
    }
  }

  return null;
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches);

  useEffect(() => {
    const query = window.matchMedia('(max-width: 760px)');
    const onChange = () => setIsMobile(query.matches);

    onChange();
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  return isMobile;
}

const TesseractStage = forwardRef<StageHandle, { disabled: boolean }>(function TesseractStage(
  { disabled },
  ref,
) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const swarmRef = useRef<ParticlesSwarm | null>(null);

  useEffect(() => {
    if (disabled || !stageRef.current) return undefined;

    const swarm = new ParticlesSwarm(stageRef.current, 14000, { speedMult: 1.9 });
    swarm.loadDirectorSettings(directorSettings);
    swarm.colorMode = 'blue-base';
    window.removeEventListener('keydown', swarm.onKeyDown);
    swarmRef.current = swarm;

    return () => {
      swarm.dispose();
      swarmRef.current = null;
    };
  }, [disabled]);

  useImperativeHandle(ref, () => ({
    playForward() {
      const swarm = swarmRef.current;
      if (!swarm || swarm.timeline || (swarm.director.active && swarm.director.playing)) return false;
      if (!swarm.director.active && swarm.currentStageIndex !== 0) return false;

      swarm.startForwardTimeline();
      return true;
    },
    failToRed() {
      const swarm = swarmRef.current;
      if (!swarm?.timeline) return false;

      swarm.startYBranch();
      return true;
    },
    reverseToBlue() {
      const swarm = swarmRef.current;
      if (!swarm) return false;

      const lastStageIndex = swarm.fullStageSequence.length - 1;
      const directorReady = swarm.director.active && swarm.director.timeMs >= swarm.director.totalDurationMs;
      const timelineReady = !swarm.director.active && !swarm.timeline && swarm.currentStageIndex === lastStageIndex;

      if (!directorReady && !timelineReady) return false;

      swarm.startReverseTimeline();
      return true;
    },
    isForwardComplete() {
      const swarm = swarmRef.current;
      if (!swarm) return false;

      const lastStageIndex = swarm.fullStageSequence.length - 1;

      if (swarm.director.active) {
        return swarm.director.timeMs >= swarm.director.totalDurationMs
          && swarm.currentStageIndex === lastStageIndex;
      }

      return !swarm.timeline && swarm.currentStageIndex === lastStageIndex;
    },
    isSettledRed() {
      const swarm = swarmRef.current;
      return Boolean(
        swarm
        && !swarm.timeline
        && !swarm.director.active
        && swarm.currentStageIndex === 0
        && swarm.colorMode === 'red-base',
      );
    },
    isSettledBlue() {
      const swarm = swarmRef.current;
      return Boolean(
        swarm
        && !swarm.timeline
        && !swarm.director.active
        && swarm.currentStageIndex === 0
        && swarm.colorMode === 'blue-base',
      );
    },
  }));

  return <div className="tesseract-stage" ref={stageRef} aria-hidden="true" />;
});

function StatusPill({
  status,
  errorMessage,
  stage,
  isDelayed,
}: {
  status: GenerationStatus;
  errorMessage: string;
  stage: GenerationStage;
  isDelayed: boolean;
}) {
  const isFailed = status === 'failed';
  const isFailing = status === 'failing';
  const statusText = isFailed
    ? errorMessage || 'Generation failed.'
    : status === 'generating' || isFailing
      ? isDelayed
        ? 'Generation is taking longer than expected. Please hold on.'
        : stage
      : status === 'reversing'
        ? 'Returning to interactive mode...'
      : status === 'ready'
        ? 'Circuit ready for download'
        : 'All systems operational';

  return (
    <div className={`generate-topbar ${isFailed ? 'is-error' : ''} ${isFailing ? 'is-warning-pulse' : ''} ${isDelayed ? 'is-delayed' : ''}`} aria-label="Generation status">
      <span>
        <i />
        {statusText}
      </span>
      <button type="button" aria-label="Notifications"><Notification size={20} /></button>
    </div>
  );
}

function PromptComposer({
  prompt,
  status,
  validation,
  session,
  targetService,
  inputMode,
  multiplicity,
  attachments,
  isJsonDropActive,
  onPromptChange,
  onTargetServiceChange,
  onInputModeChange,
  onMultiplicityChange,
  onAddJsonText,
  onAddJsonFiles,
  onRemoveAttachment,
  onOpenSerialLookup,
  onSubmit,
}: {
  prompt: string;
  status: GenerationStatus;
  validation: string;
  session: AuthSession | null;
  targetService: GenerationTargetService;
  inputMode: GenerationInputMode;
  multiplicity: CircuitMultiplicity;
  attachments: JsonAttachment[];
  isJsonDropActive: boolean;
  onPromptChange: (value: string) => void;
  onTargetServiceChange: (value: GenerationTargetService) => void;
  onInputModeChange: (value: GenerationInputMode) => void;
  onMultiplicityChange: (value: CircuitMultiplicity) => void;
  onAddJsonText: (text: string, sourceName: string) => boolean;
  onAddJsonFiles: (files: FileList) => void;
  onRemoveAttachment: (id: string) => void;
  onOpenSerialLookup: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const isBusy = status === 'generating' || status === 'failing' || status === 'ready' || status === 'reversing';
  const promptInputRef = useRef<HTMLTextAreaElement | null>(null);
  const jsonFileInputRef = useRef<HTMLInputElement | null>(null);
  const [openMenu, setOpenMenu] = useState<'eda' | 'multiplicity' | 'mode' | null>(null);
  const [isPlusMenuOpen, setIsPlusMenuOpen] = useState(false);
  const canUseAdvanced = hasAdvancedGenerationAccess(session);
  const isMultipleJson = canUseAdvanced && multiplicity === 'Multiple' && inputMode === 'JSON';
  const canAttachJson = canUseAdvanced && inputMode === 'JSON';
  const generationModes: GenerationInputMode[] = ['Balanced', 'Complex', 'Fast', 'JSON'];
  const targetLabel = targetDetails(targetService).label;
  const hasGenerationInput = Boolean(prompt.trim() || attachments.length);

  useEffect(() => {
    const promptInput = promptInputRef.current;
    if (!promptInput) return;

    promptInput.style.height = 'auto';
    promptInput.style.height = `${Math.min(promptInput.scrollHeight, 132)}px`;
  }, [prompt]);

  return (
    <form
      className={`prompt-composer ${attachments.length ? 'has-json-attachments' : ''} ${isJsonDropActive ? 'is-dragging-json' : ''}`}
      onSubmit={onSubmit}
    >
      {attachments.length > 0 && (
        <div className="composer-json-attachments" aria-label={`${attachments.length} attached JSON circuits`}>
          {attachments.map((attachment, index) => (
            <span key={attachment.id} title={attachment.name}>
              <DocumentDownload size={15} />
              <b>{index + 1}</b>
              {attachment.name}
              <button type="button" aria-label={`Remove ${attachment.name}`} onClick={() => onRemoveAttachment(attachment.id)}>
                <CloseCircle size={15} />
              </button>
            </span>
          ))}
          <small>{attachments.length}/{MAX_JSON_ATTACHMENTS}</small>
        </div>
      )}
      <input
        ref={jsonFileInputRef}
        className="sr-only"
        type="file"
        accept="application/json,.json"
        multiple
        onChange={(event) => {
          if (event.currentTarget.files?.length) onAddJsonFiles(event.currentTarget.files);
          event.currentTarget.value = '';
        }}
      />

      {canAttachJson && isPlusMenuOpen && (
        <div className="composer-plus-menu" role="menu" aria-label="JSON import options">
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setIsPlusMenuOpen(false);
              jsonFileInputRef.current?.click();
            }}
          >
            <DocumentUpload size={18} /> Add JSON file
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setIsPlusMenuOpen(false);
              onOpenSerialLookup();
            }}
          >
            <Link21 size={18} /> Download from key
          </button>
        </div>
      )}
      <button
        className="composer-plus"
        type="button"
        aria-label={canAttachJson ? 'Open JSON import options' : 'Import shared circuit serial'}
        aria-expanded={canAttachJson ? isPlusMenuOpen : undefined}
        disabled={isBusy}
        onClick={() => {
          if (canAttachJson) {
            setIsPlusMenuOpen((current) => !current);
            return;
          }
          onOpenSerialLookup();
        }}
      >
        <Add size={28} />
      </button>

      <label>
        <span className="sr-only">Circuit prompt</span>
        <textarea
          ref={promptInputRef}
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          onPaste={(event: ReactClipboardEvent<HTMLTextAreaElement>) => {
            if (!isMultipleJson) return;
            const pastedText = event.clipboardData.getData('text');
            if (!pastedText.trim()) return;
            event.preventDefault();
            onAddJsonText(pastedText, 'Pasted JSON');
          }}
          onKeyDown={(event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
            if (!isMultipleJson || !event.ctrlKey || event.key.toLowerCase() !== 'g') return;
            event.preventDefault();
            if (prompt.trim() && onAddJsonText(prompt, 'Typed JSON')) onPromptChange('');
          }}
          onWheel={(event) => {
            const textarea = event.currentTarget;
            const canScroll = textarea.scrollHeight > textarea.clientHeight + 1;

            if (!canScroll) return;

            const isAtTop = textarea.scrollTop <= 0;
            const isAtBottom = textarea.scrollTop + textarea.clientHeight >= textarea.scrollHeight - 1;
            const shouldScrollInside = (event.deltaY < 0 && !isAtTop) || (event.deltaY > 0 && !isAtBottom);

            if (shouldScrollInside) {
              event.preventDefault();
              event.stopPropagation();
              textarea.scrollTop += event.deltaY;
            }
          }}
          placeholder={inputMode === 'JSON'
            ? (multiplicity === 'Multiple' ? 'Paste JSON, press Ctrl+G, or drop up to 50 .json files...' : 'Paste one canonical circuit JSON object...')
            : `Describe your ${targetLabel} circuit in natural language...`}
          disabled={isBusy}
          rows={1}
        />
      </label>

      <div className="composer-controls">
        <div className="composer-select">
          <button
            className="composer-select__trigger"
            type="button"
            aria-haspopup="menu"
            aria-expanded={openMenu === 'eda'}
            onClick={() => {
              setOpenMenu((current) => current === 'eda' ? null : 'eda');
            }}
          >
            {targetLabel} <ArrowDown2 size={18} />
          </button>

          {openMenu === 'eda' && (
            <div className="composer-menu" role="menu">
              {([['PR', 'Proteus'], ['KC', 'KiCad'], ['LT', 'LTspice'], ['EA', 'EasyEDA Pro']] as const).map(([service, label]) => (
                <button
                  className={`composer-option ${targetService === service ? 'is-selected' : ''}`}
                  type="button"
                  role="menuitemradio"
                  aria-checked={targetService === service}
                  key={service}
                  onClick={() => {
                    onTargetServiceChange(service);
                    setOpenMenu(null);
                  }}
                >
                  {label}
                </button>
              ))}
              {['PSpice', 'Altium'].map((target) => (
                <button className="composer-option is-admin-locked" type="button" role="menuitem" aria-disabled="true" key={target}>
                  <span>{target}</span><small>Coming later</small>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="composer-select">
          <button
            className="composer-select__trigger"
            type="button"
            aria-haspopup="menu"
            aria-expanded={openMenu === 'multiplicity'}
            onClick={() => {
              setOpenMenu((current) => current === 'multiplicity' ? null : 'multiplicity');
            }}
          >
            {multiplicity} <ArrowDown2 size={18} />
          </button>

          {openMenu === 'multiplicity' && (
            <div className="composer-menu" role="menu">
              {(['Solo', 'Multiple'] as CircuitMultiplicity[]).map((mode) => {
                const isLocked = mode === 'Multiple' && !canUseAdvanced;
                return (
                <button
                  className={`composer-option ${multiplicity === mode ? 'is-selected' : ''} ${isLocked ? 'is-admin-locked' : ''}`}
                  type="button"
                  role="menuitemradio"
                  aria-checked={multiplicity === mode}
                  aria-disabled={isLocked}
                  key={mode}
                  onClick={() => {
                    if (isLocked) return;
                    onMultiplicityChange(mode);
                    setOpenMenu(null);
                  }}
                >
                  {mode}
                  {isLocked && <small>Admin or Demo only</small>}
                </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="composer-select">
          <button
            className="composer-select__trigger"
            type="button"
            aria-haspopup="menu"
            aria-expanded={openMenu === 'mode'}
            onClick={() => setOpenMenu((current) => current === 'mode' ? null : 'mode')}
          >
            {inputMode} <ArrowDown2 size={18} />
          </button>

          {openMenu === 'mode' && (
            <div className="composer-menu" role="menu">
              {generationModes.map((mode) => {
                const isLocked = mode === 'JSON' && !canUseAdvanced;
                return (
                  <button
                    className={`composer-option ${inputMode === mode ? 'is-selected' : ''} ${isLocked ? 'is-admin-locked' : ''}`}
                    type="button"
                    role="menuitemradio"
                    aria-checked={inputMode === mode}
                    aria-disabled={isLocked}
                    key={mode}
                    onClick={() => {
                      if (isLocked) return;
                      onInputModeChange(mode);
                      setOpenMenu(null);
                    }}
                  >
                    {mode}
                    {isLocked && <small>Admin or Demo only</small>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <button
        className={`composer-submit ${hasGenerationInput ? 'is-ready' : 'is-empty'}`}
        type="submit"
        disabled={isBusy}
        aria-label="Generate circuit"
      >
        <ArrowUp className="composer-submit__arrow" size={30} />
        <Forbidden2 className="composer-submit__blocked" size={27} />
      </button>

      {validation && <p className="composer-validation">{validation}</p>}
    </form>
  );
}

function DownloadModal({
  href,
  fileName,
  targetService,
  serial,
  onDownload,
  onEdit,
}: {
  href: string;
  fileName: string;
  targetService: GenerationTargetService;
  serial?: string | null;
  onDownload: (event: ReactMouseEvent<HTMLAnchorElement>) => void;
  onEdit: (serial: string) => void;
}) {
  return (
    <div className="download-overlay">
      <div className="download-popover" role="dialog" aria-modal="true" aria-labelledby="download-title">
        <span><ShieldTick size={22} /> Generation complete</span>
        <h2 id="download-title">{fileName.replace(/\.(pdsprj|zip)$/i, '')}</h2>
        <p>Your {targetDetails(targetService).projectLabel} is ready.</p>
        <div className="download-actions">
          <a href={href} download={fileName} onClick={onDownload}>
            <DocumentDownload size={18} />
            Download
          </a>
          <button
            type="button"
            disabled={!targetDetails(targetService).editable || !serial}
            title={targetDetails(targetService).editable && serial
              ? `Open ${targetDetails(targetService).label} JSON Lab`
              : 'Proteus JSON editing waits for the upgraded runtime.'}
            onClick={() => serial && onEdit(serial)}
          >
            <Edit2 size={18} />
            {targetDetails(targetService).editable && serial ? 'Edit JSON' : 'Editor pending'}
          </button>
        </div>
      </div>
    </div>
  );
}

function SharedSerialDialog({ onClose }: { onClose: () => void }) {
  const [serialInput, setSerialInput] = useState('');
  const [lookupStatus, setLookupStatus] = useState<'idle' | 'loading' | 'ready'>('idle');
  const [lookupError, setLookupError] = useState('');
  const [circuit, setCircuit] = useState<SharedCircuit | null>(null);
  const normalizedSerial = serialInput.trim();
  const downloadHref = circuit
    ? `${apiBaseUrl()}/api/download/export/${encodeURIComponent(circuit.serial)}?source=shared_serial`
    : '';

  const onLookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLookupError('');

    if (!normalizedSerial) {
      setLookupError('Enter a circuit serial first.');
      return;
    }

    setLookupStatus('loading');
    setCircuit(null);

    try {
      const response = await apiFetch(`/api/circuits/${encodeURIComponent(normalizedSerial)}`);
      if (!response.ok) {
        throw new Error(response.status === 404 ? 'No downloadable circuit was found for that serial.' : 'Serial lookup failed.');
      }

      const payload = await response.json() as SharedCircuit;
      if (!payload.canDownload) {
        throw new Error('This circuit is not ready for shared download yet.');
      }

      setCircuit(payload);
      setLookupStatus('ready');
    } catch (error) {
      setLookupStatus('idle');
      setLookupError(error instanceof Error ? error.message : 'Serial lookup failed.');
    }
  };

  return (
    <div className="download-overlay serial-share-overlay">
      <section className="download-popover serial-share-card" role="dialog" aria-modal="true" aria-labelledby="serial-share-title">
        <button className="serial-share-close" type="button" aria-label="Close serial import" onClick={onClose}>
          <CloseCircle size={21} />
        </button>

        <span><Link21 size={22} /> Shared circuit serial</span>
        <h2 id="serial-share-title">Open shared circuit</h2>
        <p>Paste a ProGenEDA serial to fetch its downloadable EDA export.</p>

        <form className="serial-share-form" onSubmit={onLookup}>
          <label>
            <SearchNormal1 size={19} />
            <input
              value={serialInput}
              onChange={(event) => {
                setSerialInput(event.target.value);
                setLookupError('');
                setCircuit(null);
                setLookupStatus('idle');
              }}
              placeholder="PR-A-..., KC-A-..., or LT-A-..."
              autoFocus
            />
          </label>
          <button type="submit" disabled={lookupStatus === 'loading'}>
            <Link21 size={17} />
            {lookupStatus === 'loading' ? 'Checking...' : 'Open key'}
          </button>
        </form>

        {lookupError && <p className="serial-share-error">{lookupError}</p>}

        {circuit && (
          <div className="serial-share-result">
            <strong>{circuit.title}</strong>
            <small>{circuit.service} · {circuit.serial}</small>
            <div className="download-actions">
              <a
                href={downloadHref}
                download={circuit.service === 'KiCad'
                  ? 'PROGEN_KICAD_PROJECT.zip'
                  : circuit.service === 'LTspice'
                    ? `${circuit.serial}.asc`
                    : circuit.service === 'EasyEDA Pro'
                      ? `${circuit.serial}.eprj`
                    : `${circuit.serial}.pdsprj`}
              >
                <DocumentDownload size={18} />
                Download
              </a>
              <button type="button" disabled>
                <Edit2 size={18} />
                Edit
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export function AnimatedDarkGeneratePage() {
  const isMobile = useIsMobile();
  const stageRef = useRef<StageHandle | null>(null);
  const timersRef = useRef<number[]>([]);
  const exampleSubmitTimerRef = useRef<number | null>(null);
  const runIdRef = useRef(0);
  const downloadStartedRef = useRef(false);
  const pendingErrorRef = useRef('');
  const downloadFileRef = useRef<DownloadFile>(FALLBACK_DOWNLOAD);
  const requestWatchRef = useRef<GenerationRequestWatch | null>(null);
  const [session] = useState(() => readStoredSession());
  const [generationMode, setGenerationMode] = useState(() => readStoredGenerationMode());
  const [prompt, setPrompt] = useState('');
  const [targetService, setTargetService] = useState<GenerationTargetService>(initialTargetService);
  const [inputMode, setInputMode] = useState<GenerationInputMode>('Balanced');
  const [multiplicity, setMultiplicity] = useState<CircuitMultiplicity>('Solo');
  const [jsonAttachments, setJsonAttachments] = useState<JsonAttachment[]>([]);
  const [exampleLibrary, setExampleLibrary] = useState<ExampleCircuitLibrary | null>(null);
  const [isExampleMenuOpen, setIsExampleMenuOpen] = useState(false);
  const [exampleSearch, setExampleSearch] = useState('');
  const [status, setStatus] = useState<GenerationStatus>('idle');
  const [generationStage, setGenerationStage] = useState<GenerationStage>('Preparing generation request');
  const [isGenerationDelayed, setIsGenerationDelayed] = useState(false);
  const [validation, setValidation] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [showDownload, setShowDownload] = useState(false);
  const [showSerialLookup, setShowSerialLookup] = useState(false);
  const [editorSerial, setEditorSerial] = useState<string | null>(null);
  const [isPageDraggingJson, setIsPageDraggingJson] = useState(false);
  const [downloadFile, setDownloadFileState] = useState<DownloadFile>(FALLBACK_DOWNLOAD);
  const [visualTone, setVisualTone] = useState<'blue' | 'red'>('blue');
  const motionMode = generationMode.motion;
  const themeMode = generationMode.theme;
  const isAnimatedDark = motionMode === 'animated';
  const isNonAnimatedDark = motionMode === 'nonanimated';
  const isAnimatedCinematic = isAnimatedDark && (
    status === 'generating'
    || status === 'failing'
    || status === 'ready'
    || status === 'reversing'
  );
  const isStaticWorkspace = isNonAnimatedDark && (
    status === 'generating'
    || status === 'failed'
    || status === 'ready'
  );
  const staticWorkspaceState: StaticGenerationState = status === 'failed'
    ? 'failed'
    : status === 'ready'
      ? 'ready'
      : 'processing';
  const isRedMode = visualTone === 'red' || status === 'failed';
  const sidebarAutoHide = useSidebarAutoHide({ disabled: isAnimatedCinematic || isMobile });
  const canAcceptPageJsonDrop = hasAdvancedGenerationAccess(session)
    && status !== 'generating'
    && status !== 'failing'
    && status !== 'ready'
    && status !== 'reversing';

  useEffect(() => {
    let active = true;
    setIsExampleMenuOpen(false);
    setExampleSearch('');

    if (targetService !== 'LT' && targetService !== 'EA') {
      setExampleLibrary(null);
      return () => { active = false; };
    }

    apiFetch(`/api/example-circuits?service=${targetService}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`${targetDetails(targetService).label} examples are unavailable.`);
        return response.json() as Promise<ExampleCircuitLibrary>;
      })
      .then((library) => {
        if (active) setExampleLibrary(library);
      })
      .catch(() => {
        if (active) setExampleLibrary(null);
      });

    return () => { active = false; };
  }, [targetService]);

  const clearTimers = () => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current = [];
  };

  const clearExampleAutoSubmit = () => {
    if (exampleSubmitTimerRef.current !== null) {
      window.clearTimeout(exampleSubmitTimerRef.current);
      exampleSubmitTimerRef.current = null;
    }
  };

  const abortActiveGenerationRequest = () => {
    const activeRequest = requestWatchRef.current;
    if (activeRequest && !activeRequest.resolved) activeRequest.controller.abort();
    requestWatchRef.current = null;
  };

  const isGenerationRequestPending = (runId: number) => {
    const activeRequest = requestWatchRef.current;
    return Boolean(activeRequest
      && activeRequest.runId === runId
      && !activeRequest.resolved
      && !activeRequest.timedOut
      && isActiveRun(runId));
  };

  const generationStagesForTarget = (): GenerationStage[] => (
    targetService === 'KC'
      ? [
          'Validating canonical CircuitIR',
          'Resolving component and pin contracts',
          'Compiling schematic topology',
          'Running deterministic export validation',
          'Packing project artifact',
        ]
      : targetService === 'LT'
        ? [
            'Validating canonical CircuitIR',
            'Resolving LTspice donor catalogue',
            'Placing LTspice stock symbols',
            'Beautifying schematic layout',
            'Routing physical wires',
            'Writing native .asc schematic',
            'Validating native .asc schematic',
            'Packing verified .asc artifact',
          ]
      : targetService === 'EA'
        ? [
            'Repairing and validating EasyEDA CircuitIR',
            'Resolving exact donor-native components',
            'Placing schematic components',
            'Routing compact wires and native terminals',
            'Writing native .eprj records',
            'Validating netlist, geometry, source records, and PCB',
            'Packing project and audit artifacts',
          ]
      : [
          'Preparing generation request',
          'Resolving component and pin contracts',
          'Compiling schematic topology',
          'Running deterministic export validation',
          'Packing project artifact',
        ]
  );

  const animationBudgetSecondsForRun = () => (
    (isAnimatedDark && !isMobile ? ANIMATED_SUCCESS_WAIT_MS : NON_ANIMATED_SUCCESS_WAIT_MS) / 1000
  );

  const markGenerationRequestResolved = (runId: number) => {
    const activeRequest = requestWatchRef.current;
    if (!activeRequest || activeRequest.runId !== runId) return;
    activeRequest.resolved = true;
    setIsGenerationDelayed(false);
  };

  const startGenerationWatchdog = (runId: number) => {
    const controller = new AbortController();
    const expectedWait = isAnimatedDark && !isMobile
      ? ANIMATED_SUCCESS_WAIT_MS
      : NON_ANIMATED_SUCCESS_WAIT_MS;
    const timeoutWait = isAnimatedDark && !isMobile
      ? ANIMATED_TIMEOUT_MS
      : NON_ANIMATED_TIMEOUT_MS;
    const stages = generationStagesForTarget();
    requestWatchRef.current = {
      runId,
      startedAt: Date.now(),
      resolved: false,
      timedOut: false,
      controller,
    };
    setGenerationStage(stages[0]);
    setIsGenerationDelayed(false);

    // LTspice and EasyEDA emit their own donor-native stage events. Keep
    // the older estimated progression only for targets that cannot report a
    // real compiler stage yet.
    if (targetService !== 'LT' && targetService !== 'EA') {
      stages.slice(1).forEach((stage, index) => {
        const delay = Math.round(expectedWait * ((index + 1) / (stages.length + 1)));
        addTimer(() => {
          if (isGenerationRequestPending(runId)) setGenerationStage(stage);
        }, delay);
      });
    }

    addTimer(() => {
      if (!isGenerationRequestPending(runId)) return;
      setGenerationStage('Finalizing download');
      setIsGenerationDelayed(true);
    }, expectedWait);

    addTimer(() => {
      const activeRequest = requestWatchRef.current;
      if (!activeRequest || activeRequest.runId !== runId || activeRequest.resolved || activeRequest.timedOut || !isActiveRun(runId)) return;
      activeRequest.timedOut = true;
      activeRequest.controller.abort();
      triggerGenerationFailure('Generation took longer than allowed time. Please try a simpler circuit.', runId);
    }, timeoutWait);

    return controller.signal;
  };

  const setDownloadFile = (nextFile: DownloadFile) => {
    const currentFile = downloadFileRef.current;

    if (currentFile.objectUrl && currentFile.href !== nextFile.href) {
      window.URL.revokeObjectURL(currentFile.href);
    }

    downloadFileRef.current = nextFile;
    setDownloadFileState(nextFile);
  };

  const resetDownloadFile = () => setDownloadFile(FALLBACK_DOWNLOAD);

  const jsonItemsForRun = (normalizedPrompt: string) => {
    const items = [...jsonAttachments];
    if (normalizedPrompt) items.push(...parseJsonAttachments(normalizedPrompt, 'Typed JSON'));
    if (items.length === 0) throw new Error('Attach or paste at least one JSON circuit.');
    if (items.length > MAX_JSON_ATTACHMENTS) throw new Error(`A batch can contain at most ${MAX_JSON_ATTACHMENTS} circuits.`);
    return items;
  };

  const requestGeneratedDownload = async (
    normalizedPrompt: string,
    signal: AbortSignal | undefined,
    runId: number,
  ): Promise<DownloadFile> => {
    if (inputMode !== 'JSON' && normalizedPrompt.toLowerCase().includes('fail')) {
      throw new Error(`Placeholder generation error: ${targetDetails(targetService).label} output validation failed.`);
    }

    // A single JSON circuit can arrive as an attachment without any typed
    // prompt. Prefer that deterministic attachment before attempting to parse
    // the prompt text itself.
    const singleMainJson = inputMode === 'JSON'
      ? (jsonAttachments[0]?.mainJson || parseJsonAttachments(normalizedPrompt, 'Circuit JSON')[0]?.mainJson)
      : undefined;
    if (inputMode === 'JSON' && !singleMainJson) {
      throw new Error('Attach or paste one JSON circuit.');
    }
    const result = inputMode === 'JSON' && multiplicity === 'Multiple'
      ? await generateJsonBatch({
          items: jsonItemsForRun(normalizedPrompt),
          targetService,
          routingMode: targetService === 'LT' ? 'wire' : 'combination',
          signal,
        })
      : targetService === 'LT' || targetService === 'EA'
        ? await generateWithExecutableProgress(
            normalizedPrompt || 'Direct JSON circuit generation',
            {
              targetService,
              mainJson: singleMainJson,
              routingMode: targetService === 'LT' ? 'wire' : 'combination',
              animationBudgetSeconds: animationBudgetSecondsForRun(),
              signal,
              onProgress: (event) => {
                if (!isActiveRun(runId)) return;
                if (event.event === 'stage' && typeof event.stage === 'string') {
                  setGenerationStage(EXECUTABLE_STAGE_LABELS[event.stage] || event.message || event.stage);
                }
                if (event.event === 'timing' && event.state === 'overdue') {
                  setGenerationStage('Finalizing download');
                  setIsGenerationDelayed(true);
                }
              },
            },
          )
      : await generateCircuit(
          normalizedPrompt || 'Direct JSON circuit generation',
          {
            targetService,
            mainJson: singleMainJson,
            routingMode: 'combination',
            signal,
          },
        );

    if (result.downloadUrl) {
      return {
        href: result.downloadUrl,
        name: result.fileName,
        objectUrl: false,
        serial: result.serial,
      };
    }

    if (!result.blob) {
      throw new Error('Backend did not return a downloadable artifact.');
    }

    return {
      href: window.URL.createObjectURL(result.blob),
      name: result.fileName,
      objectUrl: true,
      serial: result.serial,
    };
  };

  const addJsonText = (text: string, sourceName: string) => {
    try {
      const parsed = parseJsonAttachments(text, sourceName);
      if (jsonAttachments.length + parsed.length > MAX_JSON_ATTACHMENTS) {
        setValidation(`You can attach up to ${MAX_JSON_ATTACHMENTS} JSON circuits per run.`);
        return false;
      }
      setJsonAttachments((current) => [...current, ...parsed]);
      setMultiplicity('Multiple');
      setValidation('');
      return true;
    } catch (error) {
      setValidation(errorMessageFromUnknown(error));
      return false;
    }
  };

  const addJsonFiles = async (files: FileList) => {
    const selectedFiles = Array.from(files).slice(0, MAX_JSON_ATTACHMENTS);
    try {
      const parsedGroups = await Promise.all(selectedFiles.map(async (file) => {
        if (!file.name.toLowerCase().endsWith('.json')) throw new Error(`${file.name} is not a .json file.`);
        return parseJsonAttachments(await file.text(), file.name);
      }));
      const parsed = parsedGroups.flat();
      if (jsonAttachments.length + parsed.length > MAX_JSON_ATTACHMENTS) {
        throw new Error(`You can attach up to ${MAX_JSON_ATTACHMENTS} JSON circuits per run.`);
      }
      setJsonAttachments((current) => [...current, ...parsed]);
      setValidation('');
    } catch (error) {
      setValidation(errorMessageFromUnknown(error));
    }
  };

  const errorMessageFromUnknown = (error: unknown) => {
    if (error instanceof Error && error.message.trim()) return error.message;
    return 'Temporary generation failed.';
  };

  const resetGenerationFlow = () => {
    abortActiveGenerationRequest();
    clearExampleAutoSubmit();
    clearTimers();
    runIdRef.current += 1;
    downloadStartedRef.current = false;
    pendingErrorRef.current = '';
    setStatus('idle');
    setValidation('');
    setErrorMessage('');
    setGenerationStage('Preparing generation request');
    setIsGenerationDelayed(false);
    setShowDownload(false);
    resetDownloadFile();
  };

  const updateGenerationMode = (nextMode: GenerationMode) => {
    resetGenerationFlow();
    setVisualTone('blue');
    setGenerationMode(nextMode);
    writeStoredGenerationMode(nextMode);
  };

  useEffect(() => () => {
    runIdRef.current += 1;
    abortActiveGenerationRequest();
    clearExampleAutoSubmit();
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current = [];
    if (downloadFileRef.current.objectUrl) {
      window.URL.revokeObjectURL(downloadFileRef.current.href);
    }
  }, []);

  const addTimer = (callback: () => void, delay: number) => {
    const timer = window.setTimeout(callback, delay);
    timersRef.current.push(timer);
  };

  const isActiveRun = (runId: number) => runId === runIdRef.current;

  const startNewRun = () => {
    abortActiveGenerationRequest();
    clearTimers();
    runIdRef.current += 1;
    downloadStartedRef.current = false;
    setGenerationStage('Preparing generation request');
    setIsGenerationDelayed(false);
    resetDownloadFile();
    return runIdRef.current;
  };

  const waitForSuccessReady = (runId: number) => {
    if (!isActiveRun(runId)) return;

    if (isMobile || stageRef.current?.isForwardComplete()) {
      setGenerationStage('Finalizing download');
      setIsGenerationDelayed(false);
      setStatus('ready');
      setShowDownload(true);
      return;
    }

    addTimer(() => waitForSuccessReady(runId), FAILURE_POLL_MS);
  };

  const waitForRedSettle = (runId: number) => {
    if (!isActiveRun(runId)) return;

    if (isMobile || stageRef.current?.isSettledRed()) {
      setErrorMessage(pendingErrorRef.current);
      setVisualTone('red');
      setIsGenerationDelayed(false);
      setStatus('failed');
      downloadStartedRef.current = false;
      return;
    }

    addTimer(() => waitForRedSettle(runId), FAILURE_POLL_MS);
  };

  const waitForBlueSettle = (runId: number) => {
    if (!isActiveRun(runId)) return;

    if (isMobile || stageRef.current?.isSettledBlue()) {
      setVisualTone('blue');
      setGenerationStage('Preparing generation request');
      setIsGenerationDelayed(false);
      setStatus('idle');
      setErrorMessage('');
      if (inputMode === 'JSON') {
        setPrompt('');
        setJsonAttachments([]);
      }
      downloadStartedRef.current = false;
      resetDownloadFile();
      return;
    }

    addTimer(() => waitForBlueSettle(runId), FAILURE_POLL_MS);
  };

  const triggerGenerationFailure = (message: string, runId: number) => {
    if (!isActiveRun(runId)) return;

    clearTimers();
    pendingErrorRef.current = message;
    setErrorMessage('');
    setShowDownload(false);
    setIsGenerationDelayed(false);
    setStatus('failing');

    if (isMobile) {
      addTimer(() => waitForRedSettle(runId), MOBILE_SUCCESS_WAIT_MS);
      return;
    }

    if (!stageRef.current?.failToRed()) {
      setErrorMessage(message);
      setVisualTone('red');
      setStatus('failed');
      return;
    }

    addTimer(() => waitForRedSettle(runId), FAILURE_POLL_MS);
  };

  const startGeneration = (promptOverride?: string) => {
    if (status === 'generating' || status === 'failing' || status === 'ready' || status === 'reversing') return;

    const normalizedPrompt = (promptOverride ?? prompt).trim();

    if (!normalizedPrompt && jsonAttachments.length === 0) {
      setValidation(inputMode === 'JSON' ? 'Paste or attach circuit JSON before generating.' : 'Describe the circuit before generating.');
      return;
    }

    if (inputMode === 'JSON' && !hasAdvancedGenerationAccess(session)) {
      setValidation('Direct JSON generation is available to admin and demo accounts.');
      return;
    }

    if (inputMode === 'JSON') {
      try {
        if (multiplicity === 'Multiple') jsonItemsForRun(normalizedPrompt);
        else parseJsonAttachments(normalizedPrompt, 'Circuit JSON');
      } catch (error) {
        setValidation(errorMessageFromUnknown(error));
        return;
      }
    }

    const runId = startNewRun();
    pendingErrorRef.current = '';
    setValidation('');
    setErrorMessage('');
    setShowDownload(false);
    setStatus('generating');

    if (isNonAnimatedDark) {
      let successWaitComplete = false;
      let generationResolved = false;
      let failureWaitComplete = false;
      let generationError = '';

      const finishStaticSuccessIfReady = () => {
        if (!isActiveRun(runId) || !successWaitComplete || !generationResolved || generationError) return;

        setVisualTone('blue');
        setStatus('ready');
      };

      const finishStaticFailureIfReady = () => {
        if (!isActiveRun(runId) || !failureWaitComplete || !generationError) return;

        pendingErrorRef.current = generationError;
        setErrorMessage(generationError);
        setVisualTone('red');
        setStatus('failed');
      };

      addTimer(() => {
        successWaitComplete = true;
        finishStaticSuccessIfReady();
      }, NON_ANIMATED_SUCCESS_WAIT_MS);

      addTimer(() => {
        failureWaitComplete = true;
        finishStaticFailureIfReady();
      }, NON_ANIMATED_FAILURE_MIN_WAIT_MS);

      const generationSignal = startGenerationWatchdog(runId);
      requestGeneratedDownload(normalizedPrompt, generationSignal, runId)
        .then((file) => {
          if (!isActiveRun(runId)) return;

          markGenerationRequestResolved(runId);
          setDownloadFile(file);
          generationResolved = true;
          finishStaticSuccessIfReady();
        })
        .catch((error: unknown) => {
          if (!isActiveRun(runId)) return;
          if (requestWatchRef.current?.runId === runId && requestWatchRef.current.timedOut) return;

          markGenerationRequestResolved(runId);
          generationError = errorMessageFromUnknown(error);
          finishStaticFailureIfReady();
        });
      return;
    }

    if (!isMobile && isAnimatedDark) {
      const started = stageRef.current?.playForward();

      if (!started) {
        setStatus('idle');
        setValidation('Animation is still settling. Try again in a moment.');
        return;
      }
    }

    const generationSignal = startGenerationWatchdog(runId);
    requestGeneratedDownload(normalizedPrompt, generationSignal, runId)
      .then((file) => {
        if (!isActiveRun(runId)) return;

        markGenerationRequestResolved(runId);
        setDownloadFile(file);
        addTimer(() => waitForSuccessReady(runId), isMobile ? MOBILE_SUCCESS_WAIT_MS : FAILURE_POLL_MS);
      })
      .catch((error: unknown) => {
        if (!isActiveRun(runId)) return;
        const activeRequest = requestWatchRef.current;
        if (activeRequest?.runId === runId && activeRequest.timedOut) return;

        const elapsed = activeRequest?.runId === runId ? Date.now() - activeRequest.startedAt : 0;
        markGenerationRequestResolved(runId);
        addTimer(() => {
          triggerGenerationFailure(errorMessageFromUnknown(error), runId);
        }, Math.max(isMobile ? 650 : FAILURE_TRIGGER_DELAY_MS, NON_ANIMATED_FAILURE_MIN_WAIT_MS - elapsed));
      });
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    startGeneration();
  };

  const onSelectExample = (example: ExampleCircuit) => {
    if (status === 'generating' || status === 'failing' || status === 'ready' || status === 'reversing') return;

    clearExampleAutoSubmit();
    setIsExampleMenuOpen(false);
    setExampleSearch('');
    setInputMode('Balanced');
    setMultiplicity('Solo');
    setJsonAttachments([]);
    setPrompt(example.title);
    setValidation(`Selected ${example.title}. Generating in 3 seconds...`);
    exampleSubmitTimerRef.current = window.setTimeout(() => {
      exampleSubmitTimerRef.current = null;
      startGeneration(example.title);
    }, 3000);
  };

  const onPromptChange = (nextPrompt: string) => {
    clearExampleAutoSubmit();
    setPrompt(nextPrompt);
  };

  const visibleExamples = exampleLibrary?.featured || [];
  const remainingExamples = (exampleLibrary?.remaining || []).filter((example) => (
    !exampleSearch.trim() || example.title.toLowerCase().includes(exampleSearch.trim().toLowerCase())
  ));

  const onDownload = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    if (status !== 'ready' || downloadStartedRef.current) {
      event.preventDefault();
      return;
    }

    if (!isMobile && !stageRef.current?.reverseToBlue()) {
      event.preventDefault();
      return;
    }

    clearTimers();
    runIdRef.current += 1;
    const runId = runIdRef.current;
    downloadStartedRef.current = true;
    setShowDownload(false);
    setErrorMessage('');
    setIsGenerationDelayed(false);
    setGenerationStage('Preparing generation request');
    setStatus('reversing');
    addTimer(() => waitForBlueSettle(runId), isMobile ? MOBILE_SUCCESS_WAIT_MS : FAILURE_POLL_MS);
  };

  const onStaticDownload = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    if (status !== 'ready' || downloadStartedRef.current) {
      event.preventDefault();
      return;
    }

    clearTimers();
    runIdRef.current += 1;
    downloadStartedRef.current = true;
    setShowDownload(false);
    setErrorMessage('');
    setValidation('');
    setGenerationStage('Preparing generation request');
    setIsGenerationDelayed(false);
    setVisualTone('blue');
    setStatus('idle');
    if (inputMode === 'JSON') {
      setPrompt('');
      setJsonAttachments([]);
    }
    addTimer(() => {
      resetDownloadFile();
      downloadStartedRef.current = false;
    }, 1000);
  };

  const onStaticBack = () => {
    resetGenerationFlow();
    setVisualTone('red');
  };

  const onPageDragEnter = (event: ReactDragEvent<HTMLElement>) => {
    if (!canAcceptPageJsonDrop || !event.dataTransfer.types.includes('Files')) return;
    event.preventDefault();
    setIsPageDraggingJson(true);
  };

  const onPageDragOver = (event: ReactDragEvent<HTMLElement>) => {
    if (!canAcceptPageJsonDrop) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  };

  const onPageDragLeave = (event: ReactDragEvent<HTMLElement>) => {
    if (!canAcceptPageJsonDrop) return;
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return;
    setIsPageDraggingJson(false);
  };

  const onPageDrop = (event: ReactDragEvent<HTMLElement>) => {
    if (!canAcceptPageJsonDrop) return;
    event.preventDefault();
    setIsPageDraggingJson(false);
    if (event.dataTransfer.files.length) {
      setInputMode('JSON');
      setMultiplicity('Multiple');
      void addJsonFiles(event.dataTransfer.files);
    }
  };

  return (
    <main
      className={`generate-page ${isNonAnimatedDark ? 'is-static-mode' : ''} ${isRedMode ? 'is-failed' : ''} ${sidebarAutoHide.isSidebarHidden ? 'is-sidebar-collapsed' : ''} ${isAnimatedCinematic ? 'is-cinematic' : ''}`}
      onDragEnter={onPageDragEnter}
      onDragOver={onPageDragOver}
      onDragLeave={onPageDragLeave}
      onDrop={onPageDrop}
    >
      <PageMeta
        title="Generate Circuit | ProGenEDA"
        description="Generate bounded Proteus, KiCad, LTspice, and EasyEDA Pro circuit outputs with ProGenEDA's animated and non-animated dark generation workspaces."
        path="/generate"
      />

      {isPageDraggingJson && (
        <div className="page-json-drop-overlay" aria-live="polite">
          <DocumentUpload size={48} />
          <strong>Drop JSON circuits to attach them</strong>
          <span>They will be added above the prompt box.</span>
        </div>
      )}

      <GenerationSidebar
        session={session}
        activePath="/generate"
        motionMode={motionMode}
        themeMode={themeMode}
        onMotionModeChange={(nextMotionMode) => updateGenerationMode({ ...generationMode, motion: nextMotionMode })}
        onThemeModeChange={(nextThemeMode) => updateGenerationMode({ ...generationMode, theme: nextThemeMode })}
        autoHideSidebar={sidebarAutoHide.isAutoHideEnabled}
        onAutoHideSidebarChange={sidebarAutoHide.setAutoHideEnabled}
        interactionProps={sidebarAutoHide.sidebarInteractionProps}
      />
      <SidebarRevealZone {...sidebarAutoHide.revealZoneProps} />

      <section className="generate-workspace" aria-label="ProGenEDA dark generator">
        <StatusPill
          status={status}
          errorMessage={errorMessage}
          stage={generationStage}
          isDelayed={isGenerationDelayed}
        />

        {isStaticWorkspace ? (
          <NonAnimatedWorkspaceStates
            state={staticWorkspaceState}
            errorMessage={errorMessage}
            onBack={onStaticBack}
            onDownload={onStaticDownload}
            downloadHref={downloadFile.href}
            downloadName={downloadFile.name}
            targetService={targetService}
            stageLabel={generationStage}
            isDelayed={isGenerationDelayed}
            serial={downloadFile.serial}
            onEdit={(serial) => setEditorSerial(serial)}
          />
        ) : (
          <>
            <div className={`generate-hero ${isNonAnimatedDark ? 'generate-hero--static' : ''} ${isExampleMenuOpen ? 'is-example-library-open' : ''}`}>
              {!isMobile && isAnimatedDark && <TesseractStage ref={stageRef} disabled={isMobile || !isAnimatedDark} />}
              {!isMobile && isNonAnimatedDark && <NonAnimatedRoutingBoard />}

              {isMobile && (
                <div className="mobile-generate-card">
                  <MagicStar size={30} />
                  <h1>Generate circuits</h1>
                  <p>Enter a prompt or circuit JSON to create an EDA-ready output.</p>
                </div>
              )}

              <div className="generate-copy">
                <h1>Describe the circuit you want to generate</h1>
                <p>ProGenEDA interprets your intent to build accurate schematics and netlists.</p>
              </div>

              {jsonAttachments.length === 0 && (
                <div className="example-library">
                  <div className="example-chip-row" aria-label="Prompt examples">
                    {(targetService === 'LT' || targetService === 'EA') && visibleExamples.length > 0 ? (
                      <>
                        {visibleExamples.map((example, index) => {
                          const ChipIcon = index === 0 ? Activity : index === 1 ? Flash : index === 2 ? SliderHorizontal : Element4;
                          return (
                            <button type="button" key={example.id} onClick={() => onSelectExample(example)}>
                              <ChipIcon size={18} /> {example.title}
                            </button>
                          );
                        })}
                        <button
                          type="button"
                          className="example-chip-row__more"
                          aria-expanded={isExampleMenuOpen}
                          aria-label={`More ${targetDetails(targetService).label} examples`}
                          title={`More ${targetDetails(targetService).label} examples`}
                          onClick={() => setIsExampleMenuOpen((current) => !current)}
                        >
                          <MoreCircle size={20} aria-hidden="true" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button type="button"><Activity size={18} /> Low-noise instrumentation amplifier</button>
                        <button type="button"><Flash size={18} /> 24V to 5V isolated DC-DC converter</button>
                        <button type="button"><SliderHorizontal size={18} /> Active PFC power supply</button>
                        <button type="button" className="example-chip-row__more" aria-label="More examples" title="More examples"><MoreCircle size={20} aria-hidden="true" /></button>
                      </>
                    )}
                  </div>

                  {(targetService === 'LT' || targetService === 'EA') && isExampleMenuOpen && (
                    <section
                      className="example-library-menu"
                      aria-label={`More ${targetDetails(targetService).label} circuit examples`}
                      onWheelCapture={(event) => {
                        // ParticlesSwarm owns a window-level wheel listener. Preserve native scrolling here.
                        event.stopPropagation();
                        event.nativeEvent.stopImmediatePropagation();
                      }}
                    >
                      <header>
                        <div>
                          <strong>Verified {targetDetails(targetService).label} examples</strong>
                          <span>{exampleLibrary?.total || 0} canonical circuits</span>
                        </div>
                        <button type="button" aria-label={`Close ${targetDetails(targetService).label} examples`} onClick={() => setIsExampleMenuOpen(false)}>
                          <CloseCircle size={19} />
                        </button>
                      </header>
                      <label>
                        <SearchNormal1 size={17} />
                        <input
                          value={exampleSearch}
                          onChange={(event) => setExampleSearch(event.target.value)}
                          placeholder={`Filter ${exampleLibrary?.remaining.length || 0} more examples`}
                          autoFocus
                        />
                      </label>
                      <div
                        className="example-library-menu__list"
                        onWheelCapture={(event) => {
                          event.stopPropagation();
                          event.nativeEvent.stopImmediatePropagation();
                        }}
                      >
                        {remainingExamples.map((example) => (
                          <button type="button" key={example.id} onClick={() => onSelectExample(example)}>
                            <span>{example.title}</span>
                            <small>Use example</small>
                          </button>
                        ))}
                        {remainingExamples.length === 0 && <p>No matching {targetDetails(targetService).label} example.</p>}
                      </div>
                    </section>
                  )}
                </div>
              )}

              {isAnimatedDark && showDownload && (
                <DownloadModal
                  href={downloadFile.href}
                  fileName={downloadFile.name}
                  targetService={targetService}
                  serial={downloadFile.serial}
                  onDownload={onDownload}
                  onEdit={(serial) => setEditorSerial(serial)}
                />
              )}
            </div>

            <div className="composer-shell">
              <PromptComposer
                prompt={prompt}
                status={status}
                validation={validation}
                session={session}
                targetService={targetService}
                inputMode={inputMode}
                multiplicity={multiplicity}
                attachments={jsonAttachments}
                isJsonDropActive={isPageDraggingJson}
                onPromptChange={onPromptChange}
                onTargetServiceChange={(service) => {
                  clearExampleAutoSubmit();
                  setTargetService(service);
                  setValidation('');
                }}
                onInputModeChange={(mode) => {
                  clearExampleAutoSubmit();
                  setInputMode(mode);
                  if (mode !== 'JSON') {
                    setMultiplicity('Solo');
                    setJsonAttachments([]);
                  }
                  setValidation('');
                }}
                onMultiplicityChange={(nextMultiplicity) => {
                  clearExampleAutoSubmit();
                  setMultiplicity(nextMultiplicity);
                  if (nextMultiplicity === 'Multiple') setInputMode('JSON');
                  if (nextMultiplicity === 'Solo') setJsonAttachments([]);
                  setValidation('');
                }}
                onAddJsonText={addJsonText}
                onAddJsonFiles={addJsonFiles}
                onRemoveAttachment={(id) => setJsonAttachments((current) => current.filter((item) => item.id !== id))}
                onOpenSerialLookup={() => setShowSerialLookup(true)}
                onSubmit={onSubmit}
              />
              <p className="generation-warning"><ShieldTick size={16} /> AI outputs may contain errors. Verify critical results.</p>
            </div>
          </>
        )}

        {showSerialLookup && <SharedSerialDialog onClose={() => setShowSerialLookup(false)} />}
        {editorSerial && (
          <KiCadJsonLab
            serial={editorSerial}
            onClose={() => setEditorSerial(null)}
            onGenerated={() => undefined}
          />
        )}
      </section>
    </main>
  );
}
