import { ReactNode, useEffect } from 'react';
import legalPolicyText from './progen-legal.txt?raw';

const SITE_ORIGIN = 'https://progeneda.app';

type PageMetaProps = {
  title: string;
  description: string;
  path: string;
  structuredData?: Record<string, unknown>;
};

const setMeta = (selector: string, attribute: 'content' | 'href', value: string) => {
  const element = document.head.querySelector(selector);
  if (element) {
    element.setAttribute(attribute, value);
  }
};

export function PageMeta({ title, description, path, structuredData }: PageMetaProps) {
  useEffect(() => {
    const canonical = `${SITE_ORIGIN}${path}`;
    document.title = title;
    setMeta('meta[name="description"]', 'content', description);
    setMeta('link[rel="canonical"]', 'href', canonical);
    setMeta('meta[property="og:title"]', 'content', title);
    setMeta('meta[property="og:description"]', 'content', description);
    setMeta('meta[property="og:url"]', 'content', canonical);
    setMeta('meta[name="twitter:title"]', 'content', title);
    setMeta('meta[name="twitter:description"]', 'content', description);

    let jsonLd = document.getElementById('page-jsonld');
    if (!jsonLd) {
      jsonLd = document.createElement('script');
      jsonLd.id = 'page-jsonld';
      jsonLd.setAttribute('type', 'application/ld+json');
      document.head.appendChild(jsonLd);
    }

    jsonLd.textContent = JSON.stringify(
      structuredData ?? {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: title,
        description,
        url: canonical,
      },
    );
  }, [description, path, structuredData, title]);

  return null;
}

function SiteHeader() {
  return (
    <header className="content-header">
      <a className="content-brand" href="/" aria-label="ProGenEDA home">
        <img src="/assets/progen-logo-transparent.png" alt="" />
        <span>ProGenEDA</span>
      </a>
      <nav aria-label="Legal and help navigation">
        <a href="/get-help">Get help</a>
        <a href="/prompt-guide">Prompt guide</a>
        <a href="/terms-of-service">Terms</a>
        <a href="/privacy-policy">Privacy</a>
        <a href="/login">Login</a>
      </nav>
    </header>
  );
}

function PageLayout({
  title,
  description,
  path,
  eyebrow,
  children,
  structuredData,
}: PageMetaProps & { eyebrow: string; children: ReactNode }) {
  return (
    <main className="content-page">
      <PageMeta title={title} description={description} path={path} structuredData={structuredData} />
      <SiteHeader />
      <section className="content-hero">
        <p>{eyebrow}</p>
        <h1>{title.replace(' | ProGenEDA', '')}</h1>
        <span>{description}</span>
      </section>
      {children}
    </main>
  );
}

type PolicySection = {
  heading: string;
  blocks: string[];
};

const PRIVACY_HEADING = 'ProGenEDA Privacy Policy';
const COPYRIGHT_HEADING = 'ProGenEDA Copyright and Generated Output Policy';
const privacyStart = legalPolicyText.indexOf(PRIVACY_HEADING);
const copyrightStart = legalPolicyText.indexOf(COPYRIGHT_HEADING);

const termsPolicyText = privacyStart === -1
  ? legalPolicyText.trim()
  : legalPolicyText.slice(0, privacyStart).trim();

const privacyPolicyText = privacyStart === -1
  ? ''
  : legalPolicyText
    .slice(privacyStart, copyrightStart === -1 ? undefined : copyrightStart)
    .trim();

const splitPolicyText = (text: string) => {
  const blocks = text.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  const title = blocks[0] ?? '';
  const sections: PolicySection[] = [];
  const introBlocks: string[] = [];
  let currentSection: PolicySection | null = null;

  blocks.slice(1).forEach((block) => {
    if (/^\d+\.\s+/.test(block)) {
      if (currentSection) {
        sections.push(currentSection);
      }
      currentSection = { heading: block, blocks: [] };
      return;
    }

    if (currentSection) {
      currentSection.blocks.push(block);
    } else {
      introBlocks.push(block);
    }
  });

  if (currentSection) {
    sections.push(currentSection);
  }

  return { title, introBlocks, sections };
};

