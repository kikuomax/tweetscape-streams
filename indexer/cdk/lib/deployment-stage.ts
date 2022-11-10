import type { Node } from 'constructs';

/** Possible deployment stage values. */
export const DEPLOYMENT_STAGES = ['development', 'production'] as const;

/** Deployment stage. */
export type DeploymentStage = typeof DEPLOYMENT_STAGES[number];

/** Name of the CDK context that specifies the deployment stage. */
export const DEPLOYMENT_STAGE_CONTEXT = 'tweetscape:stage';

/**
 * Obtains the deployment stage specified in the CDK context.
 *
 * @throws RangeError
 *
 *   If no deployment stage is specified in the CDK context,
 *   or if an invalid deployment stage is specified in it.
 *
 * @beta
 */
export function getDeploymentStage(node: Node): DeploymentStage {
  const stage = node.tryGetContext(DEPLOYMENT_STAGE_CONTEXT);
  if (stage == null) {
    throw new RangeError(
      `context "${DEPLOYMENT_STAGE_CONTEXT}" must be specified`,
    );
  }
  if (!isDeploymentStage(stage)) {
    throw new RangeError(`invalid deployment stage: ${stage}`);
  }
  return stage;
}

/**
 * Returns if a given string is a deployment stage.
 *
 * @remarks
 *
 * This function narrows `stageStr` to `DeploymentStage`.
 *
 * @returns
 *
 *   Whether `stageStr` is a deployment stage.
 */
export function isDeploymentStage(
  stageStr: string,
): stageStr is DeploymentStage {
  for (const stage of DEPLOYMENT_STAGES) {
    if (stage === stageStr) {
      return true;
    }
  }
  return false;
}
