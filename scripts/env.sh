# Biến môi trường dùng chung — source từ các script khác.
# Dữ liệu nặng (.venv, mô hình, giọng, audio) nằm ngoài OneDrive.
export GIONGTOI_DATA_DIR="${GIONGTOI_DATA_DIR:-$HOME/VoiceCloneData}"
export UV_PROJECT_ENVIRONMENT="$GIONGTOI_DATA_DIR/.venv"
export UV_CACHE_DIR="$GIONGTOI_DATA_DIR/.uv-cache"
export HF_HOME="$GIONGTOI_DATA_DIR/models"
export HF_HUB_DISABLE_TELEMETRY=1
export PATH="$HOME/.local/bin:$PATH"
GIONGTOI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GIONGTOI_ROOT
