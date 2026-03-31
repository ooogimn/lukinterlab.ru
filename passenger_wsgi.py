import sys, os
INTERP = os.path.expanduser("~/domains/lukinterlab.ru/.venv/python313/bin/python3.13")

if sys.executable != INTERP: os.execl(INTERP, INTERP, *sys.argv)

from ALUKINTERLAB.wsgi import application