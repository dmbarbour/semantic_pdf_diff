#!/usr/bin/env bash
# Run a local, CPU-only embedding server with the same OpenAI-compatible
# /v1/embeddings endpoint as the in-house deployment, for development and the
# retrieval benchmark. Uses Hugging Face text-embeddings-inference in Docker.
#
#   scripts/embedding_server.sh start [model-id] [port]   # default: all-MiniLM-L6-v2 on 8081
#   scripts/embedding_server.sh stop  [model-id]
#
# In-house models: llmrails/ember-v1, sentence-transformers/all-MiniLM-L6-v2,
# sentence-transformers/all-mpnet-base-v2, intfloat/multilingual-e5-small,
# intfloat/multilingual-e5-large. Weights are cached in ~/.cache/tei.
# The server listens on 127.0.0.1 only.
set -euo pipefail

IMAGE="ghcr.io/huggingface/text-embeddings-inference:cpu-latest"
ACTION="${1:-start}"
MODEL="${2:-sentence-transformers/all-MiniLM-L6-v2}"
PORT="${3:-8081}"
NAME="spd-embed-$(basename "$MODEL" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-')"

case "$ACTION" in
  start)
    mkdir -p "$HOME/.cache/tei"
    docker run -d --rm --name "$NAME" -p "127.0.0.1:$PORT:80" -v "$HOME/.cache/tei:/data" \
      "$IMAGE" --model-id "$MODEL" >/dev/null
    for _ in $(seq 1 120); do
      if curl -sf -m 5 "http://127.0.0.1:$PORT/health" >/dev/null; then
        echo "$MODEL ready at http://127.0.0.1:$PORT/v1/embeddings (container $NAME)"
        exit 0
      fi
      sleep 5
    done
    echo "$MODEL did not become ready; see: docker logs $NAME" >&2
    exit 1
    ;;
  stop)
    docker stop "$NAME" >/dev/null && echo "stopped $NAME"
    ;;
  *)
    echo "usage: $0 start|stop [model-id] [port]" >&2
    exit 2
    ;;
esac
