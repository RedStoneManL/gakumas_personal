#!/usr/bin/env bash
# Gakumas RL: launch one container mapping all 8 NPUs (guide ¡ì5).
# Usage: bash run_container.sh <image> [project_dir] [shm_size]
set -euo pipefail

GK_IMAGE="${1:?usage: run_container.sh <image> [project_dir] [shm_size]}"
GK_PROJECT="${2:-/mnt/local/gakumas}"
# NOTE: with --ipc host the container uses the HOST /dev/shm (measured: 1006 GiB tmpfs)
# and --shm-size is IGNORED. Set GK_IPC=private to get a private /dev/shm of GK_SHM instead.
GK_SHM="${3:-64g}"
GK_IPC="${GK_IPC:-host}"
GK_NAME="${GK_NAME:-gakumas-rl-8npu}"

[[ "$GK_PROJECT" = /* ]] || { echo "project dir must be absolute" >&2; exit 1; }
mkdir -p "$GK_PROJECT"

if docker ps -a --format '{{.Names}}' | grep -qx "$GK_NAME"; then
  echo "container '$GK_NAME' already exists. Use:" >&2
  echo "  docker start -ai $GK_NAME     # reattach" >&2
  echo "  bash enter.sh                 # exec a login shell" >&2
  exit 1
fi

# --- Node.js toolchain lives on the bind mount so it survives container recreation. ---
# Docker cannot *prepend* to an image's PATH, so read the image PATH and rebuild it here.
GK_NODE_BIN="${GK_NODE_BIN:-$GK_PROJECT/toolchain/node/bin}"
GK_IMAGE_PATH="$(docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$GK_IMAGE"                  | sed -n 's/^PATH=//p' | head -1)"
if [[ -z "$GK_IMAGE_PATH" ]]; then
  echo "could not read PATH from image $GK_IMAGE" >&2; exit 1
fi
if [[ -x "$GK_NODE_BIN/node" ]]; then
  GK_PATH="$GK_NODE_BIN:$GK_IMAGE_PATH"
  echo "node      : $("$GK_NODE_BIN/node" --version) at $GK_NODE_BIN"
else
  GK_PATH="$GK_IMAGE_PATH"
  echo "node      : NOT FOUND at $GK_NODE_BIN -- install.sh and doctor.py will fail" >&2
fi

args=(
  --name "$GK_NAME"
  --env "PATH=$GK_PATH"
  --detach --tty
  --platform linux/arm64
  --network host
  --workdir "$GK_PROJECT"
  --restart unless-stopped          # survives a host reboot; `docker stop` still keeps it stopped
  --cap-add SYS_PTRACE              # py-spy / gdb profiling only. NOT --privileged.
)

if [[ "$GK_IPC" == "host" ]]; then
  args+=(--ipc host)                 # /dev/shm == host's, measured 1006 GiB
else
  args+=(--shm-size "$GK_SHM")       # private /dev/shm of exactly this size
fi

# --- NPU device nodes: map physical 0..7 directly, no runtime remapping (guide ¡ì5, ¡ì7.2) ---
for d in /dev/davinci{0..7} /dev/davinci_manager /dev/devmm_svm /dev/hisi_hdc; do
  [[ -e "$d" ]] || { echo "missing device node: $d" >&2; exit 1; }
  args+=(--device "$d")
done

# --- host driver user-space libs ONLY. Never mount the whole /usr/local/Ascend (guide ¡ì5) ---
[[ -d /usr/local/Ascend/driver ]] || { echo "driver dir not found" >&2; exit 1; }
args+=(--mount 'type=bind,src=/usr/local/Ascend/driver,dst=/usr/local/Ascend/driver,readonly')
for p in /usr/local/dcmi /usr/local/bin/npu-smi /etc/ascend_install.info /etc/hccn.conf; do
  [[ -e "$p" ]] && args+=(--mount "type=bind,src=$p,dst=$p,readonly")
done

# --- writable: our own project tree on the node-local RAID ---
args+=(--mount "type=bind,src=$GK_PROJECT,dst=$GK_PROJECT")
# --- shared NFS: READ-ONLY on purpose. Nothing in this container may write to /mnt/public. ---
[[ -d /mnt/public ]] && args+=(--mount 'type=bind,src=/mnt/public,dst=/mnt/public,readonly')
[[ -e /usr/share/zoneinfo/Asia/Shanghai ]] && \
  args+=(--mount 'type=bind,src=/usr/share/zoneinfo/Asia/Shanghai,dst=/etc/localtime,readonly')

echo "image     : $GK_IMAGE"
echo "container : $GK_NAME"
echo "project   : $GK_PROJECT  (writable)"
echo "/mnt/public: read-only"
if [[ "$GK_IPC" == "host" ]]; then
  echo "shm       : host /dev/shm ($(df -h --output=size /dev/shm | tail -1 | tr -d ' ')), --shm-size not used"
else
  echo "shm       : private $GK_SHM"
fi

docker run "${args[@]}" "$GK_IMAGE" sleep infinity
echo
docker ps --filter "name=$GK_NAME" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
