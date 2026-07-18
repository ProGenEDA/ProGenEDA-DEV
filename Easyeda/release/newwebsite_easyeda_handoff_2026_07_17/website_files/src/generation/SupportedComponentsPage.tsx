import { useMemo, useState } from 'react';
import {
  Box,
  Category2,
  Cpu,
  Diagram,
  Electricity,
  Flash,
  HierarchySquare3,
  MessageQuestion,
  Notification,
  SearchNormal1,
  ShieldTick,
  StatusUp,
} from 'iconsax-react';
import { AuthSession } from '../auth/authProvider';
import { PageMeta } from '../contentPages';
import { GenerationSidebar } from './GenerationSidebar';
import {
  GenerationMode,
  readStoredGenerationMode,
  writeStoredGenerationMode,
} from './generationModeStorage';
import { SidebarRevealZone } from './SidebarRevealZone';
import { useSidebarAutoHide } from './sidebarAutoHide';
import kicadSupportedComponents from './kicadSupportedComponents.json';
import ltspiceSupportedComponents from './ltspiceSupportedComponents.json';
import proteusSupportedComponents from './proteusSupportedComponents.json';
import easyedaSupportedComponents from './easyedaSupportedComponents.json';

const TEMP_SESSION_KEY = 'progeneda.tempSession';

type ComponentGroup = {
  id: string;
  title: string;
  category: string;
  icon: typeof Box;
  parts: string[];
  wide?: boolean;
};

const proteusIconMap = {
  Box,
  Cpu,
  Diagram,
  Electricity,
  Flash,
  HierarchySquare3,
  ShieldTick,
  StatusUp,
} as const;

type ProteusComponentGroupDefinition = Omit<ComponentGroup, 'icon'> & {
  icon: keyof typeof proteusIconMap;
};

// Edit the catalog JSON, not this rendering layer. The registry test prevents
// the browser list from drifting from the backend's PR-A contract.
const proteusComponentGroups: ComponentGroup[] = (
  proteusSupportedComponents.groups as ProteusComponentGroupDefinition[]
).map((group) => ({
  ...group,
  icon: proteusIconMap[group.icon] || Box,
}));

const PROTEUS_SUPPORTED_COMPONENT_COUNT = proteusComponentGroups.reduce(
  (total, group) => total + group.parts.length,
  0,
);

type SupportedService = 'PR' | 'KC_SCH' | 'KC_PCB' | 'LT' | 'EA';

function readRequestedService(): SupportedService {
  const requested = new URLSearchParams(window.location.search).get('service')?.toUpperCase();
  if (requested === 'KC_PCB' || requested === 'KICAD_PCB' || requested === 'PCB') return 'KC_PCB';
  if (requested === 'KC' || requested === 'KC_SCH' || requested === 'KICAD_SCH') return 'KC_SCH';
  if (requested === 'LT' || requested === 'LTSPICE') return 'LT';
  if (requested === 'EA' || requested === 'EASYEDA' || requested === 'EASYEDA_PRO') return 'EA';
  return 'PR';
}

const kicadGroupMeta: Record<string, { title: string; icon: typeof Box; wide?: boolean }> = {
  power_symbol: { title: 'Power & Rails', icon: StatusUp },
  source: { title: 'Sources', icon: Electricity },
  passive: { title: 'Passive Components', icon: Electricity, wide: true },
  diode: { title: 'Diodes', icon: Diagram },
  indicator: { title: 'Indicators & LEDs', icon: StatusUp },
  bjt: { title: 'BJTs', icon: HierarchySquare3 },
  mosfet: { title: 'MOSFETs', icon: HierarchySquare3 },
  regulator: { title: 'Regulators', icon: Flash },
  opamp: { title: 'Op-Amps', icon: Flash },
  logic_ic: { title: 'Logic ICs', icon: Cpu },
  interface_ic: { title: 'Interface ICs', icon: Cpu },
  memory_ic: { title: 'Memory ICs', icon: Cpu },
  microcontroller_module: { title: 'Controller Modules', icon: Cpu },
  wireless_module: { title: 'Wireless Modules', icon: Cpu },
  connector: { title: 'Connectors & Terminals', icon: Box, wide: true },
};

