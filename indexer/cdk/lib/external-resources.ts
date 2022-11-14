import { SecretValue, aws_secretsmanager as secrets } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import type { DeploymentStage } from './deployment-stage';
import neo4jConfigSet from '../configs/neo4j';
import postgresConfigSet from '../configs/postgres';
import twitterConfigSet from '../configs/twitter';

interface Props {
    /** Deployment stage. */
    deploymentStage: DeploymentStage;
}

/**
 * CDK construct that provisions resources related to external resources.
 *
 * @remarks
 *
 * Exeternal resources include
 * - PostgreSQL database that manages Tweetscape users.
 * - neo4j database that manages the graph.
 */
export class ExternalResources extends Construct {
    /** Secret for database credentials. */
    databaseCredentials: secrets.ISecret;

    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { deploymentStage } = props;
        const postgresConfig = postgresConfigSet[deploymentStage];
        const neo4jConfig = neo4jConfigSet[deploymentStage];
        const twitterConfig = twitterConfigSet[deploymentStage];

        // TODO: consider about separating secrets for different databases.
        // all credentials are in one place to reduce the charge for now.
        this.databaseCredentials = new secrets.Secret(
            this,
            'DatabaseCredentials',
            {
                description: `Database credentials (${deploymentStage})`,
                secretObjectValue: {
                    ...wrapValuesWithSecretValue(postgresConfig),
                    ...wrapValuesWithSecretValue(neo4jConfig),
                    ...wrapValuesWithSecretValue(twitterConfig),
                },
            },
        );
    }
}

// converts a given string to string map to a string to SecretValue map.
function wrapValuesWithSecretValue(
    keyValues: { [k: string]: string },
): { [k: string]: SecretValue } {
    const secretValues: { [k: string]: SecretValue } = {};
    for (const [key, value] of Object.entries(keyValues)) {
        secretValues[key] = SecretValue.unsafePlainText(value);
    }
    return secretValues;
}
