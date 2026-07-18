import { generateWithKiCadExecutable } from './kicad-executable-service.mjs';
import { planKicadMainJson } from './kicad-main-json-planner-service.mjs';
import { generateWithLtspiceExecutable } from './ltspice-executable-service.mjs';
import { planLtspiceMainJson } from './ltspice-main-json-planner-service.mjs';
import { generateWithEasyedaExecutable } from './easyeda-executable-service.mjs';
import { planEasyedaMainJson } from './easyeda-main-json-planner-service.mjs';

export async function generateCircuitArtifact({
  prompt,
  service = 'PR',
  config,
  routingPlan = null,
  mainJson = null,
  routingMode = 'combination',
  animationBudgetSeconds = null,
  onProgress = null,
}) {
  if (service === 'KC') {
    let planner = null;
    let resolvedMainJson = mainJson;

    if (!resolvedMainJson) {
      planner = await planKicadMainJson({
        prompt,
        config,
        model: routingPlan?.selectedModel || null,
      });
      resolvedMainJson = planner.mainJson;
    }

    const generated = await generateWithKiCadExecutable({
      mainJson: resolvedMainJson,
      prompt,
      config,
      routingMode,
    });
    generated.sourceMainJson = resolvedMainJson;

    if (planner) {
      generated.providerUsage = planner.providerUsage;
      generated.modelRouting = {
        provider: planner.provider,
        model: planner.model,
        adapter: planner.adapter,
      };
    }

    return generated;
  }

  if (service === 'LT') {
    let planner = null;
    let resolvedMainJson = mainJson;

    if (!resolvedMainJson) {
      planner = await planLtspiceMainJson({ prompt, config });
      resolvedMainJson = planner.mainJson;
    }

    const generated = await generateWithLtspiceExecutable({
      mainJson: resolvedMainJson,
      prompt,
      config,
      animationBudgetSeconds,
      onEvent: onProgress,
    });
    generated.sourceMainJson = resolvedMainJson;

    if (planner) {
      generated.providerUsage = planner.providerUsage;
      generated.modelRouting = {
        provider: planner.provider,
        model: planner.model,
        adapter: planner.adapter,
      };
    }

    return generated;
  }

  if (service === 'EA') {
    let planner = null;
    let resolvedMainJson = mainJson;

    if (!resolvedMainJson) {
      planner = await planEasyedaMainJson({
        prompt,
        config,
        model: routingPlan?.selectedModel || null,
      });
      resolvedMainJson = planner.mainJson;
    }

    const generated = await generateWithEasyedaExecutable({
      mainJson: resolvedMainJson,
      prompt,
      config,
      routingMode,
      onEvent: onProgress,
    });
    generated.sourceMainJson = resolvedMainJson;

    if (planner) {
      generated.providerUsage = planner.providerUsage;
      generated.modelRouting = {
        provider: planner.provider,
        model: planner.model,
        adapter: planner.adapter,
      };
    }
    return generated;
  }

  const error = new Error(
    service === 'PR'
      ? 'Proteus generation is unavailable until the upgraded Proteus package is integrated.'
      : `Generation for ${service} is not installed in this local workspace.`,
  );
  error.statusCode = 503;
  throw error;
}
