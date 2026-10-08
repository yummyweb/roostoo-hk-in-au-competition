"""The hourly regime preset (config/regime_hourly_candidate.json) run through the repository's own decision function."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapter import RepoLegs, REPO
from roostoo.strategy import Config

CONFIG = Config(**json.load(open(os.path.join(REPO, 'config/regime_hourly_candidate.json'))))
REGIME = json.load(open(os.path.join(REPO, 'config/coin_regime.json'))) if os.path.exists(os.path.join(REPO, 'config/coin_regime.json')) else {'return_bars': 24, 'vol_bars': 24}


def make(panel):
    return RepoLegs(panel, CONFIG, REGIME['return_bars'], REGIME['vol_bars'])
