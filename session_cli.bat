@echo off
setlocal
set PYTHONPATH=D:\soft\SlobTools;%PYTHONPATH%
python -m SlobMemory.session_cli %*
endlocal
