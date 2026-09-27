#!/usr/bin/env python3
"""serve_video.py - preview a rendered video on a phone over the local network.

Detail density, text size and motion speed have to be judged at delivery size,
so a film meant for phones should be watched on a phone. This serves ONLY the
files you list (nothing else in the directory is reachable), supports HTTP Range
requests and HEAD (iOS Safari will not play a video without them), redirects /
to the first file, and prints the LAN URLs to open.

  python serve_video.py out.mp4 [alt.mp4 ...] [--port 8765] [--host 0.0.0.0]

PRIVACY: binding to 0.0.0.0 exposes the listed files to every device on the
local network for as long as the server runs. Stop it (Ctrl-C) as soon as the
review is done. Use --host 127.0.0.1 to keep it on this machine.
"""
import argparse
import mimetypes
import os
import re
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit

CHUNK = 1 << 16


def parse_range(header, size):
    """Return (start, end) inclusive for a single-range 'bytes=' header,
    None if there is no usable Range header, or 'unsatisfiable'."""
    if not header:
        return None
    m = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", header)
    if not m or (not m.group(1) and not m.group(2)):
        return None                                   # malformed or multi-range: send whole file
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
        if start >= size or end < start:
            return "unsatisfiable"
        return start, min(end, size - 1)
    n = int(m.group(2))                               # suffix range: last n bytes
    if n == 0 or size == 0:
        return "unsatisfiable"
    return max(size - n, 0), size - 1


def make_handler(files):
    """files: {url_path: absolute_file_path}, in listing order."""
    first = next(iter(files))

    class Handler(BaseHTTPRequestHandler):
        server_version = "serve_video"

        def log_message(self, fmt, *args):
            sys.stderr.write(f"  {self.address_string()} {fmt % args}\n")

        def _serve(self, head):
            path = unquote(urlsplit(self.path).path)
            if path == "/":
                self.send_response(302)
                self.send_header("Location", quote(first))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            fp = files.get(path)
            if fp is None:
                self.send_error(404)
                return
            size = os.path.getsize(fp)
            ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
            rng = parse_range(self.headers.get("Range"), size)
            if rng == "unsatisfiable":
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if rng is None:
                start, end = 0, size - 1
                self.send_response(200)
            else:
                start, end = rng
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            length = max(end - start + 1, 0)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if head:
                return
            with open(fp, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    left -= len(chunk)

        def do_GET(self):
            self._serve(head=False)

        def do_HEAD(self):
            self._serve(head=True)

    return Handler


def lan_addresses():
    """Best-effort list of this machine's non-loopback IPv4 addresses."""
    addrs = set()
    try:                                  # no packet is sent: connect() on UDP only picks a route
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))       # TEST-NET-1, never routed
        addrs.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addrs.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in addrs if not a.startswith("127."))


def build_file_map(paths):
    files = {}
    for p in paths:
        ap = os.path.abspath(p)
        if not os.path.isfile(ap):
            raise SystemExit(f"FAIL  not a file: {p}")
        url = "/" + os.path.basename(ap)
        if url in files:
            raise SystemExit(f"FAIL  two listed files share the name {url[1:]!r}; rename one")
        files[url] = ap
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="video file(s) to serve; nothing else is reachable")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0",
                    help="bind address (default 0.0.0.0 = whole local network)")
    a = ap.parse_args()

    files = build_file_map(a.files)
    httpd = ThreadingHTTPServer((a.host, a.port), make_handler(files))
    port = httpd.server_address[1]

    hosts = lan_addresses() if a.host == "0.0.0.0" else [a.host]
    print(f"serving {len(files)} file(s) on {a.host}:{port}")
    for url in files:
        for h in hosts or ["<this-machine-ip>"]:
            print(f"  http://{h}:{port}{quote(url)}")
    if a.host == "0.0.0.0":
        print("\n  Bound to all interfaces: every device on this network can fetch these files.")
        print("  Stop the server (Ctrl-C) as soon as the review is done.")
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("\n  stopped")


if __name__ == "__main__":
    main()
