@echo off
:: 指向 Hostx86\x86 版本的 dumpbin
set "DUMPBIN_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC\14.29.30133\bin\Hostx86\x86\dumpbin.exe"

if exist "%DUMPBIN_PATH%" (
    "%DUMPBIN_PATH%" %*
) else (
    echo [Error] 未找到 32 位 dumpbin，请检查路径是否正确。
)