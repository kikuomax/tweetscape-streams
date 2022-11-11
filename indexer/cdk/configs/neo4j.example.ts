export default {
    development: {
        // replace <HOSTNAME>
        neo4jUri: 'neo4j+s://<HOSTNAME>',
        // replace if necessary
        neo4jUsername: 'neo4j',
        // DO NOT expose a secret here. use AWS console/CLI to edit
        neo4jPassword: 'Edit this on AWS console/CLI',
    },
    production: {
        // replace <HOSTNAME>
        neo4jUri: 'neo4j+s://<HOSTNAME>',
        // replace if necessary
        neo4jUsername: 'neo4j',
        // DO NOT expose a secret here. use AWS console/CLI to edit
        neo4jPassword: 'Edit this on AWS console/CLI',
    },
};