const kicadComponentGroups: ComponentGroup[] = Object.entries(kicadSupportedComponents.groups).map(([id, parts]) => {
  const meta = kicadGroupMeta[id] || { title: id.replace(/_/g, ' '), icon: Box };
  return {
    id: `kicad-${id}`,
    title: meta.title,
    category: meta.title,
    icon: meta.icon,
    parts,
    wide: meta.wide,
  };
});

const kicadPcbMappedComponents = Object.entries(kicadSupportedComponents.pcb.abstract_footprint_mappings)
  .filter(([, footprint]) => Boolean(footprint))
  .map(([component]) => component);

const kicadPcbComponentGroups: ComponentGroup[] = [
  {
    id: 'kicad-pcb-mappings',
    title: 'Physical Component Mappings',
    category: 'Physical Component Mappings',
    icon: HierarchySquare3,
    parts: kicadPcbMappedComponents,
    wide: true,
  },
  {
    id: 'kicad-pcb-footprints',
    title: 'Audited KiCad Footprints',
    category: 'Audited KiCad Footprints',
    icon: Box,
    parts: kicadSupportedComponents.pcb.audited_footprints,
    wide: true,
  },
];

const ltspiceGroupMeta: Record<string, { title: string; icon: typeof Box; wide?: boolean }> = {
  sources_and_ground: { title: 'Sources & Ground', icon: StatusUp },
  passive: { title: 'Passive Components', icon: Electricity },
};

const ltspiceComponentGroups: ComponentGroup[] = Object.entries(ltspiceSupportedComponents.groups).map(([id, parts]) => {
  const meta = ltspiceGroupMeta[id] || { title: id.replace(/_/g, ' '), icon: Box };
  return {
    id: `ltspice-${id}`,
    title: meta.title,
    category: meta.title,
    icon: meta.icon,
    parts,
    wide: meta.wide,
  };
});

const easyedaGroupMeta: Record<string, { title: string; icon: typeof Box; wide?: boolean }> = {
  basic: { title: 'Basic Components', icon: Electricity, wide: true },
  lab_digital: { title: 'Lab & Digital', icon: Cpu, wide: true },
  embedded: { title: 'Embedded Systems', icon: Cpu, wide: true },
  pcb_utility: { title: 'PCB Utility', icon: Box },
  power_usb: { title: 'Power & USB', icon: Flash },
  communications: { title: 'Communications', icon: Diagram },
  i2c: { title: 'I2C Peripherals', icon: HierarchySquare3 },
};

const easyedaComponentGroups: ComponentGroup[] = Object.entries(easyedaSupportedComponents.groups).map(([id, parts]) => {
  const meta = easyedaGroupMeta[id] || { title: id.replace(/_/g, ' '), icon: Box };
  return {
    id: `easyeda-${id}`,
    title: meta.title,
    category: meta.title,
    icon: meta.icon,
    parts,
    wide: meta.wide,
  };
});

const requestComponentHref = `mailto:request@progeneda.app?subject=${encodeURIComponent('ProGenEDA component request')}&body=${encodeURIComponent(`Hi ProGenEDA team,

Please add support for:

Component name:
Target EDA tool:
Use case:

Thanks.`)}`;

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

