targetScope = 'resourceGroup'

@description('Dedicated portfolio resources; no departmental subscriptions.')
param prefix string = 'operations'
param location string = resourceGroup().location
@description('Container image pinned to its immutable digest.')
param image string
@description('Existing project registry; GitHub build identity is scoped to this registry only.')
param registryName string = 'telecomvc53728'
param tags object = { project: 'azure-operations-data-platform', purpose: 'student-portfolio' }
var suffix = uniqueString(resourceGroup().id)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'ops${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
  }
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
    isVersioningEnabled: true
  }
}
resource files 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'operations'
  properties: { publicAccess: 'None' }
}
resource queues 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {}
}
resource jobs 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queues
  name: 'file-jobs'
  properties: {}
}
resource failed 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queues
  name: 'failed-jobs'
  properties: {}
}
resource identities 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [for role in ['portal', 'worker']: {
  name: '${prefix}-${role}'
  location: location
  tags: tags
}]
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for i in range(0, 2): {
  name: guid(registry.id, identities[i].id, 'pull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identities[i].properties.principalId
    principalType: 'ServicePrincipal'
  }
}]
resource blobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for i in range(0, 2): {
  name: guid(files.id, identities[i].id, 'blob-contributor')
  scope: files
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: identities[i].properties.principalId
    principalType: 'ServicePrincipal'
  }
}]
resource queueSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(jobs.id, identities[0].id, 'sender')
  scope: jobs
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
    principalId: identities[0].properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource queueProcessor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(jobs.id, identities[1].id, 'processor')
  scope: jobs
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
    principalId: identities[1].properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource deadSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(failed.id, identities[1].id, 'sender')
  scope: failed
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
    principalId: identities[1].properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.1') }
  }
}
resource monitorReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logs.id, identities[0].id, 'log-reader')
  scope: logs
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '73c42c96-874c-492b-b04d-ab87d138a893')
    principalId: identities[0].properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource environment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: '${prefix}-standard-environment'
  location: location
  tags: tags
  properties: {
    environmentMode: 'WorkloadProfiles'
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}
resource portal 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${prefix}-web'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identities[0].id}': {} } }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [{ server: registry.properties.loginServer, identity: identities[0].id }]
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
    }
    template: {
      containers: [{
        name: 'portal'
        image: image
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
        env: [
          { name: 'OPERATIONS_STORAGE_ACCOUNT', value: storage.name }
          { name: 'OPERATIONS_LOG_WORKSPACE_ID', value: logs.properties.customerId }
          { name: 'AZURE_CLIENT_ID', value: identities[0].properties.clientId }
        ]
        probes: [
          { type: 'Liveness', httpGet: { path: '/health/live', port: 8000 }, initialDelaySeconds: 15, periodSeconds: 30 }
          { type: 'Readiness', httpGet: { path: '/health/ready', port: 8000 }, initialDelaySeconds: 15, periodSeconds: 30, timeoutSeconds: 10 }
        ]
      }]
      scale: { minReplicas: 0, maxReplicas: 1, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '10' } } }] }
    }
  }
  dependsOn: [pull, blobAccess, queueSender]
}
resource worker 'Microsoft.App/jobs@2025-01-01' = {
  name: '${prefix}-processor'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identities[1].id}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Event'
      replicaTimeout: 180
      replicaRetryLimit: 1
      registries: [{ server: registry.properties.loginServer, identity: identities[1].id }]
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 1
          pollingInterval: 60
          rules: [{
            name: 'incoming-files'
            type: 'azure-queue'
            identity: identities[1].id
            metadata: { accountName: storage.name, queueName: jobs.name, queueLength: '1' }
          }]
        }
      }
    }
    template: {
      containers: [{
        name: 'processor'
        image: image
        command: ['python', '-m', 'operations_cloud.worker']
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
        env: [
          { name: 'OPERATIONS_STORAGE_ACCOUNT', value: storage.name }
          { name: 'AZURE_CLIENT_ID', value: identities[1].properties.clientId }
        ]
      }]
    }
  }
  dependsOn: [pull, blobAccess, queueProcessor, deadSender]
}
output appUrl string = 'https://${portal.properties.configuration.ingress.fqdn}'
output storageAccountName string = storage.name
output processorName string = worker.name
output logWorkspace string = logs.name
