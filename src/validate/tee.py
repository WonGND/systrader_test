# -*- coding: utf-8 -*-
"""Write a runner's console output to a UTF-8 file without a shell pipe.

`... | Tee-Object -FilePath out.txt` mangles Korean: Python reconfigures its
stdout to UTF-8, PowerShell decodes the pipe as the console codepage (CP949 on
a Korean Windows), and both the terminal and the file end up as mojibake.

Writing the file from inside Python removes the pipe from the path entirely,
so the saved report is always correct no matter what the console is set to.
The console itself still needs a UTF-8 codepage to *display* Korean; the
runners print a one-line hint when they detect otherwise (CLAUDE.md §9 treats
broken Korean as a bug, not a cosmetic issue).
"""

from __future__ import annotations

import sys
from pathlib import Path


class _Tee:
    def __init__(self, stream, handle):
        self._stream, self._handle = stream, handle

    def write(self, text):
        self._handle.write(text)
        return self._stream.write(text)

    def flush(self):
        self._handle.flush()
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def start(out_path: str | None):
    """Mirror stdout into `out_path` (UTF-8). Returns a close() callable."""
    console_ok = (sys.stdout.encoding or "").lower().replace("-", "") in ("utf8", "cp65001")
    if not console_ok:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    original, handle = sys.stdout, None
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        handle = open(p, "w", encoding="utf-8")
        sys.stdout = _Tee(original, handle)

    if not console_ok:
        print("[안내] 콘솔 코드페이지가 UTF-8이 아닙니다. 화면의 한글이 깨져 보이면"
              " 아래를 실행한 뒤 다시 실행하세요 (숫자는 그대로 읽을 수 있습니다):")
        print("       [Console]::OutputEncoding = [Text.Encoding]::UTF8")
        if out_path:
            print(f"       저장 파일 {out_path} 은 UTF-8로 정상 기록됩니다"
                  " (파이프 없이 직접 씀).")

    def close():
        if handle is not None:
            sys.stdout = original
            handle.close()
    return close
