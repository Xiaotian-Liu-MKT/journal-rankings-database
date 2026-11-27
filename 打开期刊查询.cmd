@echo off
cd /d "%~dp0"
start "" pythonw -m journaldb serve --open
