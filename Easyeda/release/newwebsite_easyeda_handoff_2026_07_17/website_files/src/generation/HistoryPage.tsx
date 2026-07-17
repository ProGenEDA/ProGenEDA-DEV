import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArchiveTick,
  Box,
  Calendar,
  Chart21,
  CloseCircle,
  Clock,
  CloudConnection,
  Copy,
  Danger,
  DocumentDownload,
  Edit2,
  More,
  Notification,
  SearchNormal1,
  StatusUp,
  TickCircle,
  Trash,
} from 'iconsax-react';
import { AuthSession } from '../auth/authProvider';
import { PageMeta } from '../contentPages';
import { apiBaseUrl, apiFetch } from '../backend/apiClient';
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

const TEMP_SESSION_KEY = 'progeneda.tempSession';

type HistoryCard = {
  id: string;
  serial: string | null;
  title: string;
  description: string;
  service: string;
  serviceCode: string;
  status: 'success' | 'failed' | 'running' | 'deleted' | 'disabled';
  createdAt: string;
  componentCount: number;
  uniqueUserDownloads: number;
  totalDownloads: number;
  sharedReuseCount: number;
  copySerialCount: number;
  canDownload: boolean;
  canCopySerial: boolean;
  errorMessage: string;
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

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function TargetBadge({ service, serviceCode }: { service: string; serviceCode: string }) {
  const logoByServiceCode: Record<string, string> = {
    PR: '/assets/proteus.png',
    PS: '/assets/pspice-for-ti-logo.png',
    KC: '',
    LT: '/assets/ltspice.png',
    EA: '/assets/easyeda-pro.png',
    AL: '/assets/altium-icon.svg',
  };
  const logoSrc = logoByServiceCode[serviceCode];

  return (
    <span className="history-item__target">
      <span className="history-item__target-mark" aria-hidden="true">
        {logoSrc ? <img src={logoSrc} alt="" /> : serviceCode === 'KC' ? 'Ki' : serviceCode.slice(0, 2)}
      </span>
      {service}
    </span>
  );
}

function formatCount(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

async function copyTextToClipboard(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    const input = document.createElement('textarea');
    input.value = value;
    input.setAttribute('readonly', '');
    input.style.position = 'fixed';
    input.style.left = '-9999px';
    document.body.appendChild(input);
    input.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(input);
    return copied;
  }
}

function HistoryInsights({ items, visibleItems }: { items: HistoryCard[]; visibleItems: HistoryCard[] }) {
  const successful = items.filter((item) => item.status === 'success');
  const failed = items.filter((item) => item.status === 'failed');
  const downloads = items.reduce((total, item) => total + item.totalDownloads, 0);
  const sharedReuses = items.reduce((total, item) => total + item.sharedReuseCount, 0);
  const componentCount = items.reduce((total, item) => total + item.componentCount, 0);
  const successRate = items.length ? Math.round((successful.length / items.length) * 100) : 0;
  const lastSuccessful = successful[0];
  const latestFailure = failed[0];
  const activeServices = [...new Set(successful.map((item) => item.service))];

  return (
    <aside className="history-insights" aria-label="History insights">
      <section className="history-insight-card history-insight-card--overview">
        <div className="history-insight-card__heading">
          <span><Chart21 size={20} /> Overview</span>
          <small>{formatCount(visibleItems.length)} shown</small>
        </div>

        <dl className="history-overview-metrics">
          <div>
            <dd>{formatCount(items.length)}</dd>
            <dt>Total</dt>
          </div>
          <div>
            <dd>{successRate}%</dd>
            <dt>Success</dt>
          </div>
          <div>
            <dd>{formatCount(failed.length)}</dd>
            <dt>Failed</dt>
          </div>
          <div>
            <dd>{formatCount(componentCount)}</dd>
            <dt>Parts</dt>
          </div>
        </dl>
      </section>

      <section className="history-insight-card">
        <div className="history-insight-card__heading">
          <span><StatusUp size={20} /> Serial Reuse</span>
          <small>Local</small>
        </div>
        <div className="history-reuse-meter">
          <span style={{ width: `${Math.min(100, Math.max(8, sharedReuses * 12))}%` }} />
        </div>
        <dl className="history-insight-list">
          <div>
            <dt>Downloads served</dt>
            <dd>{formatCount(downloads)}</dd>
          </div>
          <div>
            <dt>Shared reuses</dt>
            <dd>{formatCount(sharedReuses)}</dd>
          </div>
          <div>
            <dt>AI calls avoided</dt>
            <dd>{formatCount(sharedReuses)}</dd>
          </div>
        </dl>
      </section>

      <section className="history-insight-card">
        <div className="history-insight-card__heading">
          <span><CloudConnection size={20} /> Export Readiness</span>
          <small>{activeServices.length === 1 ? activeServices[0] : 'EDA exports'}</small>
        </div>
        <div className="history-ready-row">
          <ArchiveTick size={22} />
          <div>
            <strong>{formatCount(successful.length)} downloadable</strong>
            <span>Export artifacts are separated from internal bundles.</span>
          </div>
        </div>
        <div className="history-ready-row">
          <Box size={22} />
          <div>
            <strong>{lastSuccessful?.serial || 'No serial yet'}</strong>
            <span>Latest reusable serial registry entry.</span>
          </div>
        </div>
      </section>

      <section className="history-insight-card">
        <div className="history-insight-card__heading">
          <span><Danger size={20} /> Failure Watch</span>
          <small>{formatCount(failed.length)} open</small>
        </div>
        <div className="history-ready-row history-ready-row--danger">
          <Danger size={22} />
          <div>
            <strong>{latestFailure?.title || 'No failed exports'}</strong>
            <span>{latestFailure?.errorMessage || 'Generation checks are clear for the current history view.'}</span>
          </div>
        </div>
      </section>
    </aside>
  );
}

function HistoryItem({
  item,
  onCardUpdate,
  onDeleted,
  onOpenEditor,
}: {
  item: HistoryCard;
  onCardUpdate: (card: HistoryCard) => void;
  onDeleted: (id: string) => void;
  onOpenEditor: (serial: string) => void;
}) {
  const [showError, setShowError] = useState(item.status === 'failed');
  const [copied, setCopied] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [copyPending, setCopyPending] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const isSuccess = item.status === 'success';
  const canEdit = isSuccess && ['KC', 'LT', 'EA'].includes(item.serviceCode) && Boolean(item.serial);

  const onCopy = async () => {
    if (!item.serial || copyPending) return;
    setCopyPending(true);

    try {
      await copyTextToClipboard(item.serial);
      const response = await apiFetch(`/api/circuits/${encodeURIComponent(item.serial)}/copy-serial`, { method: 'POST' });
      if (response.ok) {
        const payload = await response.json() as { historyCard?: HistoryCard };
        if (payload.historyCard) onCardUpdate(payload.historyCard);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } finally {
      setCopyPending(false);
    }
  };

  const onDelete = async () => {
    if (deletePending) return;
    setDeletePending(true);

    try {
      const deletePath = item.serial
        ? `/api/circuits/${encodeURIComponent(item.serial)}`
        : `/api/history/${encodeURIComponent(item.id)}`;
      const response = await apiFetch(deletePath, { method: 'DELETE' });
      if (!response.ok) throw new Error('Could not delete history item.');
      onDeleted(item.id);
    } finally {
      setDeletePending(false);
      setMenuOpen(false);
    }
  };

  return (
    <article className={`history-item ${isSuccess ? 'is-success' : 'is-failed'}${showError && !isSuccess ? ' has-error-details' : ''}`}>
      <span className="history-item__rail" />
      <div className="history-item__status">
        <span>
          {isSuccess ? <TickCircle variant="Bold" size={22} /> : <CloseCircle variant="Bold" size={22} />}
        </span>
      </div>
      <div className="history-item__body">
        <div className="history-item__topline">
          <h2>{item.title}</h2>
          <TargetBadge service={item.service} serviceCode={item.serviceCode} />
        </div>
        <p>{item.description}</p>
        <div className="history-item__meta">
          <span><Clock size={16} /> {formatDate(item.createdAt)}</span>
          <span><Box size={15} /> {item.componentCount} components</span>
          {item.serial && (
            <button type="button" onClick={onCopy} disabled={copyPending}>
              <Copy size={15} /> {copied ? 'Copied' : 'Copy serial'}
            </button>
          )}
          {item.sharedReuseCount > 0 && <span><StatusUp size={15} /> {item.sharedReuseCount} shared reuses</span>}
        </div>
        {showError && !isSuccess && (
          <div className="history-error">
            <strong>Error Details</strong>
            <p>{item.errorMessage || 'Generation failed before export.'}</p>
          </div>
        )}
      </div>
      <div className="history-item__actions">
        <div className="history-item__action-row">
          <strong className={isSuccess ? 'is-success' : 'is-failed'}>
            {isSuccess ? <TickCircle size={15} /> : <CloseCircle size={15} />}
            {isSuccess ? 'Success' : 'Failed'}
          </strong>
          <div className="history-menu-shell">
            <button
              className="history-more"
              type="button"
              aria-label="More actions"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((current) => !current)}
            >
              <More size={21} />
            </button>
            {menuOpen && (
              <div className="history-menu" role="menu">
                <button type="button" role="menuitem" onClick={onDelete} disabled={deletePending}>
                  <Trash size={16} />
                  {deletePending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            )}
          </div>
        </div>
        {isSuccess && item.serial ? (
          <div className="history-item__buttons">
            <a href={`${apiBaseUrl()}/api/download/export/${encodeURIComponent(item.serial)}?source=owner_history`} download>
              <DocumentDownload size={19} />
              Download
            </a>
            <button
              type="button"
              onClick={() => canEdit && onOpenEditor(item.serial as string)}
              disabled={!canEdit}
              title={canEdit ? `Open ${item.service} JSON Lab` : 'JSON editing is not available for this generator.'}
            >
              <Edit2 size={17} />
              {canEdit ? 'Edit JSON' : 'Editor pending'}
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setShowError((current) => !current)}>
            <Danger size={18} />
            View Error
          </button>
        )}
      </div>
    </article>
  );
}

export function HistoryPage() {
  const [session] = useState(() => readStoredSession());
  const [generationMode, setGenerationMode] = useState(() => readStoredGenerationMode());
  const [items, setItems] = useState<HistoryCard[]>([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [serviceFilter, setServiceFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [editorSerial, setEditorSerial] = useState<string | null>(null);
  const sidebarAutoHide = useSidebarAutoHide();
  const updateGenerationMode = (nextMode: GenerationMode) => {
    setGenerationMode(nextMode);
    writeStoredGenerationMode(nextMode);
  };

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await apiFetch(`/api/history?status=${statusFilter}&service=${serviceFilter}&limit=10`);
      if (!response.ok) throw new Error('History API is unavailable.');
      const payload = await response.json() as { items: HistoryCard[] };
      setItems(payload.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load history.');
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, serviceFilter]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const updateHistoryCard = useCallback((card: HistoryCard) => {
    setItems((currentItems) => currentItems.map((item) => (item.id === card.id ? card : item)));
  }, []);

  const removeHistoryCard = useCallback((id: string) => {
    setItems((currentItems) => currentItems.filter((item) => item.id !== id));
  }, []);

  const visibleItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return items;
    return items.filter((item) => (
      item.title.toLowerCase().includes(query)
      || item.description.toLowerCase().includes(query)
      || item.serial?.toLowerCase().includes(query)
    ));
  }, [items, search]);

  return (
    <main className={`generate-page history-page ${sidebarAutoHide.isSidebarHidden ? 'is-sidebar-collapsed' : ''}`}>
      <PageMeta
        title="Circuit History | ProGenEDA"
        description="View generated ProGenEDA circuit history, serials, status, download actions, and generation error details."
        path="/history"
      />
      <GenerationSidebar
        session={session}
        activePath="/history"
        motionMode={generationMode.motion}
        themeMode={generationMode.theme}
        onMotionModeChange={(nextMotionMode) => updateGenerationMode({ ...generationMode, motion: nextMotionMode })}
        onThemeModeChange={(nextThemeMode) => updateGenerationMode({ ...generationMode, theme: nextThemeMode })}
        autoHideSidebar={sidebarAutoHide.isAutoHideEnabled}
        onAutoHideSidebarChange={sidebarAutoHide.setAutoHideEnabled}
        interactionProps={sidebarAutoHide.sidebarInteractionProps}
      />
      <SidebarRevealZone {...sidebarAutoHide.revealZoneProps} />

      <section className="generate-workspace history-workspace" aria-label="ProGenEDA circuit history">
        <div className="generate-topbar" aria-label="Generation status">
          <span><i /> All systems operational</span>
          <button type="button" aria-label="Notifications"><Notification size={20} /></button>
        </div>

        <div className="history-shell">
          <header className="history-header">
            <h1>History</h1>
            <p>View and manage your past generations.</p>
          </header>

          <div className="history-controls">
            <label>
              <SearchNormal1 size={22} />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search prompts, projects, or components..."
              />
            </label>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All Status</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
            </select>
            <select value={serviceFilter} onChange={(event) => setServiceFilter(event.target.value)}>
              <option value="all">All Targets</option>
              <option value="PR">Proteus</option>
              <option value="KC">KiCad</option>
              <option value="LT">LTspice</option>
              <option value="EA">EasyEDA Pro</option>
            </select>
            <button type="button" aria-label="Pick date"><Calendar size={22} /></button>
          </div>

          {error && <div className="history-empty is-error">{error}</div>}
          {isLoading && <div className="history-empty">Loading history...</div>}
          {!isLoading && !error && visibleItems.length === 0 && (
            <div className="history-empty">
              <strong>No generations yet</strong>
              <p>Generate a circuit and it will appear here with serial, download, and status metadata.</p>
            </div>
          )}

          <div className="history-content-grid">
            <div className="history-results-column">
              <div className="history-list">
                {visibleItems.map((item) => (
                  <HistoryItem
                    item={item}
                    key={item.id}
                    onCardUpdate={updateHistoryCard}
                    onDeleted={removeHistoryCard}
                    onOpenEditor={setEditorSerial}
                  />
                ))}
              </div>

              {visibleItems.length > 0 && (
                <footer className="history-footer">
                  <span>Showing 1 to {visibleItems.length} of {items.length} results</span>
                  <div>
                    <button type="button" disabled>‹</button>
                    <button type="button" className="is-active">1</button>
                    <button type="button" disabled>›</button>
                  </div>
                  <select defaultValue="10">
                    <option value="10">10 per page</option>
                    <option value="20">20 per page</option>
                  </select>
                </footer>
              )}
            </div>

            <HistoryInsights items={items} visibleItems={visibleItems} />
          </div>
        </div>
        {editorSerial && (
          <KiCadJsonLab
            serial={editorSerial}
            onClose={() => setEditorSerial(null)}
            onGenerated={() => { void loadHistory(); }}
          />
        )}
      </section>
    </main>
  );
}
