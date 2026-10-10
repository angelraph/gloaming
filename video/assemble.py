"""Cuts the recorded walkthrough into scenes, interleaves the motion-graphics clips, lays the
voice clips at their scenes over the music bed, and writes out/gloaming_demo.mp4."""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
VO = json.loads((HERE / "vo" / "durations.json").read_text())
CLIPS = HERE / "clips"
OUT = HERE / "out"

# (clip file, voice id or None, voice offset in the clip, fade in, fade out)
TIMELINE = [
    ("01_intro", "intro", 2.9, False, False),
    ("02_problem", "problem", 0.5, False, False),
    ("03_idea", "idea", 0.5, False, False),
    ("04_ch_desk", None, 0, False, False),
    ("05_hero", "hero", 0.4, True, True),
    ("06_ch_console", None, 0, False, False),
    ("07_book", "book", 0.4, True, False),
    ("08_market", "market", 0.3, False, False),
    ("09_spread", "spread", 0.3, False, False),
    ("10_risk", "risk", 0.3, False, True),
    ("11_ch_proof", None, 0, False, False),
    ("12_tape", "tape", 0.4, True, False),
    ("13_reasons", "reasons", 0.3, False, False),
    ("14_loop", "loop", 0.3, False, True),
    ("15_ch_record", None, 0, False, False),
    ("16_agent", "agent", 0.6, True, False),
    ("17_performance", "performance", 0.6, False, True),
    ("18_outro", "outro", 1.4, False, False),
]
SITE_SCENES = {"05_hero": "hero", "07_book": "book", "08_market": "market", "09_spread": "spread", "10_risk": "risk",
               "12_tape": "tape", "13_reasons": "reasons", "14_loop": "loop", "16_agent": "agent", "17_performance": "performance"}


def run(args):
    subprocess.run([FF, "-y", "-loglevel", "error", *args], check=True)


def probe(path):
    """Exact clip length from its decoded frame count (container durations can be a frame off,
    and those errors add up across the timeline and pull the voice out of sync)."""
    import re
    err = subprocess.run([FF, "-i", str(path), "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True).stderr
    frames = int(re.findall(r"frame=\s*(\d+)", err)[-1])
    return frames / FPS


def cut_site_scenes():
    frames = json.loads((HERE / "rec" / "frames.json").read_text())
    scenes = {s["id"]: s for s in json.loads((HERE / "rec" / "scenes.json").read_text())}
    fdir = HERE / "rec" / "frames"
    for clip, sid in SITE_SCENES.items():
        s = scenes[sid]
        a, b = s["start"], s["start"] + s["dur"]
        before = [f for f in frames if f["t"] <= a]
        inside = [f for f in frames if a < f["t"] < b]
        seq = ([before[-1]] if before else []) + inside
        lines = []
        for i, f in enumerate(seq):
            t0 = max(f["t"], a)
            t1 = seq[i + 1]["t"] if i + 1 < len(seq) else b
            lines.append(f"file '{(fdir / f['file']).as_posix()}'\nduration {max(t1 - t0, 0.001):.4f}")
        lines.append(f"file '{(fdir / seq[-1]['file']).as_posix()}'")
        lst = HERE / "rec" / f"{clip}.txt"
        lst.write_text("\n".join(lines))
        slow = s.get("slow", 1.0)
        # recorded at 1/slow speed: compress time back to normal, then sample at 30 fps
        run(["-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"setpts=PTS/{slow},fps={FPS},format=yuv420p,scale=1920:1080:flags=lanczos",
             "-t", f"{s['dur'] / slow:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "13", str(CLIPS / f"{clip}.mp4")])
        print("cut", clip, round(s["dur"] / slow, 2), "s from", len(seq), "frames", round(len(seq) * slow / s["dur"], 1), "fps")


def main():
    OUT.mkdir(exist_ok=True)
    cut_site_scenes()

    # video: fade where the live desk meets a card, then one concat
    parts, offsets, t = [], [], 0.0
    for clip, vo, vo_at, fin, fout in TIMELINE:
        src = CLIPS / f"{clip}.mp4"
        d = probe(src)
        f = []
        if fin:
            f.append("fade=t=in:st=0:d=0.45")
        if fout:
            f.append(f"fade=t=out:st={d - 0.45:.3f}:d=0.45")
        if f:
            dst = CLIPS / f"{clip}_f.mp4"
            run(["-i", str(src), "-vf", ",".join(f), "-c:v", "libx264", "-preset", "medium", "-crf", "13", "-pix_fmt", "yuv420p", str(dst)])
            src = dst
        parts.append(src)
        if vo:
            offsets.append((vo, t + vo_at))
        t += d
    total = t
    # the concat filter decodes every clip and keeps every frame (the concat demuxer dropped
    # frames at the joins); one encode puts every frame in the same standard format
    ins = []
    for part in parts:
        ins += ["-i", str(part)]
    graph = "".join(f"[{k}:v]scale=in_range=auto:out_range=tv,format=yuv420p,setsar=1[c{k}];" for k in range(len(parts)))
    graph += "".join(f"[c{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]"
    run([*ins, "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", str(OUT / "video.mp4")])
    print("video", round(total, 2), "s")

    # music bed sized to the cut, hit as the logo mark lands
    subprocess.run(["python", str(HERE / "music.py"), f"{total + 0.5:.2f}", "1.55", str(OUT / "music.wav")], check=True)

    # voice: each clip delayed to its scene, mixed, and the music ducked under it
    inputs, filt = ["-i", str(OUT / "music.wav")], []
    for i, (vo, at) in enumerate(offsets, start=1):
        inputs += ["-i", str(HERE / "vo" / f"{vo}.mp3")]
        ms = int(at * 1000)
        filt.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume=1.0[v{i}]")
    n = len(offsets)
    filt.append("".join(f"[v{i}]" for i in range(1, n + 1)) + f"amix=inputs={n}:normalize=0:dropout_transition=0[voice]")
    # padded with silence, so the ducking (which ends with its sidechain) runs the full length
    filt.append("[voice]apad[vp];[vp]asplit=2[vk][vm]")
    filt.append("[0:a]volume=0.55[bed]")
    filt.append("[bed][vk]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=600[ducked]")
    filt.append("[ducked][vm]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    run([*inputs, "-filter_complex", ";".join(filt), "-map", "[aout]", "-t", f"{total:.3f}", "-c:a", "pcm_s16le", str(OUT / "audio.wav")])

    run(["-i", str(OUT / "video.mp4"), "-i", str(OUT / "audio.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(OUT / "gloaming_demo.mp4")])
    print("done", OUT / "gloaming_demo.mp4", round(total, 1), "s")


if __name__ == "__main__":
    main()
