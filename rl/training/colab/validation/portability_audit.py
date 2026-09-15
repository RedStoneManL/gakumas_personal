"""Read-only source/PLv76 portability audit; no optimizer or long training."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re
import sys
import time

TRAINING = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TRAINING))
from gakumas_training.tasks import FullProduceConfig, FullProduceTask
from gakumas_training.contracts import PolicySelection


def audit():
    task = FullProduceTask()
    arena = task.arena_root
    vendor = arena / 'gakumas_arena/_vendor/gakumas_tools/packages'
    external, unresolved, case_mismatches = set(), [], []
    for path in vendor.rglob('*.js'):
        for specifier in re.findall(r'(?:from\s*|import\s*)["\x27]([^"\x27]+)["\x27]', path.read_text(encoding='utf8')):
            if not specifier.startswith('.'):
                external.add(specifier)
                continue
            target = path.parent / specifier
            resolved = next((candidate for candidate in (target, Path(str(target)+'.js'), target/'index.js')
                             if candidate.is_file()), None)
            if resolved is None:
                unresolved.append([path.relative_to(arena).as_posix(), specifier])
                continue
            current = arena
            for part in resolved.resolve().relative_to(arena).parts:
                if part not in {child.name for child in current.iterdir()}:
                    case_mismatches.append([path.relative_to(arena).as_posix(), specifier, part])
                    break
                current /= part

    from gakumas_arena.loadouts import hif_growth_panel_max_levels
    config = FullProduceConfig(loadout={
        'idol_card_id': 'i_card-shro-3-018', 'producer_level': 76, 'idol_rank': 6,
        'dearness_level': 37, 'auto_support_cards': False,
        'support_card_ids': ['s_card-2-0007', 's_card-3-0030', 's_card-3-0064',
                             's_card-3-0069', 's_card-3-0070', 's_card-3-0077'],
        'support_card_levels': [50, 60, 60, 60, 60, 60]},
        research_config={'growth_panel_levels': hif_growth_panel_max_levels()})
    task = FullProduceTask(config, arena_root=arena)
    kinds, observed_levels, support_counts = Counter(), set(), set()

    def policy(decision):
        kinds[decision.kind] += 1
        observed_levels.add(decision.observation['produce']['state']['producer_level'])
        support_counts.add(len(decision.observation['produce']['support_skills']))
        index = 0
        if decision.kind == 'outer':
            for kind in ('special_finish', 'interval_finish', 'consult_finish', 'audition_accept'):
                match = next((i for i, candidate in enumerate(decision.candidates)
                              if candidate.get('action_type') == kind), None)
                if match is not None:
                    index = match
                    break
        elif decision.kind == 'exam_action':
            index = next((i for i, candidate in enumerate(decision.candidates)
                          if candidate['type'] == 'play'), 0)
        return PolicySelection(index, 0, 0, 0)

    started = time.perf_counter()
    try:
        episode = task.run_episode(policy, seed=91076, policy_version=0)
        return {
            'schema': 'gakumas-colab-portability-audit/1',
            'not_training': True, 'linux_runtime_executed': False,
            'source_scan': {'raw_yaml_count': len(list((arena/'data/raw/gakumasu-diff').glob('*.yaml'))),
                'vendor_js_count': len(list(vendor.rglob('*.js'))),
                'vendor_json_count': len(list(vendor.rglob('*.json'))),
                'external_imports': sorted(external), 'missing_relative_imports': unresolved,
                'case_mismatches': case_mismatches},
            'plv76_natural_probe': {'config': asdict(config), 'observed_producer_levels': sorted(observed_levels),
                'observed_support_skill_counts': sorted(support_counts), 'decision_kinds': dict(kinds),
                'raw_terminal_rating': episode.raw_score, 'termination': episode.termination,
                'accepted_exam_count': episode.metadata['accepted_exam_count'],
                'rating_provenance': episode.metadata['rating_provenance'],
                'seconds': time.perf_counter()-started,
                'claim': 'PLv76 real loadout executes; this is not a policy-quality or complete 3+2 proof'},
            'arena_version': task.arena_version,
        }
    finally:
        task.close()


if __name__ == '__main__':
    result = audit()
    target = Path(__file__).with_name('portability-audit.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'source_scan': result['source_scan'], 'plv76': result['plv76_natural_probe']}, ensure_ascii=False))
