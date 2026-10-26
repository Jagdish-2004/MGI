import os
import sys
import time
import urllib.request
from pathlib import Path

URL = "https://ml-site.cdn-apple.com/models/sharp/sharp_2572gikvuh.pt"
EXPECTED_SIZE = 2809738232

PROJECT_ROOT = Path(__file__).parent.resolve()
target_dir = PROJECT_ROOT / ".cache" / "torch" / "hub" / "checkpoints"
target_dir.mkdir(parents=True, exist_ok=True)

final_file = target_dir / "sharp_2572gikvuh.pt"
partial_file = target_dir / "sharp_2572gikvuh.pt.partial"

if final_file.exists():
    actual_size = final_file.stat().st_size
    print(f"Final checkpoint file already exists: {final_file} ({actual_size} bytes)")
    if actual_size == EXPECTED_SIZE:
        print("Checkpoint size matches exactly.")
        sys.exit(0)
    else:
        print(f"Warning: size mismatch (expected {EXPECTED_SIZE}, got {actual_size}).")

existing_bytes = 0
if partial_file.exists():
    existing_bytes = partial_file.stat().st_size
    print(f"Found existing partial download: {existing_bytes} bytes (~{existing_bytes / (1024**2):.2f} MB)")
    if existing_bytes > EXPECTED_SIZE:
        print("Partial file is larger than expected size. Truncating.")
        partial_file.unlink()
        existing_bytes = 0

headers = {"User-Agent": "PhotoDepth3D-Downloader/1.0"}
if existing_bytes > 0:
    headers["Range"] = f"bytes={existing_bytes}-"
    print(f"Resuming download from byte {existing_bytes}...")
else:
    print(f"Starting fresh download of {EXPECTED_SIZE} bytes (~{EXPECTED_SIZE / (1024**3):.2f} GB)...")

req = urllib.request.Request(URL, headers=headers)

start_time = time.time()
last_report_time = start_time
last_report_bytes = existing_bytes

try:
    with urllib.request.urlopen(req) as resp:
        status = getattr(resp, "status", 200)
        print(f"HTTP response status: {status}")

        mode = "ab" if existing_bytes > 0 else "wb"
        with open(partial_file, mode) as f:
            chunk_size = 1024 * 1024  # 1 MB
            downloaded = existing_bytes

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                if now - last_report_time >= 5.0 or downloaded == EXPECTED_SIZE:
                    elapsed = now - start_time
                    speed = (downloaded - last_report_bytes) / (now - last_report_time) / (1024 * 1024) if (now - last_report_time) > 0 else 0
                    pct = (downloaded / EXPECTED_SIZE) * 100
                    print(f"Progress: {downloaded} / {EXPECTED_SIZE} bytes ({pct:.1f}%) - Speed: {speed:.2f} MB/s")
                    last_report_time = now
                    last_report_bytes = downloaded

    final_partial_size = partial_file.stat().st_size
    print(f"Download finished. Verifying size: {final_partial_size} bytes (expected: {EXPECTED_SIZE} bytes)")
    if final_partial_size == EXPECTED_SIZE:
        if final_file.exists():
            final_file.unlink()
        partial_file.rename(final_file)
        print(f"Successfully verified and saved checkpoint to: {final_file}")
    else:
        print(f"Error: Size verification failed! Expected {EXPECTED_SIZE}, got {final_partial_size}")
        sys.exit(1)

except Exception as e:
    print(f"Download error: {e}")
    sys.exit(1)
