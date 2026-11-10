<#
.SYNOPSIS
  Stores the JobFit secrets in Google Secret Manager and the demo admin token in GitHub.

.DESCRIPTION
  You type the values yourself; they are read as secure strings, never printed and never
  written to disk. The admin token is generated randomly. Run it once before `terraform apply`;
  running it again adds new secret versions.

.EXAMPLE
  .\infra\setup-secrets.ps1 -ProjectId my-project-id
#>
param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$Repo = "Wojgos/jobfit"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = New-Object System.Text.UTF8Encoding $false  # pipe values to gcloud as UTF-8

function Read-Secret([string]$Prompt, [switch]$Optional) {
  $secure = Read-Host -Prompt $Prompt -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
  if (-not $plain -and -not $Optional) { throw "$Prompt must not be empty" }
  return $plain
}

function Save-Secret([string]$Name, [string]$Value) {
  $existing = gcloud secrets list --project $ProjectId --filter "name:$Name" --format "value(name)"
  if (-not $existing) {
    gcloud secrets create $Name --project $ProjectId --replication-policy automatic --quiet | Out-Null
  }
  $Value | gcloud secrets versions add $Name --project $ProjectId --data-file=- --quiet | Out-Null
  Write-Host "  saved $Name"
}

Write-Host "Enabling Secret Manager in $ProjectId..."
gcloud services enable secretmanager.googleapis.com --project $ProjectId --quiet

$databaseUrl = Read-Secret "Neon connection string (pooling OFF)"
if ($databaseUrl -notmatch '^postgres(ql)?(\+asyncpg)?://') { throw "That does not look like a Postgres URL" }
if ($databaseUrl -match '-pooler\.') {
  Write-Warning "This is the pooled host. Use the direct connection string (pooling off) instead."
}
$geminiKey = Read-Secret "Gemini API key from a project WITHOUT billing (Enter to skip)" -Optional

$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$adminToken = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')

Write-Host "Saving secrets..."
Save-Secret "jobfit-database-url" $databaseUrl
Save-Secret "jobfit-admin-token" $adminToken
if ($geminiKey) { Save-Secret "jobfit-google-api-key" $geminiKey }

$adminToken | gh secret set DEMO_ADMIN_TOKEN --repo $Repo
Write-Host "  saved DEMO_ADMIN_TOKEN in GitHub ($Repo)"

$hasGemini = [bool]$geminiKey
$databaseUrl = $geminiKey = $adminToken = $null
if (-not $hasGemini) {
  Write-Host "No Gemini key given: set use_gemini = false in infra/terraform.tfvars (offline demo)."
}
Write-Host "Done. Next: cd infra; terraform init; terraform apply"
