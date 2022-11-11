import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import type { DeploymentStage } from './deployment-stage';
import { ExternalResources } from './external-resources';
import { PeriodicIndexer } from './periodic-indexer';

interface Props extends cdk.StackProps {
    /** Deployment stage. */
    deploymentStage: DeploymentStage;
};

export class CdkStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id, props);

        const { deploymentStage } = props;

        const externalResources = new ExternalResources(
            this,
            'ExternalResources',
            {
                deploymentStage,
            },
        );
        const periodicIndexer = new PeriodicIndexer(
            this,
            'PeriodicIndexer',
            {
                externalResources,
            },
        );
    }
}
