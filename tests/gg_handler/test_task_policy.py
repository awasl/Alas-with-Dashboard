"""Task policy checks for regular events and GG opt-in settings."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from module.gg_handler.gg_handler import GGHandler


POLICIES = [
    'disable_all_dangerous_task',
    'disable_guild_and_dangerous',
    'disable_meta_and_exercise',
    'disable_exercise',
    'enable_all',
]


def make_handler(policy, enabled=True, auto=True):
    handler = object.__new__(GGHandler)
    handler.config = SimpleNamespace(data={
        'GameManager': {'GGHandler': {
            'DisabledTask': policy,
            'Enabled': enabled,
            'AutoRestartGG': auto,
        }},
    })
    handler.check_status = Mock()
    return handler


def test_coalition_and_story_follow_regular_event_policy():
    for policy in POLICIES + [None]:
        for task in ['coalition', 'coalition_sp', 'event_story', 'event', 'event_sp']:
            handler = make_handler(policy)
            handler.check_then_set_gg_status(task)
            handler.check_status.assert_called_once_with(True)


def test_other_task_restrictions_are_preserved():
    # Raid, META, exercise and guild keep their existing user-selected rules.
    tasks = ['raid', 'raid_daily', 'opsi_ash_assist', 'opsi_ash_beacon', 'exercise', 'guild']
    allowed = {
        'disable_all_dangerous_task': [False, False, False, False, False, True],
        'disable_guild_and_dangerous': [False, False, False, False, False, False],
        'disable_meta_and_exercise': [True, True, False, False, False, True],
        'disable_exercise': [True, True, True, True, False, True],
        'enable_all': [True, True, True, True, True, True],
    }
    for policy, modes in allowed.items():
        for task, mode in zip(tasks, modes):
            handler = make_handler(policy)
            handler.check_then_set_gg_status(task)
            handler.check_status.assert_called_once_with(mode)
        handler = make_handler(policy)
        handler.check_then_set_gg_status('minigame')
        handler.check_status.assert_called_once_with(False)


def test_event_tasks_respect_gg_master_switches():
    for task in ['coalition', 'coalition_sp', 'event_story']:
        for enabled, auto in [(False, False), (False, True), (True, False), (True, True)]:
            handler = make_handler('disable_all_dangerous_task', enabled=enabled, auto=auto)
            handler.check_status = GGHandler.check_status.__get__(handler)
            handler.set = Mock()
            handler.gg_reset = Mock()
            with patch('module.gg_handler.gg_handler.GGData') as data:
                data.return_value.get_data.return_value = {
                    'gg_enable': enabled, 'gg_auto': auto, 'gg_on': False,
                }
                handler.check_then_set_gg_status(task)
            if enabled and auto:
                handler.set.assert_called_once_with(True)
            else:
                handler.set.assert_not_called()
            handler.gg_reset.assert_not_called()


def test_unclassified_tasks_keep_the_current_gg_state():
    handler = make_handler('enable_all')
    handler.check_then_set_gg_status('research')
    handler.check_status.assert_not_called()
