# -*- coding: utf-8 -*-
"""生成一份带重叠、超长行、英文混排的字幕。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SRT = """1
00:00:01,200 --> 00:00:03,000
开场第一句话，这里测试时间戳是否被正确解析。

2
00:00:02,500 --> 00:00:04,800
这一条与上一条重叠了一部分，用来检查时间轴修正。

3
00:00:05,000 --> 00:00:09,500
这一条字幕特别长，需要被拆成多行显示，但拆分的时候不能把英文单词和中文词组切断，否则看起来非常别扭而且不符合排版规范。

4
00:00:10,000 --> 00:00:12,000
Frame rate conversion 23.976 to 25 fps

5
00:00:12,500 --> 00:00:13,200
短句。
"""

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "demo.srt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(SRT)
    print("已生成", path)
