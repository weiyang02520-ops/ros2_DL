# W7: PC 侧阶段入口（Windows PowerShell）。默认只预览；显式 -Execute 才 SSH/执行。
# 目标机命令通过 SSH 转发；不改生产软链；不启未审 ZED；无 All 步骤。
# 落盘建议：复制到 C:/Users/peng/robot_ssh/vision_fix/vision_delivery/
param(
  [Parameter(Mandatory = $true)][ValidateSet(
    'Deploy', 'Perception', 'Transform', 'Subscriber', 'Capture', 'StopOwn', 'Help'
  )][string]$Step,
  [switch]$Execute,
  [string]$RobotHost = 'nvidia@192.168.43.12',
  [string]$RemoteScript = '~/vision_isolated_ws/src/vision_perception/scripts/vision_delivery/Run-VisionStage.sh',
  [int]$DurationSec = 20
)

function Show-Help {
  @"
Run-VisionStage.ps1 -Step <Deploy|Perception|Transform|Subscriber|Capture|StopOwn> [-Execute]
Default: preview remote command. -Execute runs via ssh $RobotHost.
Camera/ZED start is NOT in this script — use reviewed camera entry separately (authorized).
"@
}

if ($Step -eq 'Help') { Show-Help; exit 0 }

$remoteArgs = @($Step)
if ($DurationSec -gt 0) { $remoteArgs += "--duration=$DurationSec" }
if ($Execute) { $remoteArgs += '--execute' }

$cmd = "bash $RemoteScript $($remoteArgs -join ' ')"
Write-Host "[PREVIEW] ssh $RobotHost `$cmd => $cmd"
if (-not $Execute) {
  Write-Host 'Pass -Execute to run over SSH after user authorization.'
  exit 0
}

Write-Host "[EXECUTE] ssh $RobotHost ..."
ssh $RobotHost $cmd
exit $LASTEXITCODE