export function SupportedComponentsPage() {
  const [session] = useState<AuthSession | null>(() => readStoredSession());
  const [generationMode, setGenerationMode] = useState(() => readStoredGenerationMode());
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [service, setService] = useState<SupportedService>(() => readRequestedService());
  const sidebarAutoHide = useSidebarAutoHide();
  const componentGroups = service === 'KC_SCH'
    ? kicadComponentGroups
    : service === 'KC_PCB'
      ? kicadPcbComponentGroups
      : service === 'LT'
        ? ltspiceComponentGroups
        : service === 'EA'
          ? easyedaComponentGroups
        : proteusComponentGroups;
  const totalSupported = useMemo(
    () => service === 'KC_PCB'
      ? kicadSupportedComponents.pcb.source_footprint_record_count
      : service === 'LT'
        ? ltspiceSupportedComponents.total_supported_families
        : service === 'EA'
          ? easyedaSupportedComponents.total_supported_families
      : componentGroups.reduce((total, group) => total + group.parts.length, 0),
    [componentGroups, service],
  );
  const categories = useMemo(() => componentGroups.map((group) => group.category), [componentGroups]);
  const visibleGroups = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return componentGroups
      .filter((group) => category === 'all' || group.category === category)
      .map((group) => {
        const groupMatchesSearch = group.title.toLowerCase().includes(normalizedSearch);
        const visibleParts = !normalizedSearch || groupMatchesSearch
          ? group.parts
          : group.parts.filter((part) => part.toLowerCase().includes(normalizedSearch));

        return { ...group, parts: visibleParts };
      })
      .filter((group) => group.parts.length > 0);
  }, [category, componentGroups, search]);

  const selectService = (nextService: SupportedService) => {
    setService(nextService);
    setCategory('all');
    setSearch('');
    const url = new URL(window.location.href);
    url.searchParams.set('service', nextService);
    window.history.replaceState(window.history.state, '', url);
  };

  const updateGenerationMode = (nextMode: GenerationMode) => {
    setGenerationMode(nextMode);
    writeStoredGenerationMode(nextMode);
  };

  const isPcbService = service === 'KC_PCB';
  const isLtspiceService = service === 'LT';
  const isEasyedaService = service === 'EA';
  const serviceName = service === 'PR'
    ? 'Proteus'
    : service === 'KC_SCH'
      ? 'KiCad schematic'
      : service === 'KC_PCB'
        ? 'KiCad PCB'
        : service === 'LT'
          ? 'LTspice .asc'
          : 'EasyEDA Pro .eprj';

  return (
    <main className={`generate-page supported-page ${sidebarAutoHide.isSidebarHidden ? 'is-sidebar-collapsed' : ''}`}>
      <PageMeta
        title="Supported Components | ProGenEDA"
        description="Browse the bounded Proteus, KiCad, LTspice, and donor-native EasyEDA Pro component families currently exposed by ProGenEDA."
        path="/supported-components"
      />
      <GenerationSidebar
        session={session}
        activePath="/supported-components"
        motionMode={generationMode.motion}
        themeMode={generationMode.theme}
        onMotionModeChange={(nextMotionMode) => updateGenerationMode({ ...generationMode, motion: nextMotionMode })}
        onThemeModeChange={(nextThemeMode) => updateGenerationMode({ ...generationMode, theme: nextThemeMode })}
        autoHideSidebar={sidebarAutoHide.isAutoHideEnabled}
        onAutoHideSidebarChange={sidebarAutoHide.setAutoHideEnabled}
        interactionProps={sidebarAutoHide.sidebarInteractionProps}
      />
      <SidebarRevealZone {...sidebarAutoHide.revealZoneProps} />

      <section className="generate-workspace supported-workspace" aria-label="Supported components">
        <div className="generate-topbar" aria-label="Generation status">
          <span><i /> All systems operational</span>
          <button type="button" aria-label="Notifications"><Notification size={20} /></button>
        </div>

        <div className="supported-shell">
          <header className="supported-header">
            <h1>Supported Components</h1>
            <p>Components currently supported for schematic and netlist generation.</p>
            <div className="supported-service-tabs" role="tablist" aria-label="EDA component library">
              <button
                className={service === 'PR' ? 'is-active' : ''}
                type="button"
                role="tab"
                aria-selected={service === 'PR'}
                onClick={() => selectService('PR')}
              >
                Proteus <small>{PROTEUS_SUPPORTED_COMPONENT_COUNT}</small>
              </button>
              <button
                className={service === 'KC_SCH' ? 'is-active' : ''}
                type="button"
                role="tab"
                aria-selected={service === 'KC_SCH'}
                onClick={() => selectService('KC_SCH')}
              >
                KiCad .sch <small>{kicadSupportedComponents.totalSupportedWords}</small>
              </button>
              <button
                className={service === 'KC_PCB' ? 'is-active' : ''}
                type="button"
                role="tab"
                aria-selected={service === 'KC_PCB'}
                onClick={() => selectService('KC_PCB')}
              >
                KiCad .pcb <small>{kicadSupportedComponents.pcb.source_footprint_record_count}</small>
              </button>
              <button
                className={service === 'LT' ? 'is-active' : ''}
                type="button"
                role="tab"
                aria-selected={service === 'LT'}
                onClick={() => selectService('LT')}
              >
                LTspice .asc <small>{ltspiceSupportedComponents.total_supported_families}</small>
              </button>
              <button
                className={service === 'EA' ? 'is-active' : ''}
                type="button"
                role="tab"
                aria-selected={service === 'EA'}
                onClick={() => selectService('EA')}
              >
                EasyEDA .eprj <small>{easyedaSupportedComponents.total_supported_families}</small>
              </button>
            </div>
          </header>

          <section className="supported-toolbar" aria-label="Component filters">
            <label>
              <SearchNormal1 size={22} />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search components..."
              />
            </label>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="all">All Categories</option>
              {categories.map((categoryName) => (
                <option key={categoryName} value={categoryName}>{categoryName}</option>
              ))}
            </select>
            <aside className="supported-total" aria-label={`${totalSupported} total supported components`}>
              <strong>{totalSupported}</strong>
              <span>{isPcbService ? <>Audited footprint<br />records</> : isLtspiceService ? <>Native stock-symbol<br />families</> : isEasyedaService ? <>Donor-native<br />families</> : <>Total Supported<br />components</>}</span>
            </aside>
          </section>

          <section className="supported-callouts" aria-label="Supported component summary">
            <article>
              <span><Cpu size={32} variant="Bulk" /></span>
              <div>
                <strong>{isPcbService ? `${totalSupported} source-backed footprint records` : `${totalSupported} supported components`}</strong>
                <p>
                  {isPcbService
                    ? `${kicadPcbMappedComponents.length} physical component kinds map into the bounded two-layer PCB flow.`
                    : isLtspiceService
                      ? `Wire-only donor-native generation, with a ${ltspiceSupportedComponents.max_components_per_circuit}-component validation cap.`
                    : isEasyedaService
                      ? `Wire, terminal, and combination schematics up to ${easyedaSupportedComponents.limits.max_schematic_input_components} components; bounded PCB up to ${easyedaSupportedComponents.limits.max_physical_pcb_components} physical parts.`
                    : `Ready for use in ${serviceName} generation flows.`}
                </p>
              </div>
            </article>
            <article>
              <span><MessageQuestion size={32} /></span>
              <div>
                <strong>Need more parts?</strong>
                <p>Upgrade quota or request additional component support.</p>
              </div>
              <a href={requestComponentHref}>Request Component</a>
            </article>
          </section>

          <section className="supported-grid" aria-label="Component library">
            {visibleGroups.map(({ id, title, icon: Icon, parts, wide }) => (
              <article className={wide ? 'is-wide' : ''} id={id} key={id}>
                <h2>
                  <Icon size={25} />
                  {title}
                </h2>
                {service === 'PR' && (title === 'Analog & Control ICs' || title === 'Displays & Logic ICs') && (
                  <p className="supported-ic-limit">Maximum {proteusSupportedComponents.integratedCircuitLimitPerPart} instances of each IC per circuit.</p>
                )}
                <div className="supported-chip-grid">
                  {parts.map((part) => <span key={part}>{part}</span>)}
                </div>
              </article>
            ))}

            {visibleGroups.length === 0 && (
              <div className="supported-empty">
                <Category2 size={26} />
                <strong>No matching components</strong>
                <span>Try another search term or request the component for review.</span>
              </div>
            )}
          </section>

          <p className="supported-note">
            <Category2 size={18} />
            {isPcbService
              ? 'A board is downloadable only after source, pad-net, clearance, connectivity, overlap, and outline validation pass.'
              : isLtspiceService
                ? 'LTspice emits stock-symbol .asc files with direct physical wires only. Unsupported families are rejected instead of approximated.'
              : isEasyedaService
                ? 'EasyEDA emits one donor-native .eprj. Every source pin is explicit; netlist, geometry, donor hashes, and any included PCB are validated before download.'
              : service === 'PR'
                ? `Proteus currently lists ${PROTEUS_SUPPORTED_COMPONENT_COUNT} components. Each listed IC is limited to ${proteusSupportedComponents.integratedCircuitLimitPerPart} instances per circuit.`
                : 'Components are updated regularly. Check back for new additions.'}
          </p>
        </div>
      </section>
    </main>
  );
}
