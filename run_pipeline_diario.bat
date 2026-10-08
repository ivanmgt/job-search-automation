@echo off
set RAIZ=C:\Users\mario\Downloads\job-search-automation
set LOG=%RAIZ%\log_pipeline.txt

echo ===================================== >> "%LOG%"
echo %DATE% %TIME% - Iniciando pipeline >> "%LOG%"
echo ===================================== >> "%LOG%"

cd /d "%RAIZ%\gob"
uv run main_dia2.py >> "%LOG%" 2>&1

cd /d "%RAIZ%\link_occ"
uv run parser_alertas.py >> "%LOG%" 2>&1

cd /d "%RAIZ%\filtro_ia"
uv run filtro_fit.py >> "%LOG%" 2>&1
uv run vetting_empresa.py >> "%LOG%" 2>&1
uv run sugerencias_cv.py >> "%LOG%" 2>&1
uv run resumen_diario.py >> "%LOG%" 2>&1

echo %DATE% %TIME% - Pipeline terminado >> "%LOG%"