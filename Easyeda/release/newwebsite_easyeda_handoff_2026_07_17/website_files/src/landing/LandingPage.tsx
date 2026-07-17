import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  ArrowDown,
  ArrowRight,
  Check,
  ChevronRight,
  CircuitBoard,
  Cpu,
  Download,
  FileCode2,
  FileJson,
  Menu,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Waves,
  X,
} from 'lucide-react';
import { PageMeta } from '../contentPages';
import { landingContent } from './landingContent';
import './landing.css';

const SITE_ORIGIN = 'https://progeneda.app';

function LandingBrand() {
  return (
    <a className="landing-brand" href="/" aria-label="ProGenEDA home">
      <img src="/assets/progen-logo-transparent.png" alt="" />
      <span>{landingContent.brand}</span>
      <small>Alpha</small>
    </a>
  );
}

function ArrowLink({ href, children, className = '' }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a className={`landing-arrow-link ${className}`} href={href}>
      <span>{children}</span>
      <ArrowRight size={18} aria-hidden="true" />
    </a>
  );
}

function SectionIntro({ eyebrow, title, body, invert = false }: { eyebrow: string; title: string; body: string; invert?: boolean }) {
  return (
    <header className={`landing-section-intro ${invert ? 'is-inverted' : ''}`} data-landing-reveal>
      <p>{eyebrow}</p>
      <h2>{title}</h2>
      <span>{body}</span>
    </header>
  );
}

function StoryImage({ src, alt, className = '' }: { src: string; alt: string; className?: string }) {
  return (
    <figure className={`landing-story-image ${className}`} data-landing-reveal>
      <img src={src} alt={alt} loading="lazy" decoding="async" />
    </figure>
  );
}

