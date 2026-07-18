import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function loadLocalEnv(path) {
  if (!existsSync(path)) return;

  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const [rawKey, ...rawValueParts] = trimmed.split('=');
    const key = rawKey.trim();
    const value = rawValueParts.join('=').trim().replace(/^['"]|['"]$/g, '');
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
}

loadLocalEnv(resolve(process.cwd(), 'api.env'));

const superAdminUserIds = (
  process.env.PROGEN_SUPER_ADMIN_USER_IDS
  || process.env.SUPER_ADMIN_USER_IDS
  || 'user_local_tahabinzaeem0'
)
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);

export const config = {
  port: Number(process.env.PROGEN_API_PORT || 3000),
  frontendOrigin: process.env.PROGEN_FRONTEND_ORIGIN || 'http://localhost:5175',
  kicadExecutablePath: resolve(
    process.env.PROGEN_KICAD_EXECUTABLE_PATH
      || 'vendor/kicad/progen-kicad-portable/progen-kicad',
  ),
  kicadWorkDir: resolve(
    process.env.PROGEN_KICAD_WORK_DIR
      || 'local-data/kicad-runs',
  ),
  kicadPlannerUrl: process.env.PROGEN_KICAD_PLANNER_URL || '',
  kicadPlannerApiKey: process.env.PROGEN_KICAD_PLANNER_API_KEY || '',
  kicadPlannerModel: process.env.PROGEN_KICAD_PLANNER_MODEL || '',
  // The provider stays deliberately disabled until an owner configures it.
  // API keys are read only on the server and are never exposed to the client.
  aiProvider: String(process.env.PROGEN_AI_PROVIDER || 'disabled').trim().toLowerCase(),
  openAiApiKey: process.env.PROGEN_OPENAI_API_KEY || process.env.OPENAI_API_KEY || '',
  openAiModel: process.env.PROGEN_OPENAI_MODEL || 'gpt-5-mini',
  openAiBaseUrl: String(process.env.PROGEN_OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, ''),
  openAiTimeoutMs: Math.min(120_000, Math.max(5_000, Number(process.env.PROGEN_OPENAI_TIMEOUT_MS || 45_000))),
  openAiMaxOutputTokens: Math.min(24_000, Math.max(500, Number(process.env.PROGEN_OPENAI_MAX_OUTPUT_TOKENS || 8_000))),
  aiTestWindowMs: Math.min(3_600_000, Math.max(60_000, Number(process.env.PROGEN_AI_TEST_WINDOW_MS || 600_000))),
  aiTestMaxRequests: Math.min(20, Math.max(1, Number(process.env.PROGEN_AI_TEST_MAX_REQUESTS || 5))),
  ltspiceExecutablePath: resolve(
    process.env.PROGEN_LTSPICE_EXECUTABLE_PATH
      || 'vendor/ltspice/progen-ltspice-portable/progen-ltspice',
  ),
  ltspiceWorkDir: resolve(
    process.env.PROGEN_LTSPICE_WORK_DIR
      || 'local-data/ltspice-runs',
  ),
  ltspiceExampleLibraryDir: resolve(
    process.env.PROGEN_LTSPICE_EXAMPLE_LIBRARY_DIR
      || 'vendor/ltspice/common-circuits-100/ltspice_common_circuit_bundle',
  ),
  ltspicePlannerUrl: process.env.PROGEN_LTSPICE_PLANNER_URL || '',
  ltspicePlannerApiKey: process.env.PROGEN_LTSPICE_PLANNER_API_KEY || '',
  ltspicePlannerModel: process.env.PROGEN_LTSPICE_PLANNER_MODEL || '',
  easyedaExecutablePath: resolve(
    process.env.PROGEN_EASYEDA_EXECUTABLE_PATH
      || 'vendor/easyeda/progen-easyeda',
  ),
  easyedaWorkDir: resolve(
    process.env.PROGEN_EASYEDA_WORK_DIR
      || 'local-data/easyeda-runs',
  ),
  easyedaExampleLibraryDir: resolve(
    process.env.PROGEN_EASYEDA_EXAMPLE_LIBRARY_DIR
      || 'vendor/easyeda/examples-300',
  ),
  apiEnvPath: resolve(process.env.PROGEN_API_ENV_PATH || 'api.env'),
  localDataDir: resolve(process.env.PROGEN_LOCAL_DATA_DIR || 'local-data'),
  dbPath: resolve(process.env.PROGEN_DB_PATH || 'local-data/db/progeneda-local-db.json'),
  defaultUserId: process.env.PROGEN_DEFAULT_USER_ID || 'user_local_tahabinzaeem0',
  defaultUserEmail: process.env.PROGEN_DEFAULT_USER_EMAIL || 'tahabinzaeem0@progeneda.local',
  superAdminUserIds,
};
