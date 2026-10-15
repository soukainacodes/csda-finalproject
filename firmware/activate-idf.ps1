# Activate the ESP-IDF v5.2.8 environment in the current PowerShell session.
# Usage:  . .\activate-idf.ps1    (note the leading dot: it must be dot-sourced)
#
# Why this exists: the offline installer's final config step failed on this PC,
# so the Start-Menu "ESP-IDF PowerShell" shortcut cannot locate the install and
# the default export picked the wrong (Microsoft Store) Python. This script sets
# the paths explicitly and uses ESP-IDF's own bundled Python, which works.
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$env:IDF_PATH = "C:\Espressif\frameworks\esp-idf-v5.2.8"
$env:IDF_TOOLS_PATH = "C:\Espressif"
$env:PATH = "C:\Espressif\tools\idf-python\3.11.2;" + $env:PATH
. "$env:IDF_PATH\export.ps1"
