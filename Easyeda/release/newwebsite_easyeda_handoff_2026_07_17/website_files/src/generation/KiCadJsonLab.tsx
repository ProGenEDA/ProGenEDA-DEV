import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  CloseCircle,
  Code1,
  DocumentCode2,
  Edit2,
  InfoCircle,
  Refresh2,
  ShieldTick,
  TickCircle,
  Warning2,
} from 'iconsax-react';
import { apiBaseUrl, apiFetch } from '../backend/apiClient';

type ValidationIssue = {
  path: string;
  message: string;
  level: 'error' | 'warning';
};

type EditorValidation = {
  valid: boolean;
  issues: ValidationIssue[];
  warnings: ValidationIssue[];
};

type EditorField = {
  id: string;
  group: string;
  label: string;
  value: string;
  maxLength: number;
  kind: 'project-title' | 'reference' | 'value' | 'parameter';
  componentIndex?: number;
  componentRef?: string;
  parameter?: string;
  optional?: boolean;
  constraint?: string;
  evidence?: string;
};

type EditorEvidence = {
  sourceDigest: string;
  sourceTopologyDigest: string;
  candidateTopologyDigest: string;
  topologyPreserved: boolean;
  mode: 'guided' | 'advanced';
  locks: string[];
  sources: Array<{ id: string; label: string; source: string; rule: string }>;
};

type EditorAudit = {
  changedFieldIds: string[];
  changedFieldCount: number;
  topologyPreserved: boolean;
} | null;

type EditorDocument = {
  serial: string;
  title: string;
  service?: 'KC' | 'LT' | 'EA';
  editorLabel?: string;
  editorDescription?: string;
  canUseAdvanced: boolean;
  componentCount: number;
  fields: EditorField[];
  validation: EditorValidation;
  evidence?: EditorEvidence;
  audit?: EditorAudit;
  rawMainJson?: Record<string, unknown>;
};

type GenerationResult = {
  status: 'success' | 'failed';
  serial?: string;
  downloadUrl?: string;
  fileName?: string;
  errorMessage?: string;
};

function errorMessageFromResponse(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object') {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  return fallback;
}

async function readJsonResponse(response: Response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return { detail: text };
  }
}

function draftForFields(fields: EditorField[]) {
  return Object.fromEntries(fields.map((field) => [field.id, field.value]));
}

function groupFields(fields: EditorField[]) {
  return fields.reduce<Record<string, EditorField[]>>((groups, field) => {
    const next = groups[field.group] || [];
    next.push(field);
    groups[field.group] = next;
    return groups;
  }, {});
}