function ValueRecompileDemo() {
  const values = ['1 kΩ', '5 kΩ', '10 kΩ'] as const;
  const [activeValue, setActiveValue] = useState<(typeof values)[number]>('1 kΩ');
  const revision = values.indexOf(activeValue) + 1;

  return (
    <div className="landing-recompile" data-landing-reveal>
      <div className="landing-recompile__header">
        <span><RefreshCw size={18} /> Deterministic recompile</span>
        <small>KiCad editor alpha</small>
      </div>
      <div className="landing-recompile__body">
        <div className="landing-component-symbol" aria-hidden="true">
          <i />
          <svg viewBox="0 0 220 80">
            <path d="M0 40h30l13-18 22 36 22-36 22 36 22-36 22 36 13-18h34" />
          </svg>
          <i />
        </div>
        <div>
          <p>R1 / feedback resistor</p>
          <div className="landing-value-options" aria-label="Choose a resistor value">
            {values.map((value) => (
              <button
                className={value === activeValue ? 'is-active' : ''}
                type="button"
                onClick={() => setActiveValue(value)}
                key={value}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="landing-recompile__footer" aria-live="polite">
        <span><Check size={16} /> Value validated</span>
        <span><FileCode2 size={16} /> filter-r{revision}.kicad_sch</span>
        <span><Sparkles size={16} /> AI calls: 0</span>
      </div>
    </div>
  );
}

export function LandingPage() {
  const pageRef = useRef<HTMLElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeFile, setActiveFile] = useState(0);

  const structuredData = useMemo(() => ({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'SoftwareApplication',
        name: 'ProGenEDA',
        url: SITE_ORIGIN,
        applicationCategory: 'EngineeringApplication',
        operatingSystem: 'Web',
        description: 'ProGenEDA converts circuit intent into native, editable EDA project files for KiCad, EasyEDA Pro, LTspice, and Proteus.',
        offers: { '@type': 'Offer', availability: 'https://schema.org/PreOrder' },
      },
      {
        '@type': 'Organization',
        name: 'ProGenEDA',
        url: SITE_ORIGIN,
        logo: `${SITE_ORIGIN}/assets/progen-logo-transparent.png`,
      },
    ],
  }), []);

  useEffect(() => {
    const root = pageRef.current;
    if (!root) return;

    const revealTargets = Array.from(root.querySelectorAll<HTMLElement>('[data-landing-reveal]'));
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          (entry.target as HTMLElement).dataset.visible = 'true';
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -8% 0px' });

    revealTargets.forEach((target) => observer.observe(target));

    const updateProgress = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const progress = max > 0 ? Math.min(1, window.scrollY / max) : 0;
      root.style.setProperty('--landing-scroll-progress', String(progress));
    };

    updateProgress();
    window.addEventListener('scroll', updateProgress, { passive: true });

    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', updateProgress);
    };
  }, []);

  return (
    <main className="landing-page" ref={pageRef}>
      <PageMeta
        title="ProGenEDA | Circuit Intent In. Native EDA Files Out."
        description="ProGenEDA converts circuit intent into native, editable project files for KiCad, EasyEDA Pro, LTspice, and Proteus using a structured circuit model and deterministic exporters."
        path="/"
        structuredData={structuredData}
      />

      <div className="landing-progress" aria-hidden="true"><span /></div>

      <header className="landing-header">
        <LandingBrand />
        <nav className={menuOpen ? 'is-open' : ''} aria-label="Main navigation">
          {landingContent.nav.map((item) => (
            <a href={item.href} onClick={() => setMenuOpen(false)} key={item.label}>{item.label}</a>
          ))}
          <a className="landing-header__login" href="/login">Sign in</a>
          <a className="landing-header__demo" href="/login">Try the demo <ArrowRight size={16} /></a>
        </nav>
        <button
          className="landing-menu-button"
          type="button"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </header>

      <section className="landing-hero" id="product">
        <img
          className="landing-hero__image"
          src={landingContent.assets.hero}
          alt="A circuit schematic becoming engineering documents and waveforms on a white drafting table"
          fetchPriority="high"
        />
        <div className="landing-hero__copy" data-landing-reveal data-visible="true">
          <p>{landingContent.hero.eyebrow}</p>
          <h1>
            <span>{landingContent.hero.title[0]}</span>
            <span>{landingContent.hero.title[1]}</span>
          </h1>
          <div className="landing-hero__body">
            <span>{landingContent.hero.body}</span>
            <div className="landing-hero__actions">
              <ArrowLink href={landingContent.hero.primaryCta.href}>{landingContent.hero.primaryCta.label}</ArrowLink>
              <a className="landing-text-link" href={landingContent.hero.secondaryCta.href}>
                <Play size={16} fill="currentColor" /> {landingContent.hero.secondaryCta.label}
              </a>
            </div>
            <small>{landingContent.hero.note}</small>
          </div>
        </div>
        <a className="landing-scroll-cue" href="#problem" aria-label="Continue to the product story">
          Scroll to compile <ArrowDown size={18} />
        </a>
      </section>

      <section className="landing-proof-strip" id="proof" aria-label="Product proof points">
        {landingContent.proofPoints.map((point) => (
          <div key={point.label} data-landing-reveal>
            <strong>{point.value}</strong>
            <span>{point.label}</span>
            <small>{point.detail}</small>
          </div>
        ))}
      </section>

      <section className="landing-thesis">
        <p data-landing-reveal>Not a circuit explanation.</p>
        <p data-landing-reveal>Not a generated image.</p>
        <h2 data-landing-reveal>A real file you can open, edit, simulate, and keep working on.</h2>
      </section>

      <div className="landing-story-nav" aria-hidden="true">
        {landingContent.acts.map((act) => <span key={act.number}>{act.number} {act.label}</span>)}
      </div>

      <section className="landing-story-section landing-story-section--friction" id="problem">
        <div className="landing-story-copy">
          <span className="landing-act">Act I / The work between idea and tool</span>
          <h2>The circuit may already be known. The file still has to be built.</h2>
          <p>Components still get placed, wired, labeled, revised, and rebuilt across tools. The expensive part is often not invention. It is reconstruction.</p>
          <dl>
            <div><dt>01</dt><dd>Place every component</dd></div>
            <div><dt>02</dt><dd>Resolve every pin and net</dd></div>
            <div><dt>03</dt><dd>Rebuild the same intent elsewhere</dd></div>
          </dl>
        </div>
        <StoryImage src={landingContent.assets.friction} alt="An engineer manually redrawing several revisions of the same circuit" />
      </section>

      <section className="landing-market-section" id="market">
        <SectionIntro
          eyebrow="The economic context / Paid engineering time"
          title="A large software market. A very specific first job to automate."
          body="EDA is a meaningful, growing category, and circuit construction is skilled paid work. ProGenEDA is not claiming the whole market; it starts with the repeated work between a known circuit and a usable native project."
        />
        <div className="landing-market-ledger">
          {landingContent.marketSignals.map((signal, index) => (
            <article key={`${signal.value}-${signal.label}`} data-landing-reveal>
              <span>0{index + 1}</span>
              <strong>{signal.value}</strong>
              <h3>{signal.label}</h3>
              <a href={signal.href} target="_blank" rel="noreferrer">
                {signal.source} <ArrowRight size={14} />
              </a>
            </article>
          ))}
        </div>
        <div className="landing-market-thesis" data-landing-reveal>
          <p>What the figures support</p>
          <div>
            <span><Check size={16} /> Circuit and PCB construction is paid technical work.</span>
            <span><Check size={16} /> Manual engineering time has material economic value.</span>
            <span><Check size={16} /> Automation can create value without replacing engineering judgment.</span>
          </div>
          <small>Third-party estimates use different methodologies and change over time. They are market signals, not proof that ProGenEDA has product-market fit.</small>
        </div>
      </section>

      <section className="landing-structure" id="architecture">
        <SectionIntro
          eyebrow="Act II / Intent becomes structure"
          title="The model understands the request. Then it stops."
          body="ProGenEDA turns human intent into a tool-neutral circuit contract. The contract, not model prose, becomes the source for deterministic generation."
        />
        <div className="landing-structure__media">
          <StoryImage src={landingContent.assets.schema} alt="A circuit request resolving into a structured component and net graph" />
          <div className="landing-schema-overlay" data-landing-reveal>
            <span>R1 <b>1 kΩ</b></span>
            <span>C1 <b>10 µF</b></span>
            <span>NET <b>VOUT</b></span>
            <span>SIM <b>TRAN</b></span>
          </div>
        </div>
        <div className="landing-architecture-steps">
          {landingContent.architecture.map((step) => (
            <article key={step.index} data-landing-reveal>
              <span>{step.index}</span>
              <small>{step.label}</small>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-pipeline-section" id="pipeline">
        <SectionIntro
          eyebrow="The complete production path / Current KiCad architecture"
          title="Every stage leaves evidence. Every native file has to earn its download."
          body="The pipeline does more than turn JSON into text. It normalizes intent, explores constrained construction variants, parses its own output, compares actual connectivity with the circuit contract, and packages both the project and its validation record."
        />
        <div className="landing-pipeline-map">
          {landingContent.pipeline.map((phase) => (
            <article key={phase.index} data-landing-reveal>
              <header>
                <span>{phase.index}</span>
                <div>
                  <small>{phase.owner}</small>
                  <h3>{phase.phase}</h3>
                </div>
              </header>
              <p>{phase.body}</p>
              <ol>
                {phase.stages.map((stage) => <li key={stage}>{stage}</li>)}
              </ol>
            </article>
          ))}
        </div>
        <div className="landing-pipeline-contract" data-landing-reveal>
          <FileJson size={20} />
          <span><b>Shared input:</b> one canonical circuit JSON</span>
          <ChevronRight size={17} />
          <span><b>Target backends:</b> KiCad, EasyEDA Pro, LTspice, Proteus</span>
          <ChevronRight size={17} />
          <span><b>Release rule:</b> invalid artifacts stay private</span>
        </div>
        <p className="landing-pipeline-note">* The source-backed KiCad PCB path is a bounded MVP under work: unsupported mappings or unrouted nets produce no public board artifact.</p>
      </section>

      <section className="landing-compiler-section">
        <SectionIntro
          eyebrow="Act III / AI for understanding. Code for exactness."
          title="The model never writes the final CAD file."
          body="Exact EDA syntax is a compiler problem. Unsupported structures are rejected; accepted CircuitIR passes through backend-specific rules and validators before packaging."
        />
        <StoryImage src={landingContent.assets.compiler} alt="A precise validation jig rejecting one malformed schematic and accepting deterministic outputs" className="landing-story-image--wide" />
        <div className="landing-compiler-rule" data-landing-reveal>
          <span><FileJson size={21} /> CircuitIR</span>
          <ChevronRight size={18} />
          <span><ShieldCheck size={21} /> Validator stack</span>
          <ChevronRight size={18} />
          <span><Cpu size={21} /> Native exporter</span>
          <ChevronRight size={18} />
          <span><Download size={21} /> Openable project</span>
        </div>
      </section>

      <section className="landing-native-section">
        <SectionIntro
          eyebrow="Act IV / One circuit, multiple native ecosystems"
          title="Open the result where you already work."
          body="One logical circuit can target multiple native engineering formats. Adding another ecosystem means building its exporter and validation rules, not retraining the intent layer."
        />
        <div className="landing-native-visual">
          <StoryImage src={landingContent.assets.ecosystems} alt="One circuit model branching into schematic, simulation, and project outputs" className="landing-story-image--wide" />
          <div className="landing-file-switcher" role="tablist" aria-label="Native output files" data-landing-reveal>
            {landingContent.files.map((file, index) => (
              <button
                className={activeFile === index ? `is-active is-${file.accent}` : ''}
                type="button"
                role="tab"
                aria-selected={activeFile === index}
                onClick={() => setActiveFile(index)}
                key={file.tool}
              >
                <span>{file.tool}</span>
                <strong>{file.name}</strong>
                <small>{file.extension}</small>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-iteration-section">
        <SectionIntro
          eyebrow="Act V / Structured projects, not one-off generations"
          title="Change a value. Recompile. No second AI request."
          body="Once circuit intent exists as structured data, mechanical edits can stay deterministic: validate the change, rebuild the file, and preserve the original project."
        />
        <ValueRecompileDemo />
      </section>

      <section className="landing-simulation-section">
        <StoryImage src={landingContent.assets.simulation} alt="A small RC circuit connected to an oscilloscope showing a transient response" className="landing-story-image--wide" />
        <div className="landing-simulation-copy" data-landing-reveal>
          <p>Simulation-ready output</p>
          <h2>The setup can travel with the circuit.</h2>
          <span>For supported LTspice projects, simulation directives are compiled into the <code>.asc</code> file. File readiness is not a claim of complete electrical correctness; engineering review still matters.</span>
          <div><Waves size={20} /> .tran 0 50m</div>
        </div>
      </section>

      <section className="landing-product-proof">
        <SectionIntro
          eyebrow="Act VI / The product is already a workspace"
          title="From generation to reusable engineering artifacts."
          body="Generated projects retain target, validation, component, download, serial, and source-JSON context so the work can continue after the first result."
        />
        <div className="landing-product-shots">
          <figure data-landing-reveal>
            <img src={landingContent.assets.productGenerate} alt="ProGenEDA generation workspace" loading="lazy" />
            <figcaption><span>01</span> Intent and JSON enter the generation pipeline.</figcaption>
          </figure>
          <figure data-landing-reveal>
            <img src={landingContent.assets.productHistory} alt="ProGenEDA project history workspace" loading="lazy" />
            <figcaption><span>02</span> Native artifacts remain downloadable and reusable.</figcaption>
          </figure>
        </div>
      </section>

      <section className="landing-difference-section">
        <SectionIntro
          eyebrow="Why this architecture is different"
          title="A compiler layer, not another destination editor."
          body="ProGenEDA is designed to work with existing EDA ecosystems. Its durable asset is the circuit contract plus the exporters and validators that turn it into native files."
        />
        <div className="landing-comparison" role="table" aria-label="Product architecture comparison" data-landing-reveal>
          <div className="landing-comparison__head" role="row">
            <span role="columnheader">Capability</span>
            <span role="columnheader">Generic AI</span>
            <span role="columnheader">Closed editor</span>
            <strong role="columnheader">ProGenEDA</strong>
          </div>
          {landingContent.comparison.map((row) => (
            <div role="row" key={row.capability}>
              <b role="cell" data-label="Capability">{row.capability}</b>
              <span role="cell" data-label="Generic AI">{row.generic}</span>
              <span role="cell" data-label="Closed editor">{row.closed}</span>
              <strong role="cell" data-label="ProGenEDA"><Check size={15} /> {row.progen}</strong>
            </div>
          ))}
        </div>
        <div className="landing-competitive-landscape" data-landing-reveal>
          <header>
            <p>Competitive landscape</p>
            <span>Reference set from the current market brief. Product scopes evolve; this is positioning, not a claim that alternatives lack native-file generation.</span>
          </header>
          {landingContent.competitiveLandscape.map((item, index) => (
            <article key={item.category}>
              <span>0{index + 1}</span>
              <div>
                <small>{item.category}</small>
                <h3>{item.examples}</h3>
                <p>{item.context}</p>
              </div>
              <aside>
                <small>ProGenEDA focus</small>
                <p>{item.focus}</p>
              </aside>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-evidence-section">
        <SectionIntro
          eyebrow="Internal engineering evidence / July 2026"
          title="A validation corpus, not a hand-picked screenshot."
          body="The current KiCad pipeline records project, netlist, pin, geometry, and final validation evidence. These are internal engineering results, not customer-usage metrics."
          invert
        />
        <div className="landing-evidence-grid">
          {landingContent.evidence.map((item) => (
            <article key={item.title} data-landing-reveal>
              <strong>{item.value}</strong>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
        <p className="landing-evidence-note">* PCB generation remains a roadmap layer. Accepted corpus evidence is shown to explain technical potential, not public availability.</p>
      </section>

      <section className="landing-audience-section">
        <SectionIntro
          eyebrow="Where the leverage appears first"
          title="Known circuits. Repeated construction. Real source files."
          body="The wedge is work where the desired circuit is understood, the output format is strict, and rebuilding the project by hand is still costly."
        />
        <div className="landing-audience-grid">
          {landingContent.audiences.map((item, index) => (
            <article key={item.title} data-landing-reveal>
              <span>0{index + 1}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-business-section">
        <SectionIntro
          eyebrow="How the wedge becomes a company"
          title="The same compiler core can move up from projects to infrastructure."
          body="The initial product saves construction time for individual projects. The larger opportunity is a governed circuit-generation layer that teams can reuse across artifacts, variants, tools, and internal workflows."
        />
        <div className="landing-business-ladder">
          {landingContent.businessLayers.map((layer, index) => (
            <article key={layer.stage} data-landing-reveal>
              <span>0{index + 1}</span>
              <div>
                <small>{layer.stage} / {layer.status}</small>
                <h3>{layer.title}</h3>
                <p>{layer.body}</p>
              </div>
              <aside>
                <small>Potential buyers</small>
                <strong>{layer.buyers}</strong>
              </aside>
            </article>
          ))}
        </div>
        <div className="landing-business-model" data-landing-reveal>
          <header>
            <p>Potential revenue surfaces</p>
            <span>No public pricing is implied. These are planned business-model paths as the product matures.</span>
          </header>
          <div>
            {landingContent.businessModel.map((item) => (
              <article key={item.label}>
                <small>{item.label}</small>
                <strong>{item.value}</strong>
                <span>{item.note}</span>
              </article>
            ))}
          </div>
        </div>
        <div className="landing-compounding-loop" data-landing-reveal>
          <span>More accepted circuits</span><ChevronRight size={17} />
          <span>Stronger registries and validators</span><ChevronRight size={17} />
          <span>More native backends</span><ChevronRight size={17} />
          <span>More reusable workflows</span>
        </div>
      </section>

      <section className="landing-roadmap-section" id="roadmap">
        <StoryImage src={landingContent.assets.pcb} alt="A schematic progressing toward a compact USB-C PCB and manufacturing layers" className="landing-story-image--wide" />
        <div className="landing-roadmap-copy" data-landing-reveal>
          <span>Next compiler target / Under work</span>
          <h2>From logical connectivity to a constrained physical board.</h2>
          <p>The same circuit model can extend into a source-backed PCB pipeline without changing the user’s logical circuit.</p>
          <ul>
            {landingContent.roadmap.map((item) => <li key={item}><Check size={16} /> {item}</li>)}
          </ul>
        </div>
      </section>

      <section className="landing-final-cta">
        <div data-landing-reveal>
          <CircuitBoard size={34} />
          <p>The universal compiler layer between circuit intent and engineering tools.</p>
          <h2>Describe the circuit.<br />Get the engineering file.</h2>
          <span>Native, editable, simulatable EDA projects for the tools engineers already use.</span>
          <div>
            <ArrowLink href={landingContent.hero.primaryCta.href}>Request early access</ArrowLink>
            <a href="/login">Open the demo <ArrowRight size={17} /></a>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <LandingBrand />
        <p>Early technical alpha. Built around structured circuits, deterministic exporters, and native engineering files.</p>
        <nav aria-label="Footer navigation">
          <a href="/get-help">Get help</a>
          <a href="/terms-of-service">Terms</a>
          <a href="/privacy-policy">Privacy</a>
          <a href="mailto:request@progeneda.app">Contact</a>
        </nav>
        <span>© {new Date().getFullYear()} ProGenEDA</span>
      </footer>
    </main>
  );
}
