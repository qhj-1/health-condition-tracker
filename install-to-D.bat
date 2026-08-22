@echo off
setlocal
set SRC=%~dp0
set DEST=D:\codex-skills\health-condition-tracker
set LINK=%USERPROFILE%\.codex\skills\health-condition-tracker

echo ============================================
echo  Health Condition Tracker - Install to D:
echo ============================================
echo.
echo  Source : %SRC%
echo  Target : %DEST%
echo.

if not exist "%DEST%" mkdir "%DEST%"

echo  Copying files (xcopy) ...
xcopy "%SRC%*" "%DEST%\" /E /I /Y /Q

echo.
echo  File count in %DEST% :
dir /s /b "%DEST%" | find /c /v ""

if not exist "%USERPROFILE%\.codex\skills" mkdir "%USERPROFILE%\.codex\skills"
if exist "%LINK%" (
  echo  [skip] Link already exists: %LINK%
) else (
  echo  Creating link ...
  mklink /J "%LINK%" "%DEST%"
)

echo.
echo  ===== Verification =====
if exist "%DEST%\SKILL.md" (
  echo  [OK] SKILL.md exists at %DEST%
) else (
  echo  [FAIL] SKILL.md NOT found at %DEST%
)
if exist "%LINK%\SKILL.md" (
  echo  [OK] SKILL.md readable through junction
) else (
  echo  [FAIL] SKILL.md NOT readable through junction
)
echo.
echo  If both lines show [OK], the skill is installed.
echo  Restart Codex, then describe your symptoms in a new chat.
echo.
pause
