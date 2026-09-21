@echo off
setlocal
set "UV_PYTHON_INSTALL_DIR=%~dp0runtime\python"
set "UV_PROJECT_ENVIRONMENT=%~dp0runtime\venv"
set "UV_CACHE_DIR=%~dp0runtime\cache"
set "UV_LINK_MODE=copy"
set "UV_HTTP_RETRIES=0"
"%~dp0tools\uv.exe" sync --directory "%~dp0app" --frozen --no-dev --python 3.12.10 --managed-python --no-editable
exit /b %errorlevel%
