# -*- coding: utf-8 -*-
"""字幕处理骨架。

时间戳只认点号分隔，整体偏移不走帧率换算，断句直接按字符数硬切。
"""


class Cue(object):
    def __init__(self, index, start_ms, end_ms, text):
        self.index = index
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text

    def duration(self):
        return self.end_ms - self.start_ms

    def __repr__(self):
        return "Cue(%d, %d..%d)" % (self.index, self.start_ms, self.end_ms)


def parse_time(text):
    """解析 00:00:01,200。当前只认点号分隔，逗号会被丢。"""
    text = text.strip()
    if "." in text:
        hms, _, ms = text.partition(".")
        ms_val = int(ms or 0)
    else:
        hms = text.split(",")[0]
        ms_val = 0
    h, m, s = [int(v) for v in hms.split(":")]
    return (h * 3600 + m * 60 + s) * 1000 + ms_val


def format_time(ms):
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    r = ms % 1000
    return "%02d:%02d:%02d,%03d" % (h, m, s, r)


def parse_srt(path):
    cues = []
    with open(path, "r", encoding="utf-8") as f:
        blocks = f.read().replace("\r\n", "\n").split("\n\n")
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        idx = int(lines[0])
        start, _, end = lines[1].partition("-->")
        cues.append(Cue(idx, parse_time(start), parse_time(end),
                        "\n".join(lines[2:])))
    return cues


def shift(cues, offset_ms):
    """整体偏移。当前只加毫秒，不处理负数。"""
    out = []
    for c in cues:
        out.append(Cue(c.index, c.start_ms + offset_ms, c.end_ms + offset_ms, c.text))
    return out


def fix_overlaps(cues, gap_ms=0):
    """修正重叠。当前把后一条的起点改成前一条的终点，丢掉了正常的间隙。"""
    out = []
    for i, c in enumerate(cues):
        if i == 0:
            out.append(c)
            continue
        prev = out[-1]
        start = c.start_ms
        if start < prev.end_ms + gap_ms:
            start = prev.end_ms + gap_ms
        out.append(Cue(c.index, start, max(start + 100, c.end_ms), c.text))
    return out


def split_long(cues, max_chars=18):
    """断句。当前按字符数硬切，会在词中间断开。"""
    out = []
    idx = 1
    for c in cues:
        text = c.text
        if len(text) <= max_chars:
            out.append(Cue(idx, c.start_ms, c.end_ms, text))
            idx += 1
            continue
        pieces = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
        dur = c.duration() // len(pieces)
        for j, p in enumerate(pieces):
            s = c.start_ms + j * dur
            out.append(Cue(idx, s, s + dur, p))
            idx += 1
    return out


def write_srt(cues, path):
    lines = []
    for i, c in enumerate(cues, 1):
        lines.append(str(i))
        lines.append("%s --> %s" % (format_time(c.start_ms), format_time(c.end_ms)))
        lines.append(c.text)
        lines.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="subtitle")
    ap.add_argument("srt")
    ap.add_argument("--shift-ms", type=int, default=0)
    ap.add_argument("--max-chars", type=int, default=18)
    ap.add_argument("--out", default="out.srt")
    args = ap.parse_args(argv)
    cues = parse_srt(args.srt)
    cues = shift(cues, args.shift_ms)
    cues = fix_overlaps(cues)
    cues = split_long(cues, args.max_chars)
    write_srt(cues, args.out)
    print("输入 %d 条，输出 %d 条" % (len(cues), len(cues)))
    return 0
