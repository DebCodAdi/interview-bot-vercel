#!/bin/bash
# =====================================================================
# MIT Interview Bot AI Engine — Linux Runner
# =====================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=================================================="
echo "  🚀 MIT Interview Bot AI Engine (Linux VM)"
echo "=================================================="

# 1. Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "   Created .env — please configure your GROQ_API_KEY and VAPI keys."
fi

# 2. Check / Setup Python Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment (venv)..."
    python3 -m venv venv
fi

echo "🔄 Activating virtual environment..."
source venv/bin/activate

# 3. Install / Verify Dependencies
echo "📦 Verifying Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pypdf2 --quiet

# 4. Run automated tests
echo ""
echo "🧪 Running integration & endpoint tests..."
python3 test_endpoints.py

# 5. Get VM IP Address
VM_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=================================================="
echo "  ✅ Server Starting on 0.0.0.0:8000"
echo "  🌐 Local VM URL:     http://localhost:8000/app"
if [ ! -z "$VM_IP" ]; then
echo "  💻 Host Machine URL: http://$VM_IP:8000/app"
fi
echo "  📚 API Swagger Docs: http://localhost:8000/docs"
echo "=================================================="
echo ""

# 6. Start FastAPI with uvicorn
exec python3 main.py
