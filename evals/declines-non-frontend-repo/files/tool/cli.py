#!/usr/bin/env python3
"""Rotate log files older than N days."""
import argparse, os, time

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    cutoff = time.time() - a.days * 86400
    for f in os.listdir(a.path):
        p = os.path.join(a.path, f)
        if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
            os.rename(p, p + ".old")

if __name__ == "__main__":
    main()
