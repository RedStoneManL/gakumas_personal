#!/usr/bin/env bash
# Rank-local records refactor: unit test with a threaded fake mesh, then the full
# regression in a deploy-rooted symlink tree carrying every patched file.
set -u
D=/mnt/local/gakumas/deploy; S=/mnt/local/gakumas/scripts/stage4; T=$S/tree
cd $D && source .venv/bin/activate
echo "##### 1. sharded.py unit test (fake mesh, K ranks as threads) #####"
GK_EXAM=$D/exam-search GK_SHARDED=$S/sharded.py python3 $S/test_sharded.py 2>&1 | tail -45
echo; echo "##### 2. deploy-rooted tree with overlays #####"
rm -rf "$T"; mkdir -p "$T"
for e in "$D"/* "$D"/.[!.]*; do n=$(basename "$e"); [ "$n" = exam-search ] && continue; [ "$n" = ascend ] && continue; ln -s "$e" "$T/$n"; done
cp -r "$D/exam-search" "$T/exam-search"; cp -r "$D/ascend" "$T/ascend"
for f in sharded ppo critic_completion practice distributed runner bank_rollout continuation; do cp "$S/$f.py" "$T/exam-search/draftrl/$f.py"; done
cp "$S/train.py" "$T/exam-search/train.py"
md5sum "$T"/exam-search/draftrl/{sharded,ppo,critic_completion,distributed,runner,continuation}.py "$T/exam-search/train.py" | cut -c1-10,33- | sed "s#$T/exam-search/##"
echo; echo "##### 3. import smoke: every patched module loads #####"
cd "$T/exam-search" && python3 -c "
import sys; sys.path[:0]=['.','runtime/shared','runtime/arena']
import draftrl.sharded, draftrl.ppo, draftrl.critic_completion, draftrl.distributed, draftrl.runner, draftrl.continuation
print('  imports ok')"
echo; echo "##### 4. regression #####"
cd "$T/exam-search" && timeout 900 python3 ../ascend/run_tests.py 2>&1 | grep -E "^(ERROR|FAIL):|^Ran |^OK|^FAILED|Error:" | head -20
