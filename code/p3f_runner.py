#!/usr/bin/env python3
"""Topic 43 / P3F: detached schedule of the jobs that wait for the OpenAlex daily budget (Amendment 8 (D), (H)).

today  sources other than OpenAlex for decoy, posctl, acad1921, nonacad1921 (once; exits when done)
daily  every UTC day from the next 00:10Z until 2026-11-12T23:59Z: waits for that day's cascade pass to finish, runs one (H)
       pass, then GT-3 with OpenAlex for decoy, posctl, acad1921, nonacad1921, acad2426 (acad2426 only once set (ii) is
       fixed). Budget order within a day: cascade, (H), GT-3. Exits when nothing is left to ask.
Usage: python code/p3f_runner.py today|daily
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
OUT = ROOT / "P3F"
LOG = OUT / "runner.log"
END = dt.datetime(2026, 11, 12, 23, 59, tzinfo=dt.timezone.utc)
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
TICK = 60  # s; wall-clock check, so time spent in (Modern) Standby is not added to the wait

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def awake(on):
    """Keep the machine out of idle sleep while a pass runs (P3F2 Viec 2, LQD 2026-11-11); no effect off Windows."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def now():
    return dt.datetime.now(dt.timezone.utc)


def log(msg):
    line = f"{now():%Y-%m-%dT%H:%M:%SZ} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def call(script, *args):
    log(f"run {script} {' '.join(args)}")
    r = subprocess.run([sys.executable, str(CODE / script), *args], cwd=ROOT, env=ENV, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    log(f"  exit {r.returncode}" + (f"; stderr tail: {r.stderr[-300:]}" if r.returncode else ""))
    return r.returncode


def deep(setname, *flags):
    return call("p3f_deep_search.py", "--seed", "48", "--resume", "--set", setname, *flags)


def cascade_state():
    p = ROOT / "P3E" / "cascade_passes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"passes": []}


def cascade_complete():
    return cascade_state().get("unanswered_after_last_pass", {}).get("n_scope_unanswered") == 0


def cascade_pass_today(day):
    return any(p.get("end", "").startswith(day) and p.get("start", "") >= f"{day}T00:10" for p in cascade_state()["passes"])


def today():
    for s in ("decoy", "posctl", "acad1921", "nonacad1921"):
        deep(s, "--no-openalex")
    log("today: done")


def daily():
    while True:
        n = now()
        start = n.replace(hour=0, minute=10, second=0, microsecond=0)
        start = start if n.hour == 0 and n.minute < 10 else start + dt.timedelta(days=1)
        if start > END:
            log("daily: past the end date; exit")
            return
        wait = (start - now()).total_seconds()
        log(f"daily: waiting {wait / 60:.0f} min until {start:%Y-%m-%dT%H:%M}Z")
        while now() < start:  # short ticks on the wall clock: after a sleep of the machine the pass starts at once
            time.sleep(TICK)
        awake(True)
        try:
            if day_pass(f"{start:%Y-%m-%d}"):
                return
        finally:
            awake(False)


def day_pass(day):
    """One daily pass; True when nothing is left to ask."""
    while not (cascade_complete() or cascade_pass_today(day) or now() > END):
        time.sleep(300)  # budget order: the cascade of the day goes first
    log(f"daily: cascade of {day} done or complete ({cascade_complete()})")
    if cascade_complete() or now() > END:
        call("p3f_cascade_h.py")
    done_h = (OUT / "cascade_h_done.json").exists()
    for s in ("decoy", "posctl", "acad1921", "nonacad1921"):
        deep(s)
    if cascade_complete() or now() > END:
        deep("acad2426")
    call("p3f_deep_search.py", "--evaluate")
    if done_h and cascade_complete() and left_to_ask() == 0:
        log("daily: nothing left to ask; exit")
        return True
    return False


def left_to_ask():
    import csv
    f = ROOT / "results" / "p3f_deep_search.csv"
    if not f.exists():
        return 1
    with f.open(encoding="utf-8") as h:
        return sum(1 for r in csv.DictReader(h) if r["state"] == "unanswered" and "openalex" in r["missing_sources"])


if __name__ == "__main__":
    {"today": today, "daily": daily}[sys.argv[1]]()
