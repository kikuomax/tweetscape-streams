import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import type { DeploymentStage } from './deployment-stage';
import { ExternalResources } from './external-resources';
import { IndexerDependencies } from './indexer-dependencies';
import { OnDemandIndexer } from './on-demand-indexer';
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
        const indexerDependencies = new IndexerDependencies(
            this,
            'IndexerDependencies',
        );
        const periodicIndexer = new PeriodicIndexer(
            this,
            'PeriodicIndexer',
            {
                deploymentStage,
                externalResources,
                indexerDependencies,
            },
        );
        const onDemandIndexer = new OnDemandIndexer(this, 'OnDemandIndexer', {
            deploymentStage,
            externalResources,
            indexerDependencies,
        });
    }
}
