import click
from flask import current_app, g
from flask.cli import with_appcontext

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
from bson.errors import InvalidId
from sys import maxsize
from datetime import datetime

from pprint import pprint

#-------------------------
import json
from flaskr.config import cfg
import os
import subprocess
from pathlib import Path

from flaskr.utils import InteractiveIf

def get_db():
    if 'db' not in g:
        g.db = MongoClient(current_app.config['DATABASE'])[cfg.db_name]
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.client.close()

@InteractiveIf(msg='Drop current database or not?', divider=False)
def init_db():
    db = get_db()
    db.client.drop_database(cfg.db_name)
    print("current database dropped!")

@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)



def get_history():
    """
    history: a python list, each item is a tuple of (datetime date, score, list of user_ids of other players)
    """
    return g.user['history']
        