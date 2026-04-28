#!/usr/bin/env python3
"""
build_ambient_library.py — Synthesize 18 scene-ambient loops for foley layer.

Produces 4-second loopable WAVs in audio_engineering/assets/ambient/[name].wav.
Each ambient is designed to:
  • Sit at -28 dB under voice (continuous bed)
  • Loop seamlessly (matched ends + crossfade)
  • Match the EMOTIONAL tone of the scene type, not just literal sound

Categories cover the common scene types in our scripts:
  rain, wind, ocean, footsteps_pavement, footsteps_indoor, hospital_beeps,
  factory_industrial, lab_glassware, courtroom_murmur, city_traffic,
  office_keyboard, money_counting, crowd_chatter, heartbeat, sci_fi_data,
  paper_rustle, fire_crackle, water_drops

Synthesis: numpy + soundfile. No external APIs, no licenses to track.
"""
import math
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

OUT = Path(__file__).parent / "assets/ambient"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000
DUR = 4.0   # seconds — long enough to loop without artifact


def env_loop(n, fade=0.4):
    """Create a fade-in/fade-out envelope to make the buffer loop seamlessly."""
    fade_n = int(fade * SR)
    e = np.ones(n)
    e[:fade_n] = np.linspace(0, 1, fade_n)
    e[-fade_n:] = np.linspace(1, 0, fade_n)
    return e


def lowpass(x, cutoff_hz):
    """Simple one-pole lowpass."""
    rc = 1 / (2 * math.pi * cutoff_hz)
    dt = 1 / SR
    alpha = dt / (rc + dt)
    y = np.empty_like(x)
    y[0] = x[0] * alpha
    for i in range(1, len(x)):
        y[i] = y[i-1] + alpha * (x[i] - y[i-1])
    return y


def highpass(x, cutoff_hz):
    """Simple one-pole highpass."""
    rc = 1 / (2 * math.pi * cutoff_hz)
    dt = 1 / SR
    alpha = rc / (rc + dt)
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = alpha * (y[i-1] + x[i] - x[i-1])
    return y


def save(name, data, gain_db=0.0):
    n = int(DUR * SR)
    if len(data) < n:
        data = np.tile(data, math.ceil(n / len(data)))[:n]
    else:
        data = data[:n]
    data = data * env_loop(len(data))
    # Normalize then apply gain
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak * 0.85
    data = data * (10 ** (gain_db / 20))
    sf.write(OUT / f"{name}.wav", data, SR, subtype="PCM_16")
    print(f"  ✓ {name}.wav ({len(data)/SR:.1f}s)")


# ── Synthesis routines ──────────────────────────────────────────────────────

def make_rain():
    n = int(DUR * SR)
    # White noise → bandpass for rain hiss + occasional droplet bursts
    base = np.random.randn(n) * 0.5
    base = lowpass(base, 6000)
    base = highpass(base, 800)
    # Random droplet impacts
    for _ in range(int(DUR * 30)):
        pos = np.random.randint(100, n - 200)
        burst_len = np.random.randint(80, 200)
        burst = np.random.randn(burst_len) * np.linspace(1.0, 0.0, burst_len) * 1.5
        base[pos:pos+burst_len] += burst
    return base


def make_wind():
    n = int(DUR * SR)
    noise = np.random.randn(n) * 0.6
    noise = lowpass(noise, 1200)
    # Slow amplitude modulation (gusts)
    t = np.arange(n) / SR
    gust = 0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t) * np.cos(2 * np.pi * 0.7 * t)
    return noise * gust


def make_ocean():
    n = int(DUR * SR)
    noise = np.random.randn(n) * 0.5
    noise = lowpass(noise, 800)
    t = np.arange(n) / SR
    # Wave swell at ~0.25 Hz
    swell = 0.3 + 0.7 * (np.sin(2 * np.pi * 0.25 * t) ** 2)
    return noise * swell


def make_footsteps_pavement():
    n = int(DUR * SR)
    out = np.zeros(n)
    step_period = int(SR * 0.55)  # ~0.55s between steps (walking pace)
    for start in range(0, n, step_period):
        # Each step: short low-freq thump + gravel scrape
        thump_len = int(SR * 0.08)
        if start + thump_len >= n:
            break
        thump = np.random.randn(thump_len) * np.linspace(1.0, 0.0, thump_len)
        thump = lowpass(thump, 600)
        scrape_len = int(SR * 0.04)
        scrape = np.random.randn(scrape_len) * np.linspace(0.0, 0.6, scrape_len)
        scrape = highpass(scrape, 3000)
        out[start:start+thump_len] += thump * 1.2
        if start + thump_len + scrape_len < n:
            out[start+thump_len:start+thump_len+scrape_len] += scrape
    return out


