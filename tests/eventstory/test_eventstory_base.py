"""Regression checks for story battles and cross-task event settings."""

from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from module.eventstory.eventstory_base import EventStoryBase


def make_story(allow_restart):
    return SimpleNamespace(
        ui_goto_event_story=Mock(side_effect=['story', 'finish']),
        event_story=Mock(return_value='battle'),
        allow_event_battle_kill_game=allow_restart,
        combat_expected_end=Mock(return_value=True),
        config=SimpleNamespace(override=Mock()),
        device=SimpleNamespace(),
        app_stop=Mock(),
        app_start=Mock(),
    )


def test_story_battle_finishes_combat_and_returns_to_story_page():
    story = make_story(allow_restart=False)
    calls = []

    def execute():
        calls.append('execute')

    def status(*, expected_end):
        calls.append('status')
        assert expected_end is story.combat_expected_end
        assert expected_end()

    story.combat_execute = execute
    story.combat_status = status

    EventStoryBase.run_event_story(story)

    assert calls == ['execute', 'status']
    story.app_stop.assert_not_called()
    story.app_start.assert_not_called()
    story.config.override.assert_not_called()
    assert story.ui_goto_event_story.call_count == 2


def test_story_battle_can_still_use_restart_shortcut():
    story = make_story(allow_restart=True)
    lifecycle = Mock()
    story.app_stop = lifecycle.stop
    story.app_start = lifecycle.start
    story.combat_execute = Mock()
    story.combat_status = Mock()

    with patch('module.eventstory.eventstory_base.GGHandler') as manager:
        lifecycle.attach_mock(manager.return_value, 'gg')
        EventStoryBase.run_event_story(story)

    assert lifecycle.mock_calls == [
        call.stop(), call.start(), call.gg.check_then_set_gg_status('event_story'),
    ]
    story.config.override.assert_called_once_with(Error_HandleError=True)
    story.combat_execute.assert_not_called()
    story.combat_status.assert_not_called()
    assert story.ui_goto_event_story.call_count == 2


def make_configured_story(event):
    story = object.__new__(EventStoryBase)
    story.config = SimpleNamespace(
        Campaign_Event='campaign_main',
        cross_get=lambda key, default=None: event if key == 'Event.Campaign.Event' else default,
    )
    return story


def test_alchemist_story_uses_event_task_settings():
    for event in ['event_20250724_cn', 'event_20221124_cn']:
        assert make_configured_story(event).is_event_20250724 is True
    assert make_configured_story('coalition_20261124').is_event_20250724 is False


def test_abyss_story_uses_event_task_settings():
    assert make_configured_story('event_20250814_cn').is_event_20250814 is True
    assert make_configured_story('event_20250724_cn').is_event_20250814 is False


def test_story_restart_policy_uses_event_task_settings():
    assert make_configured_story('event_20260908_cn').allow_event_battle_kill_game is False
    assert make_configured_story('event_20250724_cn').allow_event_battle_kill_game is True


def test_story_tool_checks_gg_after_starting_game():
    for running in [False, True]:
        lifecycle = Mock()
        story = SimpleNamespace(
            config=SimpleNamespace(cross_get=lambda *args: ''),
            device=SimpleNamespace(app_is_running=lambda: running),
            app_start=lifecycle.start,
            run_event_story=lifecycle.story,
        )
        with patch('module.eventstory.eventstory_base.GGHandler') as manager:
            lifecycle.attach_mock(manager.return_value, 'gg')
            EventStoryBase.run(story)
            manager.assert_called_once_with(config=story.config, device=story.device)

        expected = [call.gg.check_config()]
        if not running:
            expected.append(call.start())
        expected += [call.gg.check_then_set_gg_status('event_story'), call.story()]
        assert lifecycle.mock_calls == expected


def test_unavailable_story_does_not_start_gg():
    story = SimpleNamespace(config=SimpleNamespace(cross_get=lambda *args: 'event_20260226_cn'))
    with patch('module.eventstory.eventstory_base.GGHandler') as manager:
        EventStoryBase.run(story)
        manager.assert_not_called()
