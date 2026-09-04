# 螢火 Firefly 後端映像 / backend image
# 目標:單一 VPS、CPU-only 推論(文件 03)。/ Target: one VPS, CPU-only inference (doc 03).
FROM python:3.11-slim

WORKDIR /app
# FIREFLY_CONFIG_PATH 必須明確指定。config.py 的 REPO_ROOT 是 parents[2],
# 在 repo 內解析為專案根目錄,但在映像內是 /,會去找不存在的 /config/firefly.yaml,
# 而 load_config 找不到檔案時「靜默」退回程式預設值 —— 掛載進來的設定檔會被完全忽略。
# compose 掛載點是 /app/config,故在此釘死。
# FIREFLY_CONFIG_PATH must be explicit. REPO_ROOT is parents[2], which resolves to the project
# root in a checkout but to / inside the image, so it would look for /config/firefly.yaml and
# load_config would silently fall back to code defaults, ignoring the mounted file entirely.
# Compose mounts it at /app/config, so pin it here.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FIREFLY_CONFIG_PATH=/app/config/firefly.yaml \
    HF_HOME=/opt/hf \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf

# D-012 的嵌入模型。必須與 config/firefly.yaml 的 embedding.model 一致。
# config/ 是執行期掛載,建置期讀不到,所以用 build arg 帶入;改模型要同時改兩處並重建。
# The D-012 embedding model. Must match embedding.model in config/firefly.yaml.
# config/ is mounted at run time and unreadable at build time, hence the build arg:
# changing the model means changing both places and rebuilding.
ARG FIREFLY_EMBED_MODEL=intfloat/multilingual-e5-base

# 1) 先裝 CPU 版 torch,單獨一層(最大、最少變動)。
#    用 --index-url 而非 --extra-index-url:CPU 索引不可達時直接失敗,
#    而不是悄悄改從 PyPI 解析出 CUDA 版,讓映像多出數 GB 的 nvidia 相依。
# 1) CPU-only torch in its own layer (largest, least churn).
#    --index-url, not --extra-index-url: if the CPU index is unreachable this fails loudly
#    instead of quietly resolving the CUDA build from PyPI and adding gigabytes of nvidia deps.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

# 2) 嵌入函式庫與模型烘進映像,放在複製程式碼之前,
#    這樣改程式不會使 1GB 的模型層失效而重新下載。
# 2) Embedding library and model are baked in before the code is copied, so a code change
#    does not invalidate the ~1GB model layer and force a re-download.
RUN pip install --no-cache-dir "sentence-transformers>=3.0" \
 && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${FIREFLY_EMBED_MODEL}', device='cpu')"

# 3) 程式碼與其餘相依。ml extra 於此已滿足。
# 3) Code and remaining dependencies; the ml extra is already satisfied.
COPY . .
RUN pip install --no-cache-dir -e ".[ml]"

# 4) 模型已在映像內,執行期不再連 HuggingFace。
#    這同時消除「下載失敗 → 靜默退回雜湊嵌入」這條路徑(見 firefly/pipeline/embedding.py)。
# 4) The model ships in the image, so run time never calls HuggingFace. This also removes the
#    "download fails, silently fall back to hashed embeddings" path (see pipeline/embedding.py).
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# 建置後自我檢查:設定要 e5 卻退回雜湊嵌入就讓建置失敗。
# Build-time self-check: fail the build if e5 is configured but the hashed fallback is active.
RUN FIREFLY_EMBEDDER=e5 python -m firefly.cli check-embedder