def make_footsteps_indoor():
    n = int(DUR * SR)
    out = np.zeros(n)
    step_period = int(SR * 0.6)
    for start in range(0, n, step_period):
        click_len = int(SR * 0.04)
        if start + click_len >= n:
            break
        click = np.random.randn(click_len) * np.linspace(1.0, 0.0, click_len)
        click = highpass(click, 1500)
        click = lowpass(click, 5000)
        out[start:start+click_len] += click * 0.9
    return out


def make_hospital_beeps():
    n = int(DUR * SR)
    out = np.zeros(n)
    t = np.arange(n) / SR
    # Steady cardiac beep ~60 BPM (every second)
    beep_freq = 1000
    beep_len = int(SR * 0.08)
    beep = np.sin(2 * np.pi * beep_freq * np.arange(beep_len) / SR)
    beep = beep * np.exp(-np.arange(beep_len) / (SR * 0.03))
    for s in range(0, n, SR):
        if s + beep_len < n:
            out[s:s+beep_len] += beep * 0.5
    # Faint room tone
    room = np.random.randn(n) * 0.05
    room = lowpass(room, 2000)
    return out + room


def make_heartbeat():
    n = int(DUR * SR)
    out = np.zeros(n)
    bpm = 72
    period = int(SR * 60 / bpm)
    thump_len = int(SR * 0.12)
    thump = np.sin(2 * np.pi * 60 * np.arange(thump_len) / SR)
    thump = thump * np.exp(-np.arange(thump_len) / (SR * 0.05))
    for s in range(0, n, period):
        if s + thump_len < n:
            out[s:s+thump_len] += thump * 1.0
        # second beat ("dub") slightly later
        s2 = s + int(SR * 0.18)
        if s2 + thump_len < n:
            out[s2:s2+thump_len] += thump * 0.7
    return out


def make_factory_industrial():
    n = int(DUR * SR)
    t = np.arange(n) / SR
    # Low rumble + machine harmonics
    rumble = np.random.randn(n) * 0.5
    rumble = lowpass(rumble, 200)
    motor = 0.3 * np.sin(2 * np.pi * 60 * t) + 0.2 * np.sin(2 * np.pi * 120 * t)
    motor = motor * (0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * t))
    # Occasional clang
    out = rumble + motor
    for _ in range(int(DUR * 2)):
        pos = np.random.randint(1000, n - 2000)
        clang_len = 800
        clang = np.sin(2 * np.pi * 800 * np.arange(clang_len) / SR)
        clang = clang * np.exp(-np.arange(clang_len) / (SR * 0.1))
        out[pos:pos+clang_len] += clang * 0.4
    return out


def make_lab_glassware():
    n = int(DUR * SR)
    out = np.random.randn(n) * 0.05
    out = lowpass(out, 1500)
    # Occasional glass tinkles
    for _ in range(int(DUR * 4)):
        pos = np.random.randint(1000, n - 1000)
        tinkle_len = 600
        freq = np.random.uniform(2500, 4500)
        tinkle = np.sin(2 * np.pi * freq * np.arange(tinkle_len) / SR)
        tinkle = tinkle * np.exp(-np.arange(tinkle_len) / (SR * 0.05))
        out[pos:pos+tinkle_len] += tinkle * 0.3
    return out


def make_courtroom_murmur():
    n = int(DUR * SR)
    base = np.random.randn(n) * 0.3
    base = lowpass(base, 1500)
    base = highpass(base, 200)
    t = np.arange(n) / SR
    base = base * (0.6 + 0.3 * np.sin(2 * np.pi * 0.4 * t))
    return base


def make_city_traffic():
    n = int(DUR * SR)
    base = np.random.randn(n) * 0.4
    base = lowpass(base, 800)
    # Distant horn
    for _ in range(int(DUR * 0.5)):
        pos = np.random.randint(1000, n - 5000)
        horn_len = 4000
        horn = np.sin(2 * np.pi * 250 * np.arange(horn_len) / SR)
        horn = horn * np.exp(-np.arange(horn_len) / (SR * 0.4)) * 0.3
        base[pos:pos+horn_len] += horn
    return base


def make_office_keyboard():
    n = int(DUR * SR)
    out = np.zeros(n)
    # ~7 keystrokes per second cluster
    keystrokes = int(DUR * 7)
    for _ in range(keystrokes):
        pos = np.random.randint(0, n - 200)
        click_len = 80
        click = np.random.randn(click_len) * np.linspace(1.0, 0.0, click_len)
        click = highpass(click, 2000)
        click = lowpass(click, 6000)
        out[pos:pos+click_len] += click * 0.8
    return out


