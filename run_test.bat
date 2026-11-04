@echo off
chcp 65001 > nul
echo ======================================
echo 视野日报测试脚本
echo ======================================
echo.

cd /d "%~dp0"

echo [1/4] 检查环境变量...
if "%OPENAI_API_KEY%"=="" (
    echo [ERROR] OPENAI_API_KEY 未设置
    pause
    exit /b 1
) else (
    echo [OK] OPENAI_API_KEY 已设置
)

if "%OPENAI_BASE_URL%"=="" (
    echo [ERROR] OPENAI_BASE_URL 未设置
    pause
    exit /b 1
) else (
    echo [OK] OPENAI_BASE_URL 已设置
)

echo.
echo [2/4] 检查 Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python 未安装或不在 PATH 中
    pause
    exit /b 1
)

echo.
echo [3/4] 检查依赖包...
python -c "import feedparser, openai, requests, bs4" 2>nul
if errorlevel 1 (
    echo [ERROR] 缺少依赖包，正在安装...
    pip install -r requirements.txt
)

echo.
echo [4/4] 运行程序...
echo ======================================
echo.

python news_digest.py

echo.
echo ======================================
if errorlevel 1 (
    echo [ERROR] 程序运行失败
) else (
    echo [OK] 程序运行完成
    echo.
    echo 生成的文件位于: digests\ 目录
    explorer digests
)

pause
