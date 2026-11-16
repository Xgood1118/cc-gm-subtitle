# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subtitle.core import Cue, format_time, parse_srt, parse_time  # noqa: E402


def test_parse_time_point():
    assert parse_time("00:00:01.200") == 1200


def test_format_time():
    assert format_time(1200) == "00:00:01,200"


def test_cue_duration():
    c = Cue(1, 100, 900, "hi")
    assert c.duration() == 800


def test_parse_srt_count():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "demo.srt")
    if not os.path.exists(path):
        return
    cues = parse_srt(path)
    assert len(cues) == 5
