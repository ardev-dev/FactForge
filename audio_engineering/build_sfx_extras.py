#!/usr/bin/env python3
"""
build_sfx_extras.py — 20 synthesized SFX (transitions, impacts, stings, alerts).

100% generated via numpy. We own full rights. Zero licensing risk.
Output: audio_engineering/assets/sfx_extras/[name].wav
"""
import math
from pathlib import Path
import numpy as np
import soundfile as sf

OUT = Path(__file__).parent / "assets/sfx_extras"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000


def save(name, data, peak=0.85):
    if peak > 0:
        m = np.max(np.abs(data))
        if m > 0:
            data = data / m * peak
    sf.write(OUT / f"{name}.wav", data, SR, subtype="PCM_16")
    print(f"  ✓ {name}.wav ({len(data)/SR:.2f}s)")


def lowpass(x, cutoff_hz):
    rc = 1 / (2 * math.pi * cutoff_hz); dt = 1 / SR
    a = dt / (rc + dt); y = np.empty_like(x); y[0] = x[0] * a
    for i in range(1, len(x)): y[i] = y[i-1] + a * (x[i] - y[i-1])
    return y


def highpass(x, cutoff_hz):
    rc = 1 / (2 * math.pi * cutoff_hz); dt = 1 / SR
    a = rc / (rc + dt); y = np.empty_like(x); y[0] = x[0]
    for i in range(1, len(x)): y[i] = a * (y[i-1] + x[i] - x[i-1])
    return y


# ── Transitions ─────────────────────────────────────────────────────────────

def whoosh_high():
    n = int(0.4 * SR); t = np.arange(n) / SR
    noise = np.random.randn(n) * 0.7
    noise = highpass(noise, 2000)
    env = np.exp(-((t - 0.2) ** 2) / 0.005)
    return noise * env


def whoosh_low():
    n = int(0.5 * SR); t = np.arange(n) / SR
    noise = np.random.randn(n) * 0.8
    noise = lowpass(noise, 800)
    env = np.exp(-((t - 0.25) ** 2) / 0.008)
    return noise * env


def transition_sweep():
    n = int(0.5 * SR); t = np.arange(n) / SR
    freq = np.linspace(200, 4000, n)
    sig = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    env = np.sin(np.pi * t / t[-1]) ** 2
    return sig * env * 0.6


def glitch_digital():
    n = int(0.3 * SR)
    out = np.zeros(n)
    for _ in range(40):
        pos = np.random.randint(0, n - 200)
        burst = np.random.randn(np.random.randint(50, 200)) * np.random.uniform(0.3, 0.9)
        out[pos:pos + len(burst)] += burst
    return highpass(out, 2000)


def power_down():
    n = int(0.6 * SR); t = np.arange(n) / SR
    freq = np.linspace(2000, 50, n)
    sig = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    env = np.exp(-t * 4)
    return sig * env * 0.7


def power_up():
    n = int(0.5 * SR); t = np.arange(n) / SR
    freq = np.linspace(80, 3000, n)
    sig = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    env = np.linspace(0, 1, n)
    return sig * env * 0.7


# ── Impacts ─────────────────────────────────────────────────────────────────

def impact_heavy():
    n = int(0.6 * SR); t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 4)
    sub = np.sin(2 * np.pi * 30 * t) * np.exp(-t * 3) * 0.7
    crack = np.random.randn(int(0.05 * SR)) * np.linspace(1, 0, int(0.05 * SR))
    out = boom + sub
    out[:len(crack)] += crack * 0.5
    return out


def impact_punch():
    n = int(0.3 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 100 * t) * np.exp(-t * 8)
    snap = highpass(np.random.randn(int(0.04 * SR)) * np.linspace(1, 0, int(0.04 * SR)), 1500)
    out = body
    out[:len(snap)] += snap * 0.6
    return out


def impact_thud():
    n = int(0.4 * SR); t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * 80 * t) * np.exp(-t * 6)
    return lowpass(thud, 400)


# ── Stings / Alerts ─────────────────────────────────────────────────────────

def sting_dramatic():
    n = int(0.8 * SR); t = np.arange(n) / SR
    # Rising minor chord
    chord = (np.sin(2*np.pi*220*t) + np.sin(2*np.pi*262*t) + np.sin(2*np.pi*330*t)) / 3
    env = np.linspace(0, 1, n) ** 2
    return chord * env * 0.6


