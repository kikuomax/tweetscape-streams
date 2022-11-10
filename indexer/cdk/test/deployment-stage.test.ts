import { isDeploymentStage } from '../lib/deployment-stage';

describe('DeploymentStage', () => {
  it('isDeploymentStage("development") should be true', () => {
    expect(isDeploymentStage('development')).toBe(true);
  });

  it('isDeploymentStage("production") should be false', () => {
    expect(isDeploymentStage('production')).toBe(true);
  });

  it('isDeploymentStage("test") should be false', () => {
    expect(isDeploymentStage('test')).toBe(false);
  });
});
