import subprocess
import sys


def run(cmd):
    print(">", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    run([sys.executable, "build_insight_hub_v1.py"])
    run([sys.executable, "build_longreads_v1.py"])
    run([sys.executable, "build_ai_digest_clone.py"])
    print("daily pipeline done")


if __name__ == "__main__":
    main()
