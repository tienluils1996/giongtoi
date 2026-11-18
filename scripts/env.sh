# Biến môi trường dùng chung — source từ các script khác.
# GIONGTOI_HOME: hạ tầng (.venv, cache, mô hình) — nằm ngoài OneDrive.
# GIONGTOI_DATA_DIR: dữ liệu người dùng (giọng, dự án, DB) — mặc định trùng GIONGTOI_HOME.
export GIONGTOI_HOME="${GIONGTOI_HOME:-$HOME/VoiceCloneData}"
export GIONGTOI_DATA_DIR="${GIONGTOI_DATA_DIR:-$GIONGTOI_HOME}"
export UV_PROJECT_ENVIRONMENT="$GIONGTOI_HOME/.venv"
export UV_CACHE_DIR="$GIONGTOI_HOME/.uv-cache"
export HF_HOME="$GIONGTOI_HOME/models"
export HF_HUB_DISABLE_TELEMETRY=1
export PATH="$HOME/.local/bin:$PATH"
GIONGTOI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GIONGTOI_ROOT
