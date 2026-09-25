"""Queue mode: a long playlist fed through a fixed number of grid cells."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gridplayer.models.video import Video
from gridplayer.params.static import VideoEndAction
from gridplayer.player.manager import Commands, Context
from gridplayer.player.managers.queue import QueueManager
from gridplayer.widgets.video_block import VideoBlock


def _video(n):
    return Video(uri=f"https://example.com/video_{n}.mp4")


class FakeBlock:
    def __init__(self, video):
        self.video_params = video
        self.id = f"block-{video.uri}"
        self.loaded = []
        self.stopped = False

    @property
    def video_id(self):
        return str(self.video_params.id)

    def queue_load(self, template):
        self.loaded.append(template)
        self.video_params = template.model_copy()

    def stop_playback(self):
        self.stopped = True


class FakeBlocks(list):
    def by_id(self, _id):
        return next((b for b in self if b.id == _id), None)

    def blocks_for_ids(self, ids):
        return [b for i in ids for b in self if b.video_id == i]


@pytest.fixture
def queue():
    ctx = Context()
    ctx.commands = Commands()
    ctx.video_blocks = FakeBlocks()
    ctx.is_shuffle_on_load = False

    def add_direct(videos):
        added = [FakeBlock(v) for v in videos]
        ctx.video_blocks.extend(added)
        return added

    def remove(ids):
        for b in [b for b in ctx.video_blocks if b.video_id in ids]:
            ctx.video_blocks.remove(b)

    ctx.commands.update(
        {
            "add_videos_to_layout_direct": add_direct,
            "remove_video_blocks": remove,
            "layout_order": lambda: [b.video_id for b in ctx.video_blocks],
            "add_video_blocks": add_direct,
        }
    )

    manager = QueueManager(context=ctx, parent=None)
    ctx.commands.update(manager.commands)
    return SimpleNamespace(manager=manager, ctx=ctx)


def _on_screen(ctx):
    return [str(b.video_params.uri).rsplit("_", 1)[1] for b in ctx.video_blocks]


def _finish(q, cell_index):
    block = q.ctx.video_blocks[cell_index]
    q.manager.on_slot_finished(block.id)
    return block


def test_only_slot_count_videos_are_opened(queue):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 101)])

    assert _on_screen(queue.ctx) == ["1.mp4", "2.mp4", "3.mp4", "4.mp4"]
    assert queue.manager.get_queue_progress() == "4 / 100"


def test_finished_cell_alone_gets_the_next_video(queue):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 101)])

    others = [queue.ctx.video_blocks[i] for i in (0, 2, 3)]

    _finish(queue, 1)  # video 2 is done
    assert _on_screen(queue.ctx) == ["1.mp4", "5.mp4", "3.mp4", "4.mp4"]

    _finish(queue, 3)  # video 4 is done
    assert _on_screen(queue.ctx) == ["1.mp4", "5.mp4", "3.mp4", "6.mp4"]

    # cells 1 and 3 were never touched
    assert not others[0].loaded
    assert not others[1].loaded


def test_queue_wraps_around_when_repeating(queue):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 7)])  # 6 videos

    _finish(queue, 0)  # -> 5
    _finish(queue, 1)  # -> 6
    _finish(queue, 2)  # -> wraps, 1
    assert _on_screen(queue.ctx) == ["5.mp4", "6.mp4", "1.mp4", "4.mp4"]


def test_queue_stops_at_the_end_without_repeat(queue):
    queue.manager.toggle_queue_repeat()
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 6)])  # 5 videos

    _finish(queue, 0)  # -> 5
    block = _finish(queue, 1)  # nothing left
    assert block.stopped


def test_no_video_is_shown_twice_after_wrapping(queue):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 6)])  # 5 videos

    _finish(queue, 0)  # -> 5
    # the next in line (1) is not on screen any more, fine
    _finish(queue, 1)  # -> 1
    # next in line is 2, which just left cell 1: allowed
    _finish(queue, 2)  # -> 2 would be fine, 3 is leaving itself
    screen = _on_screen(queue.ctx)
    assert len(set(screen)) == len(screen)


def test_short_playlist_cell_replays_its_own_video(queue):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 5)])  # 4 = slots

    _finish(queue, 1)
    assert _on_screen(queue.ctx) == ["1.mp4", "2.mp4", "3.mp4", "4.mp4"]


def test_entering_queue_mode_keeps_first_cells_playing(queue):
    queue.ctx.commands.add_videos_to_layout_direct([_video(n) for n in range(1, 11)])
    first_four = list(queue.ctx.video_blocks[:4])

    queue.manager.toggle_queue_mode()

    assert list(queue.ctx.video_blocks) == first_four
    assert queue.manager.get_queue_progress() == "4 / 10"

    _finish(queue, 0)
    assert _on_screen(queue.ctx)[0] == "5.mp4"


def test_more_slots_fill_from_the_queue(queue, mocker):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 21)])

    mocker.patch(
        "gridplayer.player.managers.queue.QCustomSpinboxInput.get_int",
        return_value=9,
    )
    queue.manager.ask_queue_slots()

    assert len(queue.ctx.video_blocks) == 9
    assert _on_screen(queue.ctx)[-1] == "9.mp4"


def test_fewer_slots_close_the_last_cells(queue, mocker):
    queue.manager.toggle_queue_mode()
    queue.manager.queue_add([_video(n) for n in range(1, 21)])

    mocker.patch(
        "gridplayer.player.managers.queue.QCustomSpinboxInput.get_int",
        return_value=2,
    )
    queue.manager.ask_queue_slots()

    assert _on_screen(queue.ctx) == ["1.mp4", "2.mp4"]


def test_normal_mode_ignores_finished_cells(queue):
    queue.ctx.commands.add_videos_to_layout_direct([_video(1)])
    block = _finish(queue, 0)
    assert not block.loaded


# --- the cell's side ---


def _mock_block(mocker, is_queue_mode, end_action=VideoEndAction.LOOP_FILE):
    block = mocker.Mock()
    block._ctx = SimpleNamespace(is_queue_mode=is_queue_mode)
    block.video_params.loop_start = None
    block.video_params.loop_end = None
    block.video_params.end_action = end_action
    block.id = "cell"
    return block


def test_cell_asks_the_queue_instead_of_looping(mocker):
    block = _mock_block(mocker, is_queue_mode=True)

    VideoBlock.loop_end_action(block)

    block.queue_end_reached.emit.assert_called_once_with("cell")
    block._loop_to_start.assert_not_called()


def test_cell_loops_as_usual_outside_queue_mode(mocker):
    block = _mock_block(mocker, is_queue_mode=False)

    VideoBlock.loop_end_action(block)

    block.queue_end_reached.emit.assert_not_called()
    block._loop_to_start.assert_called_once()


def test_ab_loop_still_wins_in_queue_mode(mocker):
    block = _mock_block(mocker, is_queue_mode=True)
    block.video_params.loop_start = 1000

    VideoBlock.loop_end_action(block)

    block.queue_end_reached.emit.assert_not_called()
    block._loop_to_start.assert_called_once()


def test_vlc_wrap_is_not_a_silent_loop_in_queue_mode(mocker):
    block = _mock_block(mocker, is_queue_mode=True)
    block.video_params.is_start_random = False

    VideoBlock._loop_wrapped(block)

    block.loop_end_action.assert_called_once()


def test_queue_load_swaps_the_file_but_keeps_the_cell(mocker):
    block = Mock()
    block._is_closing = False
    block._is_error = False
    block.is_video_initialized = True
    old = _video(1)
    old.volume = 0.3
    old.is_muted = True
    block.video_params = old
    cell_id = old.id

    VideoBlock.queue_load(block, _video(2))

    new = block.set_video.call_args.args[0]
    assert str(new.uri).endswith("video_2.mp4")
    assert new.id == cell_id
    assert new.volume == 0.3
    assert new.is_muted is True
    assert new.current_position == 0
