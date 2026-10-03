targetScope = 'resourceGroup'
@description('Monthly amount in the subscription billing currency. An alert is not a spending cap.')
@minValue(1)
param monthlyAmount int
@description('Email address explicitly selected for cost notifications.')
param contactEmail string
param startDate string = utcNow('yyyy-MM-01T00:00:00Z')
resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'telecom-monthly-budget'
  properties: {
    category: 'Cost'
    amount: monthlyAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: startDate }
    notifications: {
      Actual50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [contactEmail]
      }
      Actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [contactEmail]
      }
      Forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [contactEmail]
      }
    }
  }
}
