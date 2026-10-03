#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
LSTM_PYTHON="${LSTM_PYTHON:-python3.12}"
"$LSTM_PYTHON" -m venv .venv-lstm
.venv-lstm/bin/python -m pip install -r requirements-lstm.txt
