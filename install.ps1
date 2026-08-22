# install.ps1 — Health Condition Tracker 一键安装脚本（Windows）
# 功能：把技能包复制到 D 盘长期存放，并可选择在 Codex skills 目录创建目录联接（junction）,
#       使 Codex 自动加载该技能，而文件实际保存在 D 盘。
# 用法：
#   .\install.ps1                          # 复制到 D:\codex-skills\health-condition-tracker
#   .\install.ps1 -LinkToCodexSkills       # 复制 + 在 ~/.codex/skills 创建联接
#   .\install.ps1 -Destination D:\MySkills\hct -LinkToCodexSkills   # 自定义目标路径
param(
    [string]$Destination = "D:\codex-skills\health-condition-tracker",
    [switch]$LinkToCodexSkills
)
$ErrorActionPreference = "Stop"

# 脚本所在目录即技能包根目录
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = (Resolve-Path $Source).Path

if (-not (Test-Path (Join-Path $Source "SKILL.md"))) {
    Write-Error "未在 $Source 找到 SKILL.md，请确认 install.ps1 位于技能包根目录。"
    exit 1
}

Write-Host "==> 正在复制技能包"
Write-Host "    源目录: $Source"
Write-Host "    目标:   $Destination"

# 确保目标父目录存在
$destParent = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force -Path $destParent | Out-Null

# 复制全部内容（含子目录）
Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
Write-Host "    复制完成。"

if ($LinkToCodexSkills) {
    $link = Join-Path $HOME ".codex\skills\health-condition-tracker"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $link) | Out-Null
    if (Test-Path $link) {
        $item = Get-Item $link
        if ($item.LinkType -eq "Junction") {
            Write-Host "==> 已存在目录联接，跳过创建: $link"
        } else {
            Write-Host "警告: $link 已存在但不是目录联接（$($item.LinkType)），未自动处理，请手动检查。"
        }
    } else {
        New-Item -ItemType Junction -Path $link -Target $Destination | Out-Null
        Write-Host "==> 已创建目录联接: $link -> $Destination"
    }
}

Write-Host ""
Write-Host "完成！技能已安装到: $Destination"
if ($LinkToCodexSkills) {
    Write-Host "Codex 已可自动加载该技能（数据仍保存在 D 盘）。"
} else {
    Write-Host "如需 Codex 自动加载，请再运行一次: .\install.ps1 -LinkToCodexSkills"
}
