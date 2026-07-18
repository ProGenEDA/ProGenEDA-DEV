const DEFAULT_API_URL = 'http://127.0.0.1:3000';
export type GenerationResult = {
  blob?: Blob;
  downloadUrl?: string;
  serial?: string | null;
  fileName: string;
  mode: string;
};
type BackendGenerationResponse = {
  serial: string | null;
  status: 'success' | 'failed';
  errorMessage?: string;
  downloadUrl?: string;
  fileName?: string;
};

export type GenerationTargetService = 'PR' | 'KC' | 'LT' | 'EA';
export type RoutingMode = 'wire' | 'terminal' | 'combination';
export type DirectJsonBatchItem = {
  name: string;
  mainJson: Record<string, unknown>;
  prompt?: string;
};

type GenerationRequestOptions = {
  targetService?: GenerationTargetService;
  mainJson?: Record<string, unknown>;
  routingMode?: RoutingMode;
  animationBudgetSeconds?: number;
  signal?: AbortSignal;
};

export type GeneratorProgressEvent = {
  event?: string;
  stage?: string;
  state?: string;
  message?: string;
  percent?: number;
  detail?: string;
  [key: string]: unknown;
};

function defaultFileName(targetService: GenerationTargetService | undefined) {
  if (targetService === 'KC') return 'PROGEN_KICAD_PROJECT.zip';
  if (targetService === 'LT') return 'PROGENEDA_LTSPICE.asc';
  if (targetService === 'EA') return 'PROGENEDA_EASYEDA.eprj';
  return 'PROGEN_OUTPUT.pdsprj';
}

function defaultRoutingMode(targetService: GenerationTargetService | undefined): RoutingMode {
  return targetService === 'LT' ? 'wire' : 'combination';
}

function readHeaderFileName(disposition: string | null) {
  if (!disposition) return null;

  const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1].trim());

  const regularMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (regularMatch?.[1]) return regularMatch[1].trim();

  return null;
}

async function readErrorDetail(response: Response) {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    try {
      const payload = await response.json() as { detail?: unknown; message?: unknown };
      const detail = payload.detail || payload.message;
      if (typeof detail === 'string' && detail.trim()) return detail;
    } catch {
      return `Generation failed with HTTP ${response.status}.`;
    }
  }

  const text = await response.text();
  return text.trim() || `Generation failed with HTTP ${response.status}.`;
}

function readTempSessionHeaders() {
  const headers: Record<string, string> = {};
  const rawSession = window.localStorage.getItem('progeneda.tempSession')
    || window.sessionStorage.getItem('progeneda.tempSession');

  if (!rawSession) return headers;

  try {
    const session = JSON.parse(rawSession) as { email?: string; displayName?: string; plan?: string; role?: string; id?: string };
    if (session.email) headers['X-ProGenEDA-User-Email'] = session.email;
    if (session.displayName) headers['X-ProGenEDA-Display-Name'] = session.displayName;
    if (session.plan) headers['X-ProGenEDA-Plan'] = session.plan;
    if (session.role) headers['X-ProGenEDA-Role'] = session.role;
    if (session.id) headers['X-ProGenEDA-User-Id'] = session.id;
  } catch {
    return headers;
  }

  return headers;
}

export async function generateCircuit(
  prompt: string,
  options: GenerationRequestOptions = {},
): Promise<GenerationResult> {
  const apiBaseUrl = import.meta.env.VITE_PROGEN_API_URL || DEFAULT_API_URL;
  const endpoint = `${apiBaseUrl.replace(/\/$/, '')}/api/generate`;
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...readTempSessionHeaders(),
    },
    body: JSON.stringify({
      prompt,
      targetService: options.targetService || 'PR',
      mainJson: options.mainJson,
      routingMode: options.routingMode || defaultRoutingMode(options.targetService),
    }),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const payload = await response.json() as BackendGenerationResponse;

    if (payload.status !== 'success' || !payload.downloadUrl) {
      throw new Error(payload.errorMessage || 'Generation failed.');
    }

    return {
      downloadUrl: `${apiBaseUrl.replace(/\/$/, '')}${payload.downloadUrl}`,
      serial: payload.serial,
      fileName: payload.fileName
        || defaultFileName(options.targetService),
      mode: 'backend-local-production',
    };
  }

  const blob = await response.blob();
  const fileName = readHeaderFileName(response.headers.get('content-disposition')) || defaultFileName(options.targetService);
  const mode = response.headers.get('x-progeneda-circuit-mode') || 'unknown';

  return {
    blob,
    fileName,
    mode,
  };
}

