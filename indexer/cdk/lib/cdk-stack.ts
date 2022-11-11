import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import type { DeploymentStage } from './deployment-stage';

interface Props extends cdk.StackProps {
    /** Deployment stage. */
    deploymentStage: DeploymentStage;
};

export class CdkStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id, props);
    }
}