function renderInlineText(text: string) {
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match = linkPattern.exec(text);

  while (match) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    parts.push(
      <a href={match[2]} key={`${match[2]}-${match.index}`}>
        {match[1]}
      </a>,
    );
    lastIndex = match.index + match[0].length;
    match = linkPattern.exec(text);
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

const isMetadataBlock = (lines: string[]) =>
  lines.length > 1 && lines.every((line) => /^[A-Za-z /]+:/.test(line));

function PolicyBlock({ block }: { block: string }) {
  const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);

  if (isMetadataBlock(lines)) {
    return (
      <dl className="policy-meta">
        {lines.map((line) => {
          const [label, ...valueParts] = line.split(':');
          return (
            <div key={line}>
              <dt>{label}</dt>
              <dd>{renderInlineText(valueParts.join(':').trim())}</dd>
            </div>
          );
        })}
      </dl>
    );
  }

  if (lines.length > 1) {
    return (
      <ul className="policy-list">
        {lines.map((line) => (
          <li key={line}>{renderInlineText(line)}</li>
        ))}
      </ul>
    );
  }

  return <p>{renderInlineText(block)}</p>;
}

function PolicyText({ text }: { text: string }) {
  if (!text) {
    return (
      <div className="content-section-list content-section-list--legal">
        <section className="content-section content-section--policy-title">
          <h2>Loading policy</h2>
          <p>The latest policy text is loading from the ProGenEDA legal source.</p>
        </section>
      </div>
    );
  }

  const policy = splitPolicyText(text);

  return (
    <div className="content-section-list content-section-list--legal">
      <section className="content-section content-section--policy-title">
        <h2>{policy.title}</h2>
        {policy.introBlocks.map((block) => (
          <PolicyBlock block={block} key={block} />
        ))}
      </section>
      {policy.sections.map((section) => (
        <section className="content-section" key={section.heading}>
          <h2>{section.heading}</h2>
          {section.blocks.map((block) => (
            <PolicyBlock block={block} key={block} />
          ))}
        </section>
      ))}
    </div>
  );
}

const helpFaq = [
  {
    question: 'Why did my circuit fail to generate?',
    answer:
      'Your prompt may be missing circuit purpose, input voltage, output voltage, required components, load requirement, or output target.',
  },
  {
    question: 'Why is a component missing?',
    answer:
      'The requested component may not be supported yet. Check supported components and request additional support when needed.',
  },
  {
    question: 'Can I use ProGenEDA with Proteus?',
    answer:
      'Yes. ProGenEDA is designed around schematic and netlist workflows that can support Proteus-oriented circuit creation.',
  },
  {
    question: 'Are AI-generated circuit outputs always correct?',
    answer:
      'No. Always verify electrical safety, values, connections, ratings, and simulation behavior before using generated circuits.',
  },
];

const promptGuideFaq = [
  {
    question: 'What details make a circuit prompt actionable?',
    answer: 'State the circuit purpose, input, required output or load, target EDA tool, and any topology, safety, simulation, or layout constraints.',
  },
  {
    question: 'Can I request an unsupported Proteus component?',
    answer: 'Yes. The visible Proteus list is a compatibility target while its runtime catalogue is being audited, so request the component before relying on an export.',
  },
  {
    question: 'Why is each Proteus IC limited to 15 instances?',
    answer: 'Fifteen is the requested registry target, but live exporter enforcement is still being audited and must not be treated as a release guarantee yet.',
  },
];

function TermsPage() {
  return (
    <PageLayout
      title="Terms of Service | ProGenEDA"
      description="Read the ProGenEDA Terms of Service for accounts, generated circuit outputs, API-key use, quotas, acceptable use, safety disclaimers, and third-party EDA tools."
      path="/terms-of-service"
      eyebrow="Legal"
      structuredData={breadcrumbJsonLd('Terms of Service', '/terms-of-service')}
    >
      <PolicyText text={termsPolicyText} />
    </PageLayout>
  );
}

function PrivacyPage() {
  return (
    <PageLayout
      title="Privacy Policy | ProGenEDA"
      description="Learn how ProGenEDA may collect, use, store, protect, and process account data, circuit prompts, usage counters, API-key metadata, and technical logs."
      path="/privacy-policy"
      eyebrow="Privacy"
      structuredData={breadcrumbJsonLd('Privacy Policy', '/privacy-policy')}
    >
      <PolicyText text={privacyPolicyText} />
    </PageLayout>
  );
}