export async function generateWithExecutableProgress(
  prompt: string,
  options: GenerationRequestOptions & { onProgress?: (event: GeneratorProgressEvent) => void } = {},
): Promise<GenerationResult> {
  const apiBaseUrl = import.meta.env.VITE_PROGEN_API_URL || DEFAULT_API_URL;
  const targetService = options.targetService || 'LT';
  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/generate/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...readTempSessionHeaders(),
    },
    body: JSON.stringify({
      prompt,
      targetService,
      mainJson: options.mainJson,
      routingMode: options.routingMode || defaultRoutingMode(targetService),
      animationBudgetSeconds: options.animationBudgetSeconds,
    }),
    signal: options.signal,
  });

  if (!response.ok) throw new Error(await readErrorDetail(response));
  if (!response.body) throw new Error('The EDA executable did not open a progress stream.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = '';
  let result: BackendGenerationResponse | null = null;
  let streamError = '';

  const consumeLine = (line: string) => {
    const text = line.trim();
    if (!text) return;
    let event: GeneratorProgressEvent;
    try {
      event = JSON.parse(text) as GeneratorProgressEvent;
    } catch {
      return;
    }
    if (event.event === 'result' && event.result && typeof event.result === 'object') {
      result = event.result as BackendGenerationResponse;
      return;
    }
    if (event.event === 'error') {
      streamError = typeof event.detail === 'string' ? event.detail : 'EDA executable progress stream failed.';
      return;
    }
    options.onProgress?.(event);
  };

  while (true) {
    const { value, done } = await reader.read();
    buffered += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffered.split(/\r?\n/);
    buffered = lines.pop() || '';
    lines.forEach(consumeLine);
    if (done) break;
  }
  buffered += decoder.decode();
  consumeLine(buffered);

  if (streamError) throw new Error(streamError);
  // TypeScript cannot follow the assignment performed inside consumeLine().
  const finalResult = result as BackendGenerationResponse | null;
  if (!finalResult || finalResult.status !== 'success' || !finalResult.downloadUrl) {
    throw new Error(finalResult?.errorMessage || 'Generation failed before a downloadable native project was released.');
  }

  return {
    downloadUrl: `${apiBaseUrl.replace(/\/$/, '')}${finalResult.downloadUrl}`,
    serial: finalResult.serial,
    fileName: finalResult.fileName || defaultFileName(targetService),
    mode: 'backend-executable-progress',
  };
}

export async function generateJsonBatch({
  items,
  targetService,
  routingMode = 'combination',
  signal,
}: {
  items: DirectJsonBatchItem[];
  targetService: GenerationTargetService;
  routingMode?: RoutingMode;
  signal?: AbortSignal;
}): Promise<GenerationResult> {
  const apiBaseUrl = import.meta.env.VITE_PROGEN_API_URL || DEFAULT_API_URL;
  const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/generate/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...readTempSessionHeaders(),
    },
    body: JSON.stringify({ items, targetService, routingMode: targetService === 'LT' ? 'wire' : routingMode }),
    signal,
  });

  if (!response.ok) throw new Error(await readErrorDetail(response));

  const blob = await response.blob();
  return {
    blob,
    fileName: readHeaderFileName(response.headers.get('content-disposition')) || 'PROGENEDA_CIRCUIT_BATCH.zip',
    mode: 'backend-batch-json',
  };
}
