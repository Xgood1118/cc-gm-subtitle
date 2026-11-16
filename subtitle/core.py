# -*- coding: utf-8 -*-
"""字幕时间轴与断句处理（仅使用 Python 标准库）。

时间戳同时接受逗号与点号分隔；整体偏移会钳制到非负；支持 23.976 与 25 fps
之间的帧率换算；重叠修正只动真正重叠的条目并保留原有间隙；断句以词/标点为
断点，英文单词不会被切断，每行宽度受 ``max_chars`` 约束，拆分后的时间按文本
长度成比例分配。
"""
import re
from fractions import Fraction


# 修正重叠后单条字幕允许的最小持续时间（毫秒）。
MIN_DURATION_MS = 500

# 行首避头尾：这些标点不能出现在一行开头。
NO_LINE_START = set("，。！？；：、）】」』》…·”’%‰.,!?;:")
# 行末避头尾：这些标点不能出现在一行结尾。
NO_LINE_END = set("（【「『《“‘(")

# 常见帧率的精确有理值，23.976 fps 即 24000/1001。
FPS_PRESETS = {
    "23.976": Fraction(24000, 1001),
    "24000/1001": Fraction(24000, 1001),
    "24": Fraction(24),
    "25": Fraction(25),
    "30": Fraction(30),
    "30000/1001": Fraction(30000, 1001),
}

_TOKEN_RE = re.compile(
    r"(?P<newline>\n)"
    r"|(?P<space>[^\S\n]+)"
    r"|(?P<word>[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*(?:\.[A-Za-z0-9]+)*)"
    r"|(?P<cjk>[㐀-䶿一-鿿豈-﫿])"
    r"|(?P<punct>.)"
)


class Cue(object):
    def __init__(self, index, start_ms, end_ms, text):
        self.index = index
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text

    def duration(self):
        return self.end_ms - self.start_ms

    def __eq__(self, other):
        if not isinstance(other, Cue):
            return NotImplemented
        return (
            self.index == other.index
            and self.start_ms == other.start_ms
            and self.end_ms == other.end_ms
            and self.text == other.text
        )

    def __repr__(self):
        return "Cue(%d, %d..%d)" % (self.index, self.start_ms, self.end_ms)


def parse_time(text):
    """解析 ``HH:MM:SS,mmm`` 或 ``HH:MM:SS.mmm`` 形式的时间戳为毫秒。

    逗号与点号分隔等价；小数部分不足三位时右侧补零（``.2`` 视为 200ms），
    超过三位时截断；也接受没有小数部分的 ``HH:MM:SS`` 与 ``MM:SS``。
    """
    text = text.strip()
    if "," in text:
        hms, _, frac = text.partition(",")
    elif "." in text:
        hms, _, frac = text.partition(".")
    else:
        hms, frac = text, ""
    parts = hms.strip().split(":")
    if len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        h, m, s = parts
    frac = (frac or "").strip()
    if frac:
        ms_val = int(frac.ljust(3, "0")[:3])
    else:
        ms_val = 0
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + ms_val


def format_time(ms):
    """把毫秒格式化为 SRT 标准时间戳 ``HH:MM:SS,mmm``，负值钳为 0。"""
    ms = max(0, int(ms))
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    r = ms % 1000
    return "%02d:%02d:%02d,%03d" % (h, m, s, r)