def sting_dark():
    n = int(1.0 * SR); t = np.arange(n) / SR
    # Low ominous drone
    drone = (np.sin(2*np.pi*55*t) + np.sin(2*np.pi*82.4*t) * 0.5) * 0.7
    rumble = lowpass(np.random.randn(n) * 0.3, 200)
    env = np.sin(np.pi * t / t[-1])
    return (drone + rumble) * env


def sting_reveal():
    n = int(0.8 * SR); t = np.arange(n) / SR
    # Bright major chord opening up
    chord = (np.sin(2*np.pi*440*t) + np.sin(2*np.pi*554*t) + np.sin(2*np.pi*659*t)) / 3
    env = (1 - np.exp(-t * 5)) * np.exp(-t * 1.5)
    return chord * env * 0.7


def alert_warning():
    n = int(0.5 * SR); t = np.arange(n) / SR
    sig = np.sign(np.sin(2 * np.pi * 800 * t))  # square wave alarm
    env = np.sin(2 * np.pi * 4 * t) ** 2  # pulsing
    return sig * env * 0.5


def error_buzz():
    n = int(0.3 * SR); t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * 200 * t)
    sig += np.random.randn(n) * 0.3
    env = np.exp(-t * 8)
    return sig * env * 0.7


def bell_chime():
    n = int(1.5 * SR); t = np.arange(n) / SR
    # Bell harmonics
    bell = (np.sin(2*np.pi*880*t) + np.sin(2*np.pi*1318*t)*0.5 + np.sin(2*np.pi*1760*t)*0.25)
    env = np.exp(-t * 1.5)
    return bell * env * 0.5


def countdown_tick():
    n = int(0.1 * SR); t = np.arange(n) / SR
    tick = np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 80)
    return tick * 0.6


def text_pop():
    n = int(0.15 * SR); t = np.arange(n) / SR
    # Cartoon-y pop
    pop = np.sin(2 * np.pi * (300 + 1500 * t) * t) * np.exp(-t * 15)
    return pop * 0.6


# ── Tense / Suspense ────────────────────────────────────────────────────────

def breathing_tense():
    n = int(2.0 * SR); t = np.arange(n) / SR
    # 4 inhales / exhales over 2s
    breath_in = np.random.randn(int(0.5 * SR)) * 0.4
    breath_in = lowpass(breath_in, 800)
    breath_out = np.random.randn(int(0.5 * SR)) * 0.5
    breath_out = lowpass(breath_out, 600)
    out = np.concatenate([breath_in, breath_out, breath_in, breath_out])
    out = out[:n]
    env = np.linspace(0.3, 1, n)
    return out * env


def heartbeat_fast():
    n = int(2.0 * SR)
    out = np.zeros(n)
    bpm = 120  # tense
    period = int(SR * 60 / bpm)
    thump_len = int(SR * 0.1)
    thump = np.sin(2 * np.pi * 50 * np.arange(thump_len) / SR) * np.exp(-np.arange(thump_len) / (SR * 0.04))
    for s in range(0, n, period):
        if s + thump_len < n:
            out[s:s+thump_len] += thump * 1.0
    return out


def static_buildup():
    n = int(1.5 * SR); t = np.arange(n) / SR
    noise = np.random.randn(n) * 0.5
    noise = highpass(noise, 1000)
    env = (t / t[-1]) ** 2
    return noise * env


# ── Build all 20 ────────────────────────────────────────────────────────────

LIBRARY = [
    # Transitions (6)
    ("whoosh_high", whoosh_high),
    ("whoosh_low", whoosh_low),
    ("transition_sweep", transition_sweep),
    ("glitch_digital", glitch_digital),
    ("power_down", power_down),
    ("power_up", power_up),
    # Impacts (3)
    ("impact_heavy", impact_heavy),
    ("impact_punch", impact_punch),
    ("impact_thud", impact_thud),
    # Stings/Alerts (8)
    ("sting_dramatic", sting_dramatic),
    ("sting_dark", sting_dark),
    ("sting_reveal", sting_reveal),
    ("alert_warning", alert_warning),
    ("error_buzz", error_buzz),
    ("bell_chime", bell_chime),
    ("countdown_tick", countdown_tick),
    ("text_pop", text_pop),
    # Tense (3)
    ("breathing_tense", breathing_tense),
    ("heartbeat_fast", heartbeat_fast),
    ("static_buildup", static_buildup),
]


def main():
    print(f"Building {len(LIBRARY)} synthesized SFX → {OUT}/")
    for name, fn in LIBRARY:
        save(name, fn())
    print(f"\n✅ Done — {len(LIBRARY)} new SFX (100% owned, commercial-OK).")


if __name__ == "__main__":
    main()
