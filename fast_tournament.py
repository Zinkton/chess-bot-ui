import argparse
import subprocess
import psutil
import os

E_CORES = list(range(16, 32))

def engine_name(path):
    return os.path.splitext(os.path.basename(path))[0]

def main():
    parser = argparse.ArgumentParser(description="SPRT test with fastchess on the E-cores.")
    parser.add_argument("engine1", help="New version")
    parser.add_argument("engine2", help="Baseline")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=15)
    args = parser.parse_args()
    
    name1 = engine_name(args.engine1)
    name2 = engine_name(args.engine2)
    if name1 == name2:
        name1 += "_1"
        name2 += "_2"

    psutil.Process().cpu_affinity(E_CORES)

    cmd = [
        "fastchess.exe",
        "-engine", f"cmd={args.engine1}", f"name={name1}",
        "-engine", f"cmd={args.engine2}", f"name={name2}",
        "-each", "proto=uci", "tc=10+0.05", f"option.Threads={args.threads}",
        "-concurrency", str(args.concurrency),
        "-games", "2", "-repeat", "-rounds", "50000",
        "-recover",
        "-resign", "movecount=3", "score=400",
        "-draw", "movenumber=40", "movecount=8", "score=10",
        "-openings", "file=chess.epd", "format=epd", "order=random",
        "-sprt", "elo0=0", "elo1=5", "alpha=0.05", "beta=0.05", "model=normalized",
        "-output", "format=cutechess",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        line = line.strip()
        if line.startswith(("Score of", "Elo difference", "SPRT", "H0", "H1")):
            print(line, flush=True)
    proc.wait()

if __name__ == "__main__":
    main()