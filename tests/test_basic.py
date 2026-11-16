# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subtitle.core import (  # noqa: E402
    Cue,
    convert_framerate,
    fix_overlaps,
    format_time,
    parse_srt,
    parse_time,
    shift,
    split_long,
    write_srt,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo.srt")


def test_parse_time_point():
    assert parse_time("00:00:01.200") == 1200


def test_parse_time_comma():
    """SRT 标准逗号分隔，毫秒不能丢。"""
    assert parse_time("00:00:01,200") == 1200
    assert parse_time("01:02:03,456") == 3723456


def test_parse_time_fraction_padding():
    assert parse_time("00:00:01.2") == 1200
    assert parse_time("00:00:01.20") == 1200
    assert parse_time("00:00:01") == 1000
    assert parse_time("10:05,007") == 605007


def test_format_time():
    assert format_time(1200) == "00:00:01,200"
    assert format_time(-10) == "00:00:00,000"


def test_cue_duration():
    c = Cue(1, 100, 900, "hi")
    assert c.duration() == 800


def test_parse_srt_count():
    if not os.path.exists(DEMO):
        return
    cues = parse_srt(DEMO)
    assert len(cues) == 5
    # 逗号时间戳的毫秒被正确保留。
    assert cues[0].start_ms == 1200


def test_negative_shift_is_clamped():
    """负偏移后不能出现负时间，且起止保持有序。"""
    cues = [Cue(1, 500, 1500, "a"), Cue(2, 3000, 4000, "b")]
    out = shift(cues, -2000)
    assert out[0].start_ms == 0
    assert out[0].end_ms == 0
    assert out[1].start_ms == 1000
    assert out[1].end_ms == 2000
    for c in out:
        assert c.start_ms >= 0 and c.end_ms >= c.start_ms


def test_fix_overlaps_preserves_gap():
    """真正重叠的被修正，本来不相接的间隙原样保留。"""
    cues = [
        Cue(1, 0, 1000, "a"),
        Cue(2, 2000, 3000, "b"),       # 与上一条有 1000ms 间隙
        Cue(3, 2500, 4000, "c"),       # 与上一条真正重叠
    ]
    out = fix_overlaps(cues)
    assert out[1].start_ms == 2000          # 间隙保留，不被顶动
    assert out[2].start_ms == 3000          # 重叠被推到上一条终点
    assert out[2].end_ms >= out[2].start_ms + 500


def test_fix_overlaps_min_duration():
    cues = [
        Cue(1, 0, 2000, "a"),
        Cue(2, 1500, 1800, "b"),
    ]
    out = fix_overlaps(cues)
    assert out[1].start_ms == 2000
    assert out[1].duration() >= 500


def test_split_does_not_break_english_word():
    text = "Frame rate conversion 23.976 to 25 fps"
    cues = [Cue(1, 0, 10000, text)]
    out = split_long(cues, max_chars=18)
    words = text.split()
    for c in out:
        for line in c.text.split("\n"):
            # 每行每个英文单词都必须完整出现在原文里。
            for w in line.split():
                assert w in words
            assert len(line) <= 18


def test_split_line_width_limit():
    cues = [
        Cue(1, 0, 10000,
            "这一条字幕特别长，需要被拆成多行显示，但拆分的时候不能把英文"
            "单词和中文词组切断，否则看起来非常别扭而且不符合排版规范。")
    ]
    out = split_long(cues, max_chars=18)
    assert len(out) > 1
    for c in out:
        for line in c.text.split("\n"):
            assert len(line) <= 18


def test_split_time_proportional_and_contiguous():
    cues = [Cue(1, 0, 10000, "Frame rate conversion 23.976 to 25 fps")]
    out = split_long(cues, max_chars=18)
    # 时间连续、覆盖原区间。
    assert out[0].start_ms == 0
    assert out[-1].end_ms == 10000
    for a, b in zip(out, out[1:]):
        assert a.end_ms == b.start_ms
    # 时长与文本长度正相关。
    assert out[0].duration() > out[-1].duration() or len(out) == 1


def test_short_cue_passes_through():
    cues = [Cue(7, 100, 900, "短句。")]
    out = split_long(cues, max_chars=18)
    assert len(out) == 1
    assert out[0].text == "短句。"
    assert out[0].start_ms == 100 and out[0].end_ms == 900


def test_framerate_23976_to_25():
    # 1 秒（1000ms）在 23.976 帧素材转到 25fps：1000 * (24000/1001) / 25
    cues = [Cue(1, 0, 1000, "x")]
    out = convert_framerate(cues, "23.976", "25")
    expected = round(1000 * (24000.0 / 1001.0) / 25.0)
    assert out[0].end_ms == expected


def test_framerate_roundtrip():
    cues = [Cue(1, 1200, 98765, "x")]
    once = convert_framerate(cues, "23.976", "25")
    back = convert_framerate(once, "25", "23.976")
    # 往返只允许舍入级（不超过 2ms）误差。
    assert abs(back[0].start_ms - 1200) <= 2
    assert abs(back[0].end_ms - 98765) <= 2


def test_write_and_reread_roundtrip(tmp_path):
    path = os.path.join(str(tmp_path), "x.srt")
    cues = [
        Cue(1, 1200, 3000, "第一行\n第二行"),
        Cue(2, 3500, 4000, "hello world"),
    ]
    write_srt(cues, path)
    reread = parse_srt(path)
    assert len(reread) == len(cues)
    for a, b in zip(reread, cues):
        assert a.start_ms == b.start_ms
        assert a.end_ms == b.end_ms
        assert a.text == b.text
    # 序号从 1 连续。
    assert [c.index for c in parse_srt(path)] == [1, 2]


def test_two_runs_byte_identical(tmp_path):
    """连续跑两次，输出逐字节相同。"""
    out1 = os.path.join(str(tmp_path), "a.srt")
    out2 = os.path.join(str(tmp_path), "b.srt")
    if not os.path.exists(DEMO):
        return
    from subtitle.core import main

    main([DEMO, "--shift-ms", "0", "--max-chars", "18", "--out", out1])
    main([DEMO, "--shift-ms", "0", "--max-chars", "18", "--out", out2])
    with open(out1, "rb") as f:
        b1 = f.read()
    with open(out2, "rb") as f:
        b2 = f.read()
    assert b1 == b2

    # 读回后条目数与写出的条目一一对应。
    cues = parse_srt(out1)
    assert len(cues) >= 5
    assert [c.index for c in cues] == list(range(1, len(cues) + 1))
