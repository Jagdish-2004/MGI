import http.server
import os
import socketserver
import sys
import urllib.parse
from pathlib import Path

VIEWER_DIR = Path(r"D:\Mgai\viewer").resolve()
OUTPUT_DIR = Path(r"D:\Mgai\outputs").resolve()
TEST_OUTPUT_DIR = Path(r"D:\Mgai\test_output").resolve()
DEFAULT_PORT = 8080

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class ViewerHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

    def end_headers(self):
        # Enable CORS and Cross-Origin Isolation for WebGL / WebWorker performance
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        clean_path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # Dedicated API endpoint to safely stream requested or active PLY
        if clean_path == "/api/ply":
            req_file = None
            if "id" in params and params["id"]:
                req_file = params["id"][0]
            elif "file" in params and params["file"]:
                req_file = params["file"][0]

            ply_path = self.resolve_ply_path(req_file)
            if ply_path and ply_path.exists():
                self.serve_ply_file(ply_path)
            else:
                self.send_error(404, "PLY file not found")
            return

        # Dedicated endpoint to download PLY with attachment header
        if clean_path == "/api/download":
            req_file = None
            if "id" in params and params["id"]:
                req_file = params["id"][0]
            elif "file" in params and params["file"]:
                req_file = params["file"][0]

            ply_path = self.resolve_ply_path(req_file)
            if ply_path and ply_path.exists():
                self.serve_ply_file(ply_path, as_attachment=True)
            else:
                self.send_error(404, "PLY file not found")
            return

        # Direct safe serving by filename under /data/<filename.ply>
        if clean_path.startswith("/data/"):
            filename = clean_path[6:]
            ply_path = self.resolve_ply_path(filename)
            if ply_path and ply_path.exists():
                self.serve_ply_file(ply_path)
            else:
                self.send_error(404, f"PLY file {filename} not found")
            return


        return super().do_GET()

    def resolve_ply_path(self, requested_name: str | None) -> Path | None:
        """Safely resolve a requested PLY name preventing directory traversal."""
        if requested_name:
            # Strip query params or path segments if present
            base_name = os.path.basename(requested_name.split("?")[0])
            if not base_name.lower().endswith(".ply"):
                base_name += ".ply"

            # Check outputs directory first
            out_candidate = OUTPUT_DIR / base_name
            if out_candidate.is_file():
                return out_candidate

            # Check test_output directory
            test_candidate = TEST_OUTPUT_DIR / base_name
            if test_candidate.is_file():
                return test_candidate

            return None

        # If no specific file requested, find the newest file in outputs
        ply_files = sorted(OUTPUT_DIR.glob("*.ply"), key=lambda p: p.stat().st_mtime, reverse=True)
        if ply_files:
            return ply_files[0]

        # Fallback to test_output teaser.ply if outputs is empty
        teaser = TEST_OUTPUT_DIR / "teaser.ply"
        if teaser.is_file():
            return teaser

        return None

    def serve_ply_file(self, ply_path: Path, as_attachment: bool = False):
        file_size = ply_path.stat().st_size
        range_header = self.headers.get("Range")

        try:
            if range_header and range_header.startswith("bytes="):
                # Handle HTTP range request
                ranges = range_header[6:].split("-")
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if ranges[1] else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", "application/octet-stream")
                if as_attachment:
                    self.send_header("Content-Disposition", f'attachment; filename="{ply_path.name}"')
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(ply_path, "rb") as f:
                    f.seek(start)
                    self.wfile.write(f.read(length))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                if as_attachment:
                    self.send_header("Content-Disposition", f'attachment; filename="{ply_path.name}"')
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()


                with open(ply_path, "rb") as f:
                    chunk_size = 1024 * 1024  # 1MB
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass


def run_server(port=DEFAULT_PORT):
    server_address = ("127.0.0.1", port)
    for p in range(port, port + 20):
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", p), ViewerHTTPHandler)
            httpd.daemon_threads = True
            print(f"[PhotoDepth 3D Server] Serving at http://127.0.0.1:{p}/")
            print(f"[PhotoDepth 3D Server] PLY endpoint available at http://127.0.0.1:{p}/api/ply")
            sys.stdout.flush()
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer shutting down.")
            finally:
                httpd.server_close()
            return
        except OSError:
            continue

    print(f"Error: Could not bind to any port in range {port}-{port+20}")
    sys.exit(1)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_server(port)
