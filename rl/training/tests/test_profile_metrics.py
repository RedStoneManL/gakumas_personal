from gakumas_training.contracts import Episode
from gakumas_training.runtime.trainer import episode_summary


def test_profile_scores_do_not_hide_failed_profile_in_overall_mean():
    episodes = [
        Episode('full_produce', 1, [], 100., 'clear', {'loadout_profile': 'a'}),
        Episode('full_produce', 2, [], 0., 'failed', {'loadout_profile': 'b'}),
        Episode('full_produce', 3, [], 50., 'clear', {'loadout_profile': 'a'}),
    ]
    result = episode_summary(episodes)
    assert result['raw_score_mean'] == 50.
    assert result['loadout_profiles']['a']['raw_score_mean'] == 75.
    assert result['loadout_profiles']['a']['episodes'] == 2
    assert result['loadout_profiles']['b']['terminations'] == {'failed': 1}


def test_single_unlabelled_task_stays_compatible():
    result = episode_summary([Episode('exam_score', 1, [], 13., 'clear')])
    assert result['raw_score_mean'] == 13.
    assert 'loadout_profiles' not in result
