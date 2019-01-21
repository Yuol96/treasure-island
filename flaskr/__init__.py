import os

from flask import Flask
from flaskr.config import cfg

from flask_socketio import SocketIO
from threading import Lock

async_mode = None
socketio = SocketIO()
thread = None
thread_lock = Lock()
all_rooms = {}
all_users = {}

def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # a default secret that should be overridden by instance config
        SECRET_KEY='dev',
        # store the database in the instance folder
        DATABASE="mongodb://127.0.0.1:27017/" + cfg.db_name,
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.update(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    # register the database commands
    from flaskr import db
    db.init_app(app)

    socketio.init_app(app=app, async_mode=async_mode)

    # apply the blueprints to the app
    from flaskr import auth, island
    app.register_blueprint(auth.bp)
    app.register_blueprint(island.bp)

    # make url_for('index') == url_for('island.index')
    # in another app, you might define a separate main index here with
    # app.route, while giving the island blueprint a url_prefix, but for
    # the tutorial the island will be the main index
    app.add_url_rule('/', endpoint='index')

    return app
