#!/usr/bin/env python3
from universe_study import main
from roostoo.strategy import Config

if __name__=='__main__':
    main([
        Config(strategy='allocation',fast=24,slow=168,momentum=72,max_position=.2,top_n=6,target_volatility=.35),
        Config(strategy='allocation',fast=24,slow=168,momentum=72,max_position=.2,top_n=6,target_volatility=.55),
        Config(strategy='allocation',fast=48,slow=336,momentum=168,max_position=.2,top_n=6,target_volatility=.35),
        Config(strategy='allocation',fast=48,slow=336,momentum=168,max_position=.2,top_n=6,target_volatility=.55),
    ],'runs/allocation-study')
