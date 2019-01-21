from easydict import EasyDict as edict
from os import path as osp
from pathlib import Path
import os

cfg = edict()

cfg.PATH = edict()
cfg.PATH.root_dir = Path(os.environ['ROOT_DIR'])

cfg.db_name = 'treasureIsland'
