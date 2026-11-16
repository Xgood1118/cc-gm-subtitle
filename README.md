# 字幕时间轴处理

骨架能解析、能偏移、能修重叠、能断句、能写出 SRT，但每一步都有偏差。

## 已知缺口

- `parse_time` 只认点号分隔，SRT 标准用的是逗号，`00:00:01,200` 会被解析成 1200 之外的错值。
- `shift` 遇负数偏移会产生负时间，没有钳到 0。
- 不做帧率换算，23.976 与 25 帧之间的转换完全没处理。
- `fix_overlaps` 把后一条起点强行推到前一条终点，原本有正常间隙的条目也被顶掉。
- `split_long` 按字符数硬切，中英文混排会在单词中间断开。
- 没有行宽与行数上限，超长条拆完仍是超长。

## 运行

```
python gen_samples.py
python -m subtitle.cli data/demo.srt --shift-ms 0 --max-chars 18 --out out.srt
python -m pytest tests -q
```

`demo.srt` 五条：第一条时间戳用逗号分隔，第二条与第一条重叠，第三条超长中英混排，
第四条含帧率说明，第五条正常短句。
