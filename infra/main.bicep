targetScope = 'resourceGroup'

@description('Short lowercase project name; resources are scoped to a dedicated resource group.')
@minLength(3)
@maxLength(11)
param prefix string = 'telecom'
param location string = resourceGroup().location
@description('Public container image, pinned to an immutable digest for releases. No registry credential required.')
param image string
@description('Optional existing Azure Container Registry in this resource group. Leave empty for a public image.')
param registryName string = ''
@description('Deploy manually first. Enabling schedules is a separate operational decision.')
param enableSchedule bool = false
@description('Bootstrap with false, publish the first data release, then deploy with true.')
param deployApi bool = true
param tags object = { project: 'azure-telecom-cloud', purpose: 'portfolio' }
var suffix = uniqueString(resourceGroup().id)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${prefix}${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Enabled'
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
resource curated 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'curated'
  properties: { publicAccess: 'None' }
}
resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-api-reader'
  location: location
  tags: tags
}
resource jobIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-pipeline-writer'
  location: location
  tags: tags
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = if (!empty(registryName)) {
  name: registryName
}
resource apiPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(registryName)) {
  name: guid(registry!.id, apiIdentity.id, 'acr-pull')
  scope: registry!
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource jobPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(registryName)) {
  name: guid(registry!.id, jobIdentity.id, 'acr-pull')
  scope: registry!
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource readRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(curated.id, apiIdentity.id, 'reader')
  scope: curated
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
    )
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource writeRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(curated.id, jobIdentity.id, 'writer')
  scope: curated
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.1') }
  }
}
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-insights'
  location: location
  kind: 'web'
  tags: tags
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-environment'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}
var commonEnv = [
  { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
  { name: 'TELECOM_CONTAINER', value: curated.name }
  { name: 'TELECOM_DATA_DIR', value: '/tmp/telecom-data' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
]
resource api 'Microsoft.App/containerApps@2024-03-01' = if (deployApi) {
  name: '${prefix}-api'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${apiIdentity.id}': {} } }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: empty(registryName) ? [] : [{ server: registry!.properties.loginServer, identity: apiIdentity.id }]
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          env: concat(commonEnv, [{ name: 'AZURE_CLIENT_ID', value: apiIdentity.properties.clientId }])
          resources: { cpu: json('0.5'), memory: '1Gi' }
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health/live', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health/ready', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 30
              timeoutSeconds: 15
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
  dependsOn: [readRole, apiPullRole]
}
resource pipeline 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-pipeline'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${jobIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      registries: empty(registryName) ? [] : [{ server: registry!.properties.loginServer, identity: jobIdentity.id }]
      triggerType: enableSchedule ? 'Schedule' : 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      manualTriggerConfig: enableSchedule ? null : { parallelism: 1, replicaCompletionCount: 1 }
      scheduleTriggerConfig: enableSchedule
        ? { cronExpression: '0 8 2 */3 *', parallelism: 1, replicaCompletionCount: 1 }
        : null
    }
    template: {
      containers: [
        {
          name: 'pipeline'
          image: image
          command: ['python', '-m', 'telecom_cloud.pipeline', '--publish']
          env: concat(commonEnv, [{ name: 'AZURE_CLIENT_ID', value: jobIdentity.properties.clientId }])
          resources: { cpu: 1, memory: '2Gi' }
        }
      ]
    }
  }
  dependsOn: [writeRole, jobPullRole]
}
output appUrl string = deployApi ? 'https://${api!.properties.configuration.ingress.fqdn}' : ''
output pipelineName string = pipeline.name
output storageAccountName string = storage.name
output readerIdentity string = apiIdentity.name
output writerIdentity string = jobIdentity.name