def make_money_counting():
    n = int(DUR * SR)
    out = np.zeros(n)
    rate = int(SR / 12)  # 12 bills per second
    for s in range(0, n, rate):
        crinkle_len = int(SR * 0.06)
        if s + crinkle_len >= n:
            break
        crinkle = np.random.randn(crinkle_len) * np.linspace(1.0, 0.0, crinkle_len)
        crinkle = highpass(crinkle, 3000)
        out[s:s+crinkle_len] += crinkle * 0.8
    return out


def make_crowd_chatter():
    n = int(DUR * SR)
    base = np.random.randn(n) * 0.35
    base = bandpass(base, 200, 2000)
    t = np.arange(n) / SR
    return base * (0.7 + 0.2 * np.sin(2 * np.pi * 0.3 * t))


def bandpass(x, low, high):
    return lowpass(highpass(x, low), high)


def make_sci_fi_data():
    n = int(DUR * SR)
    out = np.random.randn(n) * 0.05
    # Random short beeps at varied frequencies
    for _ in range(int(DUR * 4)):
        pos = np.random.randint(0, n - 1000)
        freq = np.random.choice([800, 1200, 1800, 2400, 3200])
        beep_len = int(SR * np.random.uniform(0.04, 0.12))
        beep = np.sin(2 * np.pi * freq * np.arange(beep_len) / SR)
        beep = beep * np.linspace(1.0, 0.0, beep_len) * 0.4
        out[pos:pos+beep_len] += beep
    return out


def make_paper_rustle():
    n = int(DUR * SR)
    out = np.random.randn(n) * 0.1
    out = highpass(out, 2000)
    out = lowpass(out, 8000)
    # Pages flipping
    for _ in range(int(DUR * 1.5)):
        pos = np.random.randint(0, n - 3000)
        flip_len = 2500
        flip = np.random.randn(flip_len) * np.linspace(0, 1, flip_len) * np.linspace(1, 0, flip_len)
        flip = highpass(flip, 3000)
        out[pos:pos+flip_len] += flip * 0.6
    return out


def make_fire_crackle():
    n = int(DUR * SR)
    base = np.random.randn(n) * 0.3
    base = lowpass(base, 1500)
    # Crackles
    out = base
    for _ in range(int(DUR * 8)):
        pos = np.random.randint(0, n - 200)
        crack_len = int(SR * np.random.uniform(0.01, 0.04))
        crack = np.random.randn(crack_len) * np.linspace(1.0, 0.0, crack_len)
        crack = highpass(crack, 3000)
        out[pos:pos+crack_len] += crack * 1.0
    return out


def make_water_drops():
    n = int(DUR * SR)
    out = np.zeros(n)
    for _ in range(int(DUR * 3)):
        pos = np.random.randint(0, n - 2000)
        freq = np.random.uniform(800, 1400)
        drop_len = 1200
        drop = np.sin(2 * np.pi * freq * np.arange(drop_len) / SR)
        drop = drop * np.exp(-np.arange(drop_len) / (SR * 0.08))
        out[pos:pos+drop_len] += drop * 0.5
    # Faint water bed
    bed = np.random.randn(n) * 0.05
    bed = lowpass(bed, 600)
    return out + bed


# ── Build all 18 ambients ───────────────────────────────────────────────────

LIBRARY = [
    ("rain",                make_rain,                0),
    ("wind",                make_wind,                0),
    ("ocean",               make_ocean,               0),
    ("footsteps_pavement",  make_footsteps_pavement,  -3),
    ("footsteps_indoor",    make_footsteps_indoor,    -4),
    ("hospital_beeps",      make_hospital_beeps,      -2),
    ("heartbeat",           make_heartbeat,           -2),
    ("factory_industrial",  make_factory_industrial,  0),
    ("lab_glassware",       make_lab_glassware,       -3),
    ("courtroom_murmur",    make_courtroom_murmur,    -2),
    ("city_traffic",        make_city_traffic,        -1),
    ("office_keyboard",     make_office_keyboard,     -3),
    ("money_counting",      make_money_counting,      -2),
    ("crowd_chatter",       make_crowd_chatter,       -2),
    ("sci_fi_data",         make_sci_fi_data,         -1),
    ("paper_rustle",        make_paper_rustle,        -2),
    ("fire_crackle",        make_fire_crackle,        -1),
    ("water_drops",         make_water_drops,         -1),
]


def main():
    print(f"Building {len(LIBRARY)} ambient loops in {OUT}/...")
    for name, fn, gain in LIBRARY:
        save(name, fn(), gain_db=gain)
    print(f"\n✅ Done — {len(LIBRARY)} ambients ready.")


if __name__ == "__main__":
    main()