export function KiCadJsonLab({
  serial,
  onClose,
  onGenerated,
}: {
  serial: string;
  onClose: () => void;
  onGenerated: () => void;
}) {
  const [document, setDocument] = useState<EditorDocument | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [rawJson, setRawJson] = useState('');
  const [mode, setMode] = useState<'guided' | 'advanced'>('guided');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [validation, setValidation] = useState<EditorValidation | null>(null);
  const [generated, setGenerated] = useState<GenerationResult | null>(null);

  useEffect(() => {
    let alive = true;
    setIsLoading(true);
    setMessage('');
    setGenerated(null);

    apiFetch(`/api/circuits/${encodeURIComponent(serial)}/editor`)
      .then(async (response) => {
        const payload = await readJsonResponse(response);
        if (!response.ok) throw new Error(errorMessageFromResponse(payload, 'Could not load the JSON Lab.'));
        return payload as unknown as EditorDocument;
      })
      .then((payload) => {
        if (!alive) return;
        setDocument(payload);
        setDraft(draftForFields(payload.fields));
        setRawJson(payload.rawMainJson ? JSON.stringify(payload.rawMainJson, null, 2) : '');
        setValidation(payload.validation);
      })
      .catch((error) => {
        if (alive) setMessage(error instanceof Error ? error.message : 'Could not load the JSON Lab.');
      })
      .finally(() => {
        if (alive) setIsLoading(false);
      });

    return () => { alive = false; };
  }, [serial]);

  const changes = useMemo(() => {
    if (!document) return [];
    return document.fields
      .filter((field) => draft[field.id] !== field.value)
      .map((field) => ({ id: field.id, value: draft[field.id] ?? '' }));
  }, [document, draft]);

  const fieldsByGroup = useMemo(() => groupFields(document?.fields || []), [document]);

  const buildPayload = () => {
    if (mode === 'advanced') {
      let mainJson: unknown;
      try {
        mainJson = JSON.parse(rawJson);
      } catch {
        throw new Error('Advanced JSON must be valid JSON before it can be checked.');
      }
      if (!mainJson || typeof mainJson !== 'object' || Array.isArray(mainJson)) {
        throw new Error('Advanced JSON must contain one circuit object.');
      }
      return { mode: 'advanced', mainJson };
    }
    if (!changes.length) throw new Error('Change a guided field before validating or regenerating.');
    return { mode: 'guided', changes };
  };

  const validate = async () => {
    if (!document) return null;
    setIsSaving(true);
    setMessage('');

    try {
      const payload = buildPayload();
      const response = await apiFetch(`/api/circuits/${encodeURIComponent(serial)}/editor/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await readJsonResponse(response);
      if (!response.ok) {
        const issues = Array.isArray(responsePayload.issues) ? responsePayload.issues as ValidationIssue[] : [];
        setValidation({ valid: false, issues, warnings: [] });
        throw new Error(errorMessageFromResponse(responsePayload, 'The edited JSON did not pass validation.'));
      }
      const next = responsePayload as unknown as EditorDocument;
      setDocument((current) => current ? { ...current, ...next } : next);
      setDraft(draftForFields(next.fields));
      if (next.rawMainJson) setRawJson(JSON.stringify(next.rawMainJson, null, 2));
      setValidation(next.validation);
      setMessage(next.validation.valid ? 'Deterministic validation passed.' : 'Validation needs attention.');
      return payload;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Validation failed.');
      return null;
    } finally {
      setIsSaving(false);
    }
  };

  const onGenerate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!document) return;
    setIsSaving(true);
    setMessage('');
    setGenerated(null);

    try {
      const payload = buildPayload();
      const response = await apiFetch(`/api/circuits/${encodeURIComponent(serial)}/editor/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, routingMode: document.service === 'LT' ? 'wire' : 'combination' }),
      });
      const result = await readJsonResponse(response) as unknown as GenerationResult;
      if (!response.ok || result.status !== 'success') {
        throw new Error(result.errorMessage || errorMessageFromResponse(result, 'Edited project generation failed.'));
      }
      setGenerated(result);
      setMessage(`A new serial was created from your validated ${document.editorLabel || 'CircuitIR'} JSON.`);
      onGenerated();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Edited project generation failed.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="json-lab-overlay" role="presentation">
      <section className="json-lab" role="dialog" aria-modal="true" aria-labelledby="json-lab-title">
        <header className="json-lab__header">
          <div>
            <span><DocumentCode2 size={20} /> {document?.editorLabel || 'Circuit JSON Lab'}</span>
            <h2 id="json-lab-title">{document?.title || 'Loading circuit editor'}</h2>
            <p>{document?.editorDescription || 'Safe edits preserve topology. Pins, nets, component kinds, and type mappings remain locked in guided mode.'}</p>
          </div>
          <button type="button" aria-label="Close JSON Lab" onClick={onClose}><CloseCircle size={23} /></button>
        </header>

        {isLoading && <div className="json-lab__loading"><Refresh2 size={24} /> Loading canonical CircuitIR…</div>}

        {!isLoading && document && (
          <>
            <div className="json-lab__toolbar">
              <div className="json-lab__tabs" role="tablist" aria-label="Editor mode">
                <button
                  type="button"
                  className={mode === 'guided' ? 'is-active' : ''}
                  onClick={() => setMode('guided')}
                  role="tab"
                  aria-selected={mode === 'guided'}
                >
                  <Edit2 size={17} /> Guided edit
                </button>
                <button
                  type="button"
                  className={mode === 'advanced' ? 'is-active' : ''}
                  onClick={() => document.canUseAdvanced && setMode('advanced')}
                  disabled={!document.canUseAdvanced}
                  title={document.canUseAdvanced ? 'Edit canonical JSON directly' : 'Advanced JSON is available to demo and admin accounts.'}
                  role="tab"
                  aria-selected={mode === 'advanced'}
                >
                  <Code1 size={17} /> Advanced JSON
                </button>
              </div>
              <span><ShieldTick size={17} /> {document.componentCount} components · deterministic validation</span>
            </div>

            {document.evidence && (
              <section className="json-lab__evidence" aria-label="Deterministic editing evidence">
                <div>
                  <span><ShieldTick size={17} /> Evidence-backed edit boundary</span>
                  <p>{document.evidence.mode === 'guided'
                    ? (document.evidence.topologyPreserved ? 'Topology fingerprint preserved.' : 'Topology fingerprint changed.')
                    : 'Advanced mode permits topology changes, then validates the full CircuitIR contract.'}</p>
                </div>
                <dl>
                  <div><dt>Source digest</dt><dd>{document.evidence.sourceDigest.slice(0, 16)}</dd></div>
                  <div><dt>Locked in guided mode</dt><dd>{document.evidence.locks.length}</dd></div>
                  <div><dt>Checks</dt><dd>{document.evidence.sources.length}</dd></div>
                </dl>
                <ul>
                  {document.evidence.sources.map((source) => <li key={source.id} title={source.source}>{source.label}</li>)}
                </ul>
              </section>
            )}

            <form className="json-lab__form" onSubmit={onGenerate}>
              <div className="json-lab__editor">
                {mode === 'guided' ? (
                  <div className="json-lab__fields">
                    {Object.entries(fieldsByGroup).map(([group, fields]) => (
                      <section key={group} className="json-lab__field-group">
                        <h3>{group}</h3>
                        <div>
                          {fields.map((field) => (
                            <label key={field.id}>
                              <span title={field.constraint}>{field.componentRef ? `${field.componentRef} · ` : ''}{field.label}</span>
                              <input
                                value={draft[field.id] ?? ''}
                                maxLength={field.maxLength}
                                onChange={(event) => setDraft((current) => ({ ...current, [field.id]: event.target.value }))}
                              />
                              {field.constraint && <small>{field.constraint}</small>}
                            </label>
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                ) : (
                  <label className="json-lab__raw-field">
                    <span><Code1 size={17} /> Canonical CircuitIR JSON</span>
                    <textarea value={rawJson} spellCheck={false} onChange={(event) => setRawJson(event.target.value)} />
                  </label>
                )}
              </div>

              <aside className="json-lab__validation" aria-live="polite">
                <h3>{validation?.valid ? <TickCircle size={20} /> : <Warning2 size={20} />} Validation</h3>
                {validation?.valid ? <p>Current circuit structure is valid.</p> : <p>Resolve deterministic validation errors before generation.</p>}
                <ul>
                  {(validation?.issues || []).slice(0, 8).map((issue) => <li key={`${issue.path}-${issue.message}`}><strong>{issue.path}</strong>{issue.message}</li>)}
                  {(validation?.warnings || []).slice(0, 5).map((warning) => <li className="is-warning" key={`${warning.path}-${warning.message}`}><strong>{warning.path}</strong>{warning.message}</li>)}
                  {!validation?.issues?.length && !validation?.warnings?.length && <li className="is-clean"><InfoCircle size={16} /> No structural issues found.</li>}
                </ul>
              </aside>

              <footer className="json-lab__footer">
                <p>{message || `Changes are validated deterministically before the ${document.service === 'LT' ? 'LTspice donor-native' : document.service === 'EA' ? 'EasyEDA donor-native' : 'KiCad'} executable runs.`}</p>
                <div>
                  <button type="button" onClick={() => void validate()} disabled={isSaving}><ShieldTick size={17} /> Validate</button>
                  <button type="submit" disabled={isSaving}><Refresh2 size={17} /> {isSaving ? 'Working…' : 'Generate edited project'}</button>
                </div>
              </footer>
            </form>

            {generated?.downloadUrl && (
              <div className="json-lab__result">
                <TickCircle size={20} />
                <span>New serial: <strong>{generated.serial}</strong></span>
                <a href={`${apiBaseUrl()}${generated.downloadUrl}`} download={generated.fileName || undefined}>Download edited project</a>
              </div>
            )}
          </>
        )}

        {!isLoading && !document && <div className="json-lab__error"><Warning2 size={20} /> {message || 'The JSON Lab could not be opened.'}</div>}
      </section>
    </div>
  );
}
