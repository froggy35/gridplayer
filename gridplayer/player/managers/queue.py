"""Queue mode: a long playlist fed through a limited number of grid slots.

The playlist is one shared queue. Only ``slots`` videos play at the same
time; whenever one of them finishes, only that cell is handed the next
video from the queue, while every other cell keeps playing untouched.

    Playlist -> queue -> free grid slots

With repeat on, the queue wraps around to the first video after the last
one and playback goes on forever.
"""

import random

from gridplayer.dialogs.input_dialog import QCustomSpinboxInput
from gridplayer.models.video import Video
from gridplayer.params.static import VideoInitialState
from gridplayer.player.managers.base import ManagerBase
from gridplayer.utils.qt import translate

DEFAULT_SLOTS = 4
MAX_SLOTS = 64


class QueueManager(ManagerBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._ctx.is_queue_mode = False

        self._slots = DEFAULT_SLOTS
        self._is_repeat = True

        # templates of every video in the playlist, in playlist order
        self._queue: list[Video] = []
        # index of the next template to hand out
        self._cursor = 0

    @property
    def commands(self):
        return {
            "toggle_queue_mode": self.toggle_queue_mode,
            "is_queue_mode": lambda: self._ctx.is_queue_mode,
            "ask_queue_slots": self.ask_queue_slots,
            "get_queue_slots": lambda: str(self._slots),
            "toggle_queue_repeat": self.toggle_queue_repeat,
            "is_queue_repeat": lambda: self._is_repeat,
            "get_queue_progress": self.get_queue_progress,
            "queue_add": self.queue_add,
        }

    # --- mode ---

    def toggle_queue_mode(self):
        if self._ctx.is_queue_mode:
            self._leave_queue_mode()
        else:
            self._enter_queue_mode()

    def _enter_queue_mode(self):
        """Turn what is on screen into the queue without restarting anything.

        The first ``slots`` videos in grid order stay exactly as they are and
        keep playing; the rest are closed and wait in the queue.
        """

        self._ctx.is_queue_mode = True

        blocks = self._blocks_in_grid_order()

        self._queue = [_template_from(vb.video_params) for vb in blocks]
        self._cursor = min(self._slots, len(self._queue))

        extra = blocks[self._slots :]
        if extra:
            self._ctx.commands.remove_video_blocks([vb.video_id for vb in extra])

        self._log.debug(
            f"Queue mode on: {len(self._queue)} videos, {self._slots} slots"
        )

    def _leave_queue_mode(self):
        """Keep whatever is playing, forget the queue."""

        self._ctx.is_queue_mode = False
        self._queue = []
        self._cursor = 0

        self._log.debug("Queue mode off")

    # --- settings ---

    def ask_queue_slots(self):
        slots = QCustomSpinboxInput.get_int(
            parent=self.parent(),
            title=translate("Queue", "Videos playing at the same time"),
            initial_value=self._slots,
            _min=1,
            _max=MAX_SLOTS,
        )

        if slots == self._slots:
            return

        self._slots = slots

        if self._ctx.is_queue_mode:
            self._apply_slot_count()

    def _apply_slot_count(self):
        blocks = self._blocks_in_grid_order()

        if len(blocks) > self._slots:
            extra = blocks[self._slots :]
            self._ctx.commands.remove_video_blocks([vb.video_id for vb in extra])
            return

        self._fill_free_slots()

    def toggle_queue_repeat(self):
        self._is_repeat = not self._is_repeat

    def get_queue_progress(self):
        if not self._queue:
            return "0 / 0"
        return f"{min(self._cursor, len(self._queue))} / {len(self._queue)}"

    # --- feeding the queue ---

    def queue_add(self, videos):
        """New videos go to the end of the queue; free slots get filled."""

        videos = [_template_from(v) for v in videos]

        if self._ctx.is_shuffle_on_load:
            random.shuffle(videos)

        self._queue.extend(videos)

        self._fill_free_slots()

    def on_videos_loaded(self, videos):
        """A playlist file was opened."""

        if self._ctx.is_queue_mode:
            self.queue_add(videos)
            return

        self._ctx.commands.add_video_blocks(videos)

    def on_playlist_closed(self):
        self._queue = []
        self._cursor = 0

    def _fill_free_slots(self):
        free = self._slots - len(self._ctx.video_blocks)
        if free <= 0:
            return

        to_add = []
        for _ in range(free):
            template = self._take_next(extra_on_screen=to_add)
            if template is None:
                break
            to_add.append(template)

        if to_add:
            self._ctx.commands.add_videos_to_layout_direct(
                [_fresh_video(t) for t in to_add]
            )

    # --- a slot finished ---

    def on_slot_finished(self, block_id):
        if not self._ctx.is_queue_mode:
            return

        vb = self._ctx.video_blocks.by_id(block_id)
        if vb is None:
            return

        template = self._take_next(leaving=vb)

        if template is None:
            # queue ran out and repeat is off
            vb.stop_playback()
            return

        vb.queue_load(template)

    def _take_next(self, leaving=None, extra_on_screen=()):
        """Hand out the next template from the queue.

        Tries not to put a video on screen twice: if the next one in line is
        already playing in another cell (only possible with short playlists
        right after wrapping around), it looks further along the queue.
        """

        total = len(self._queue)
        if total == 0:
            return None

        if self._cursor >= total:
            if not self._is_repeat:
                return None
            self._cursor = 0

        on_screen = {
            str(vb.video_params.uri)
            for vb in self._ctx.video_blocks
            if vb is not leaving and vb.video_params is not None
        }
        on_screen.update(str(t.uri) for t in extra_on_screen)

        look_ahead = total if self._is_repeat else total - self._cursor

        for step in range(look_ahead):
            index = (self._cursor + step) % total
            template = self._queue[index]
            if str(template.uri) not in on_screen:
                self._cursor = index + 1
                return template

        # everything in the queue is on screen already
        if leaving is not None:
            # the finished cell just plays its own video again
            return _template_from(leaving.video_params)

        return None

    def _blocks_in_grid_order(self):
        order = self._ctx.commands.layout_order()
        blocks = self._ctx.video_blocks.blocks_for_ids(order)

        # anything the layout does not know about goes last
        placed = set(blocks)
        blocks.extend(vb for vb in self._ctx.video_blocks if vb not in placed)

        return blocks


def _template_from(video: Video) -> Video:
    return video.model_copy(deep=True)


def _fresh_video(template: Video) -> Video:
    """A new, independent video for a new cell, starting from the top."""

    return Video(
        uri=template.uri,
        title=template.title,
        external_audio=list(template.external_audio),
        external_subtitles=list(template.external_subtitles),
        # a queue that starts paused would never move on
        playback_state=VideoInitialState.PLAYING,
    )