function HelpPage() {
  return (
    <PageLayout
      title="Get Help with ProGenEDA"
      description="Get help writing better circuit prompts, understanding supported components, fixing generation errors, protecting API keys, validating outputs, and using Proteus-ready results."
      path="/get-help"
      eyebrow="Help Center"
      structuredData={{
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: helpFaq.map((item) => ({
          '@type': 'Question',
          name: item.question,
          acceptedAnswer: {
            '@type': 'Answer',
            text: item.answer,
          },
        })),
      }}
    >
      <div className="content-section-list">
        <section className="content-section content-section--lead">
          <h2>What ProGenEDA Helps With</h2>
          <p>
            ProGenEDA turns natural-language circuit descriptions into structured
            electronic design outputs. Use this help center for prompts, supported
            components, generation errors, API key safety, native EDA output, validation,
            quota usage, and component requests.
          </p>
        </section>

        <section className="content-section">
          <h2>How ProGenEDA Works</h2>
          <ol className="content-steps">
            <li>Prompt: describe the circuit in natural language.</li>
            <li>Plan: enhance and structure the request for generation.</li>
            <li>Place: select supported components and arrange the circuit.</li>
            <li>Wire: route connections or terminals based on the design.</li>
            <li>Validate: check values, placement, requirements, and output quality.</li>
            <li>Output: produce a validated schematic or netlist result.</li>
          </ol>
        </section>

        <section className="content-section">
          <h2>Write Better Circuit Prompts</h2>
          <p>
            Include circuit purpose, input voltage, output voltage, required components,
            preferred topology, current requirement, load type, protection needs,
            simulator target, and special constraints.
          </p>
          <div className="example-box">
            Design a 24V to 5V isolated DC-DC converter with input protection, output
            filtering, and regulated 5V output for a small embedded system.
          </div>
        </section>

        <section className="content-section">
          <h2>Supported Components</h2>
          <p>
            ProGenEDA supports common sources, passive components, diodes, LEDs,
            transistors, MOSFETs, analog/control ICs, logic ICs, displays, protection
            parts, transformers, switches, and terminals.
          </p>
          <ul className="content-tags" aria-label="Supported component examples">
            {['RES', 'CAP', 'DIODE', 'LM741', 'NE555', 'LM317', 'TRANSFORMER', 'FUSE', '74HC08', '74HC32'].map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        </section>

        <section className="content-section">
          <h2>Common Generation Problems</h2>
          <div className="faq-list">
            {helpFaq.map((item) => (
              <article key={item.question}>
                <h3>{item.question}</h3>
                <p>{item.answer}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="content-section">
          <h2>API Key and Quota Safety</h2>
          <p>
            Never share API keys publicly, paste them into screenshots, expose them in
            frontend code, or store them in plain text. Rotate keys if exposed and use
            restricted permissions where possible. The Usage panel shows remaining
            generation quota.
          </p>
        </section>

        <section className="content-section">
          <h2>Contact Support</h2>
          <p>
            For help with prompts, validation, Proteus-ready output, quota issues, or
            component requests, contact{' '}
            <a href="mailto:support@progeneda.app">support@progeneda.app</a>. The
            source help document remains available as <a href="/get-help.txt">plain text</a>.
          </p>
        </section>
      </div>
    </PageLayout>
  );
}

function PromptGuidePage() {
  return (
    <PageLayout
      title="Circuit Prompt Guide | ProGenEDA"
      description="Write precise ProGenEDA circuit prompts for KiCad, EasyEDA Pro, Proteus, and LTspice. Learn the required engineering details and deterministic validation rules."
      path="/prompt-guide"
      eyebrow="Prompt Guide"
      structuredData={{
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: promptGuideFaq.map((item) => ({
          '@type': 'Question',
          name: item.question,
          acceptedAnswer: {
            '@type': 'Answer',
            text: item.answer,
          },
        })),
      }}
    >
      <div className="content-section-list">
        <section className="content-section content-section--lead">
          <h2>Give The Compiler Engineering Intent</h2>
          <p>
            ProGenEDA works best when the request describes what the circuit must
            achieve, the electrical conditions it operates under, and the EDA result
            you expect. A clear prompt reduces avoidable model work and gives the
            deterministic validator useful constraints to check.
          </p>
        </section>

        <section className="content-section">
          <h2>Five Details To Include</h2>
          <ol className="content-steps">
            <li><strong>Purpose:</strong> the job, such as a regulated supply, LED driver, filter, timer, or amplifier.</li>
            <li><strong>Input:</strong> voltage, current, waveform, supply range, and polarity where relevant.</li>
            <li><strong>Output or load:</strong> expected voltage, current, gain, frequency, load, or observable behavior.</li>
            <li><strong>Constraints:</strong> topology, protection, efficiency, noise, size, simulation, and required components.</li>
            <li><strong>Target:</strong> KiCad schematic or PCB, EasyEDA Pro, Proteus, or LTspice when an export target matters.</li>
          </ol>
        </section>

        <section className="content-section">
          <h2>Prompt Template</h2>
          <div className="example-box">
            Design a [purpose] for [target EDA tool]. Input: [source and operating range].
            Output/load: [required behavior]. Topology and components: [required choices].
            Constraints: [protection, simulation, footprint, or validation needs].
          </div>
        </section>

        <section className="content-section">
          <h2>Example Requests</h2>
          <div className="faq-list">
            <article>
              <h3>KiCad regulated supply</h3>
              <p>Design a 12V to 5V regulated supply in KiCad with reverse-polarity protection, a fuse, 500mA output, and input/output capacitors.</p>
            </article>
            <article>
              <h3>Proteus timer</h3>
              <p>Build a Proteus NE555 astable LED blinker from a 9V supply. Use an LED-RED, 1Hz target frequency, a current-limiting resistor, and a switch.</p>
            </article>
            <article>
              <h3>LTspice filter</h3>
              <p>Create an LTspice RC low-pass filter for a 1kHz cutoff with a 1V sine source and a named output node for simulation.</p>
            </article>
          </div>
        </section>

        <section className="content-section">
          <h2>Proteus Catalogue Status</h2>
          <p>
            The visible Proteus list is a versioned compatibility target covering
            sources, passives, diodes, transistors, selected logic and analog ICs,
            displays, protection parts, and switches. Its deterministic exporter and
            requested <strong>15-per-IC</strong> runtime rule are still under audit, so
            do not treat every displayed name as a tested generation guarantee.
          </p>
          <ul className="content-tags" aria-label="Proteus component examples">
            {['RESISTOR', 'CAP', 'DIODE', '1N4007', 'NE555', 'LM741', '74HC08', '74HC86', 'TRAN-2P2S', 'LED-RED'].map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
          <p>Browse the compatibility catalogue in <a href="/supported-components?service=PR">Supported Components</a>.</p>
        </section>

        <section className="content-section">
          <h2>JSON And Deterministic Validation</h2>
          <p>
            Generated projects cross a structured circuit JSON boundary before an EDA
            exporter runs. The JSON Lab permits small guided KiCad, EasyEDA Pro, and LTspice edits while locking
            component kinds, pin maps, net membership, routing contracts, and executable
            targets. Demo and admin accounts can use advanced JSON editing, followed by
            full deterministic validation before regeneration.
          </p>
        </section>

        <section className="content-section">
          <h2>Generation Pipeline</h2>
          <ol className="content-steps">
            <li>Check the prompt, account limits, target, and local reusable artifacts.</li>
            <li>Use deterministic validation and local data before any model call.</li>
            <li>Choose an allowed model tier and provider only when a model is needed.</li>
            <li>Validate structured circuit JSON and route it to the native exporter.</li>
            <li>Store the resulting artifact, history record, component summary, and shareable serial.</li>
          </ol>
        </section>

        <section className="content-section">
          <h2>Prompt Guide FAQ</h2>
          <div className="faq-list">
            {promptGuideFaq.map((item) => (
              <article key={item.question}>
                <h3>{item.question}</h3>
                <p>{item.answer}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </PageLayout>
  );
}

function breadcrumbJsonLd(name: string, path: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      {
        '@type': 'ListItem',
        position: 1,
        name: 'Home',
        item: SITE_ORIGIN,
      },
      {
        '@type': 'ListItem',
        position: 2,
        name,
        item: `${SITE_ORIGIN}${path}`,
      },
    ],
  };
}

export function ContentRoute({ path }: { path: string }) {
  if (path === '/terms-of-service') return <TermsPage />;
  if (path === '/privacy-policy') return <PrivacyPage />;
  if (path === '/get-help') return <HelpPage />;
  if (path === '/prompt-guide') return <PromptGuidePage />;
  return null;
}
