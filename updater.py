# -*- coding: utf-8 -*-
"""자동 업데이트: GitHub 저장소의 최신 코드를 받아 이 폴더에 덮어쓴다.
config.json(키·설정), data 폴더(기록), .venv(설치된 프로그램), run.bat/install.bat 은 건드리지 않는다."""
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO = "xnononox87-star/rank-checker"
BRANCH = "main"
SKIP_FILES = {"config.json", "run.bat", "install.bat"}
SKIP_DIRS = {"data", ".venv", ".git", "__pycache__"}


def _repo():
    try:
        with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
            return json.load(f).get("update_repo") or DEFAULT_REPO
    except Exception:
        return DEFAULT_REPO


def local_version():
    try:
        with open(os.path.join(BASE, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0"


def remote_version():
    url = f"https://raw.githubusercontent.com/{_repo()}/{BRANCH}/VERSION"
    r = requests.get(url, timeout=10, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    return r.text.strip()


def _vt(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


def update(force=False, log=print):
    """새 버전이 있으면 받아서 적용. 반환: (업데이트했는지, 메시지)"""
    try:
        lv, rv = local_version(), remote_version()
    except Exception as e:
        return False, f"업데이트 확인 실패(인터넷 확인): {e}"
    if not force and _vt(rv) <= _vt(lv):
        return False, f"최신 버전이에요 (v{lv})"
    log(f"새 버전 v{rv} 받는 중... (현재 v{lv})")
    url = f"https://github.com/{_repo()}/archive/refs/heads/{BRANCH}.zip"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    old_req = _read(os.path.join(BASE, "requirements.txt"))
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        root = z.namelist()[0].split("/")[0] + "/"
        for name in z.namelist():
            rel = name[len(root):]
            if not rel or name.endswith("/"):
                continue
            parts = rel.split("/")
            if parts[0] in SKIP_DIRS or rel in SKIP_FILES:
                continue
            dest = os.path.join(BASE, *parts)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(name) as src, open(dest + ".new", "wb") as out:
                shutil.copyfileobj(src, out)
            os.replace(dest + ".new", dest)
    if _read(os.path.join(BASE, "requirements.txt")) != old_req:
        log("필요한 구성요소 설치 중...")
        subprocess.call([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(BASE, "requirements.txt")])
    return True, f"v{rv}로 업데이트했어요"


def _read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


if __name__ == "__main__":
    ok, msg = update()
    print(msg)
