"""
Run SPRT tests from a queue file, one after another.

queue.txt: one test per line, with the same arguments you'd give sprt.py.
Blank lines and lines starting with # are ignored. Example:

    engines/dev_lmr.exe engines/base.exe
    engines/dev_cleanup.exe engines/base.exe --nonreg
    "engines/my dev.exe" engines/base.exe --elo0 0 --elo1 3

The queue file is re-read before each test, so you can add, remove or
reorder lines while the runner is going. Finished tests are moved to
done.txt, and the full output of each test goes to logs/.

Usage:
    python sprt_queue.py               # run until the queue is empty
    python sprt_queue.py --watch       # keep waiting for new lines
"""
import argparse
import datetime
import os
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SPRT_SCRIPT = os.path.join(HERE, "sprt.py")

SUMMARY_PREFIXES = ("Score of", "Elo difference", "SPRT", "H0", "H1")


def split_args(line):
    # posix=False keeps Windows backslashes intact; strip quotes ourselves.
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] == '"' else t
            for t in shlex.split(line, posix=False)]


def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def write_lines(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    os.replace(tmp, path)


def pop_next(queue_path):
    """Remove and return the first real entry, keeping comments in place."""
    lines = read_lines(queue_path)
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s and not s.startswith("#"):
            write_lines(queue_path, lines[:i] + lines[i + 1:])
            return s
    return None


def push_front(queue_path, entry):
    write_lines(queue_path, [entry] + read_lines(queue_path))


def append_line(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def run_test(entry, log_dir):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    engines = [os.path.splitext(os.path.basename(a))[0]
               for a in split_args(entry) if not a.startswith("-")][:2]
    log_path = os.path.join(log_dir, f"{stamp}_{'_vs_'.join(engines) or 'test'}.log")

    cmd = [sys.executable, "-u", SPRT_SCRIPT] + split_args(entry)
    print(f"\n=== [{stamp}] {entry}", flush=True)
    print(f"    log: {log_path}", flush=True)

    summary = {}
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"# {entry}\n")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, cwd=HERE)
        try:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                s = line.strip()
                print("    " + s, flush=True)
                for p in SUMMARY_PREFIXES:
                    if s.startswith(p):
                        summary[p] = s  # keep the latest of each kind
        except KeyboardInterrupt:
            proc.kill()
            proc.wait()
            raise
        proc.wait()

    result = " | ".join(summary[p] for p in SUMMARY_PREFIXES if p in summary)
    return proc.returncode, result


def main():
    ap = argparse.ArgumentParser(description="Run queued SPRT tests sequentially.")
    ap.add_argument("--queue", default=os.path.join(HERE, "queue.txt"))
    ap.add_argument("--done", default=os.path.join(HERE, "done.txt"))
    ap.add_argument("--logs", default=os.path.join(HERE, "logs"))
    ap.add_argument("--watch", action="store_true",
                    help="When the queue is empty, wait for new entries instead of exiting")
    ap.add_argument("--poll", type=int, default=30, help="Seconds between checks in --watch mode")
    args = ap.parse_args()

    os.makedirs(args.logs, exist_ok=True)
    if not os.path.exists(args.queue):
        write_lines(args.queue, ["# one test per line: <new.exe> <base.exe> [sprt.py options]"])

    while True:
        entry = pop_next(args.queue)
        if entry is None:
            if not args.watch:
                print("Queue empty, done.")
                return
            time.sleep(args.poll)
            continue

        started = datetime.datetime.now()
        try:
            code, result = run_test(entry, args.logs)
        except KeyboardInterrupt:
            push_front(args.queue, entry)
            print("\nInterrupted; test put back at the top of the queue.")
            return

        mins = (datetime.datetime.now() - started).total_seconds() / 60
        status = "OK" if code == 0 else f"EXIT {code}"
        append_line(args.done,
                    f"{started:%Y-%m-%d %H:%M}  [{status}, {mins:.0f} min]  {entry}\n    {result}")


if __name__ == "__main__":
    main()