def parse_srt(path):
    """读取 SRT 文件，返回 :class:`Cue` 列表，容忍 BOM 与 CRLF。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read().replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in content.split("\n\n"):
        lines = [line.rstrip() for line in block.split("\n") if line.strip()]
        if len(lines) < 3:
            continue
        idx = int(lines[0].strip())
        start, _, end = lines[1].partition("-->")
        cues.append(
            Cue(
                idx,
                parse_time(start),
                parse_time(end),
                "\n".join(lines[2:]),
            )
        )
    return cues


def shift(cues, offset_ms):
    """整体平移 ``offset_ms`` 毫秒，结果钳制到非负且保持起止有序。"""
    out = []
    for c in cues:
        start = max(0, c.start_ms + offset_ms)
        end = max(start, c.end_ms + offset_ms)
        out.append(Cue(c.index, start, end, c.text))
    return out


def _fps_fraction(value):
    """把帧率参数转成精确 Fraction，23.976 映射为 24000/1001。"""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, str):
        v = value.strip()
        if v in FPS_PRESETS:
            return FPS_PRESETS[v]
        if "/" in v:
            num, den = v.split("/", 1)
            return Fraction(int(num), int(den))
        return Fraction(v)
    if isinstance(value, float):
        if abs(value - 24000.0 / 1001.0) < 1e-9:
            return Fraction(24000, 1001)
        return Fraction(str(value))
    return Fraction(value)


def convert_framerate(cues, src_fps, dst_fps):
    """按帧率比例缩放全部时间戳。

    新时间 = 旧时间 × src_fps / dst_fps（同一批画面在不同帧率下播放，
    时间轴与帧率成反比）。23.976 按精确值 24000/1001 参与运算，毫秒
    结果四舍五入，往返换算只引入舍入级误差。
    """
    src = _fps_fraction(src_fps)
    dst = _fps_fraction(dst_fps)
    factor = src / dst

    def scale(t):
        return int((t * factor.numerator * 2 + factor.denominator)
                   // (2 * factor.denominator))

    out = []
    for c in cues:
        out.append(Cue(c.index, scale(c.start_ms), scale(c.end_ms), c.text))
    return out


def fix_overlaps(cues, gap_ms=0, min_duration_ms=MIN_DURATION_MS):
    """修正相邻条目间的真正重叠。

    - 只有当后一条起点早于前一条终点（加 ``gap_ms`` 间隔）时才后移起点，
      原本不相接的条目之间的间隙原样保留。
    - 每条修正后的时长不短于 ``min_duration_ms``，不足则延长终点。
    - 起点只会被推迟、不会被提前。
    """
    out = []
    for c in cues:
        if not out:
            start = c.start_ms
        else:
            prev = out[-1]
            earliest = prev.end_ms + gap_ms
            start = earliest if c.start_ms < earliest else c.start_ms
        end = max(c.end_ms, start + min_duration_ms)
        out.append(Cue(c.index, start, end, c.text))
    return out


def _tokenize(text):
    """把文本切成 (文本, 类型) token；换行是硬断点，空格是软断点。"""
    return [(m.group(0), m.lastgroup) for m in _TOKEN_RE.finditer(text)]


def _render(tokens):
    return "".join(t for t, _ in tokens).strip()


def _wrap_lines(text, max_chars):
    """把单行文本按宽度上限断成多行。

    英文/数字单词是不可拆分的整体；CJK 字符之间允许断点；空格是软断点
    且换行时被消耗；标点优先附在所属内容一侧，再做避头尾级联调整。除
    单个不可拆分单词本身超长的极端情况外，每行都保证不超过 ``max_chars``。
    """
    if text == "":
        return [""]

    # 第一遍：贪心装行，token 形式保留，便于之后挪动断点。
    lines = [[]]
    for token, kind in _tokenize(text):
        if kind == "newline":
            if lines[-1]:
                lines.append([])
            continue
        if kind == "space":
            if lines[-1]:
                lines[-1].append((token, kind))
            continue
        cur_width = len(_render(lines[-1]))
        if lines[-1] and cur_width + (1 if cur_width else 0) + len(token) > max_chars:
            while lines[-1] and lines[-1][-1][1] == "space":
                lines[-1].pop()
            lines.append([])
        lines[-1].append((token, kind))
    if not lines[-1]:
        lines.pop()

    def width(ln):
        return len(_render(ln))

    def cascade(boundary):
        """把 boundary 行末 token 级联后移，保持所有中间行宽度不变。

        成功返回新的行列表；会导致任何一行超宽则返回 None，调用方放弃
        这次避头尾调整（宽度上限是硬约束，避头尾是尽力而为）。
        """
        new = [list(ln) for ln in lines]
        token = new[boundary].pop()
        pos = boundary + 1
        new[pos].insert(0, token)
        while width(new[pos]) > max_chars and pos + 1 < len(new):
            token = new[pos].pop()
            pos += 1
            new[pos].insert(0, token)
        if width(new[pos]) > max_chars:
            return None
        return new

    # 第二遍：避头尾。行首不能是结束类标点，行末不能是开始类标点。
    i = 0
    while i < len(lines) - 1:
        head = lines[i + 1][0][0]
        tail = lines[i][-1][0]
        if head in NO_LINE_START or tail in NO_LINE_END:
            shifted = cascade(i)
            if shifted is not None:
                lines = shifted
        i += 1

    return [_render(ln) for ln in lines]


def split_long(cues, max_chars=18):
    """按行宽上限断句，返回重新连续编号的新列表。

    原文每行都不超限的条目原样保留；超限条目先断行，再按各行文本长度
    占比分配原条目的持续时间，最后一条的终点严格等于原终点。
    """
    out = []
    idx = 1
    for c in cues:
        src_lines = c.text.split("\n")
        if all(len(line) <= max_chars for line in src_lines):
            out.append(Cue(idx, c.start_ms, c.end_ms, c.text))
            idx += 1
            continue

        pieces = []
        for src_line in src_lines:
            pieces.extend(_wrap_lines(src_line, max_chars))

        weights = [len(p) for p in pieces]
        total = sum(weights)
        duration = c.duration()
        cursor = c.start_ms
        accumulated = 0
        for j, piece in enumerate(pieces):
            accumulated += weights[j]
            if j == len(pieces) - 1:
                end = c.end_ms
            else:
                end = c.start_ms + (duration * accumulated + total // 2) // total
            end = max(end, cursor + 1)
            out.append(Cue(idx, cursor, end, piece))
            cursor = end
            idx += 1
    return out


def write_srt(cues, path):
    """写出 SRT：序号从 1 连续编号，UTF-8、LF 结尾，输出确定可复现。"""
    blocks = []
    for i, c in enumerate(cues, 1):
        blocks.append(
            "%d\n%s --> %s\n%s"
            % (i, format_time(c.start_ms), format_time(c.end_ms), c.text)
        )
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n\n".join(blocks) + "\n")


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(prog="subtitle")
    ap.add_argument("srt")
    ap.add_argument("--shift-ms", type=int, default=0)
    ap.add_argument("--max-chars", type=int, default=18)
    ap.add_argument("--out", default="out.srt")
    ap.add_argument("--fps-from", default=None,
                    help="源帧率，如 23.976 / 25，与 --fps-to 同时给出")
    ap.add_argument("--fps-to", default=None,
                    help="目标帧率，如 23.976 / 25")
    args = ap.parse_args(argv)

    cues = parse_srt(args.srt)
    count_in = len(cues)
    cues = shift(cues, args.shift_ms)
    if args.fps_from is not None and args.fps_to is not None:
        cues = convert_framerate(cues, args.fps_from, args.fps_to)
    cues = fix_overlaps(cues)
    cues = split_long(cues, args.max_chars)
    write_srt(cues, args.out)
    print("输入 %d 条，输出 %d 条" % (count_in, len(cues)))
    return 0
