from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

from flaskr import socketio
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect

from flaskr import thread, thread_lock, all_rooms
import pdb
import datetime
import uuid
import functools

bp = Blueprint('island', __name__)
namespace = '/test'

@bp.route('/')
@login_required
def index():
    db = get_db()
    return render_template('island/search.html', async_mode=socketio.async_mode)

def not_in_room(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        for roomid, room in all_rooms.items():
            if g.user['user_id'] in room.members:
                session['roomid'] = room.roomid
                return redirect(url_for('island.room'))
        session['roomid'] = None
        return view(**kwargs)
    return wrapped_view

def in_room(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        for roomid, room in all_rooms.items():
            if g.user['user_id'] in room.members:
                session['roomid'] = room.roomid
                return view(**kwargs)
        session['roomid'] = None
        return redirect(url_for('island.wait'))
    return wrapped_view

@bp.route('/wait', methods=('GET', 'POST'))
@login_required
@not_in_room
def wait():
    db = get_db()
    # user = db.user_info.find_one({'user_id': user_id}, {'_id': 0, 'records': 1})
    records = {
        datetime.datetime.utcnow(): {'score': 95, 'players': ['hyc','yxy','zyj']}
    }
    if request.method == 'POST':
        error = None
        if request.form['room_button'] == 'createroom':
            roomid = str(uuid.uuid1())[:8]
            all_rooms[roomid] = Room(g.user, roomid)
            # socketio.emit('join', {"roomid": roomid});
            print("create room", roomid)
        elif request.form['room_button'] == 'joinroom':
            roomid = request.form['roomid']
            if roomid in all_rooms:
                room = all_rooms[roomid]
                room.add_user(g.user)
            else:
                error = "No such a room"
        else:
            raise ValueError

        # data = {'roomid': roomid}

        if not roomid:
            error = "Specify the roomid before you join the room!"
        
        if error is not None:
            flash(error)
        else:
            session['roomid'] = roomid
            return redirect(url_for('island.room'))
    return render_template('island/wait.html', async_mode=socketio.async_mode, records=records)

@bp.route('/room', methods=('GET', 'POST'))
@login_required
@in_room
def room():
    db = get_db()
    if request.method == 'POST':
        error = None
        if request.form['button'] == 'leaveroom':
            roomid = session['roomid']
            session['roomid'] = None
            all_rooms[roomid].leave(g.user['user_id'])
            return redirect(url_for('island.wait'))
        elif request.form['button'] == 'start':
            raise NotImplementedError
        else:
            raise ValueError

    return render_template('island/room.html', async_mode=socketio.async_mode)

@bp.route('/search')
@login_required
@in_room
def search():
    db = get_db()
    boxes = db.boxes_info.find({}, {'_id':0, 'pos':1})
    boxes_pos = [box['pos'] for box in boxes]
    return render_template('island/search.html', async_mode=socketio.async_mode, boxes_pos=boxes_pos)

@bp.route('/pkumap')
@login_required
def pkumap():
    db = get_db()
    return render_template('island/pkumap.html', async_mode=socketio.async_mode)

@bp.route('/match')
@login_required
def match():
    db = get_db()
    return render_template('island/match.html', async_mode=socketio.async_mode)

@bp.route('/lobby')
@login_required
def lobby():
    db = get_db()
    return render_template('island/lobby.html', async_mode=socketio.async_mode)

@bp.route('/grade_rank')
@login_required
def grade_rank():
    db = get_db()
    return render_template('island/grade_rank.html', async_mode=socketio.async_mode)

class Room:
    def __init__(self, user, roomid):
        self.owner_id = user['user_id']
        self.roomid = roomid
        self.members = {
            self.owner_id: {
                'name': user['username'],
                'score': 0,
                'location': None,
            },
        }
        self.boxes = self._get_boxes()
        self.status = 0 

    def _get_boxes(self):
        db = get_db()
        boxes = db.boxes_info.find({}, {'_id':0, 'pos':1})
        return {tuple(box['pos'][0],box['pos'][1]):{'openned': 1} for box in boxes}

    def empty(self):
        return len(self.members) == 0

    def add_user(self, user):
        self.members[user['user_id']] = {
            'name': user['username'],
            'score': 0,
            'location': None,
        }

    def leave(self, user_id):
        self.members.pop(user_id)
        if len(self.members) == 0:
            all_rooms.pop(self.roomid)
        else:    
            if self.owner_id not in self.members:
                self.owner_id = list(self.members.keys())[0]

    def sync(self):
        socketio.emit('room_sync', (self.members, self.boxes), room=self.roomid, namespace=namespace)
        print("Room {} syncronized! {}".format(self.roomid, self.members[self.owner_id]['name']))

    def get_boxes(self):
        raise NotImplementedError

    def start_game(self):
        raise NotImplementedError
        self.boxes = self.get_boxes()
        self.status = 1

    def event_handler(self, msg, user_id):
        raise NotImplementedError


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        # count += 1
        # socketio.emit('my_response',
        #               {'data': 'Server generated event', 'count': count},
        #               namespace=namespace)
        for room in all_rooms.values():
            room.sync()
        socketio.sleep(3)

class MyNamespace(Namespace):
    def on_my_event(self, message):
        print(datetime.datetime.utcnow(), session['user']['username'], 'connected!')
        # session['receive_count'] = session.get('receive_count', 0) + 1
        # emit('my_response',
        #      {'data': message['data'], 'count': session['receive_count']})

    def on_my_broadcast_event(self, message):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': message['data'], 'count': session['receive_count']},
             broadcast=True)

    def on_join(self, message):
        join_room(message['roomid'])
        print("{} joined {}".format(session['user']['username'], message['roomid']))
        # roomid = message['roomid']
        # if roomid in all_rooms:
        #     room = all_rooms[roomid]
        #     room.add_user(session['user'])
        # else:
        #     all_rooms[roomid] = Room(session['user'], roomid)
        # session['receive_count'] = session.get('receive_count', 0) + 1
        # emit('my_response',
        #      {'data': 'In rooms: ' + ', '.join(rooms()),
        #       'count': session['receive_count']})

    def on_leave(self, message):
        leave_room(message['roomid'])
        print("{} left {}".format(session['user']['username'], message['roomid']))

    # def on_close_room(self, message):
    #     roomid = message['room']
    #     if roomid in all_rooms:
    #         all_rooms[roomid].close()
    #     session['receive_count'] = session.get('receive_count', 0) + 1
    #     emit('my_response', {'data': 'Room ' + message['room'] + ' is closing.',
    #                          'count': session['receive_count']},
    #          room=message['room'])
    #     close_room(message['room'])

    def on_my_room_event(self, message):
        session['receive_count'] = session.get('receive_count', 0) + 1
        roomid = message['room']
        all_rooms[roomid].event_handler(message, session['user']['user_id'])
        emit('my_response',
             {'data': message['data'], 'count': session['receive_count']},
             room=message['room'])

    def on_disconnect_request(self):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': 'Disconnected!', 'count': session['receive_count']})
        disconnect()

    def on_my_ping(self):
        emit('my_pong')

    def on_connect(self):
        user_id = session.get('user_id')
        session['user'] = get_db().user_info.find_one({'user_id': user_id}, {'_id': 0})
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(background_thread)
        # emit('my_response', {'data': 'Connected', 'count': 0})

    def on_disconnect(self):
        print('Client disconnected', request.sid)


socketio.on_namespace(MyNamespace(namespace))


# def get_post(id, check_author=True):
#     """Get a post and its author by id.

#     Checks that the id exists and optionally that the current user is
#     the author.

#     :param id: id of post to get
#     :param check_author: require the current user to be the author
#     :return: the post with author information
#     :raise 404: if a post with the given id doesn't exist
#     :raise 403: if the current user isn't the author
#     """
#     post = get_db().execute(
#         'SELECT p.id, title, body, created, author_id, username'
#         ' FROM post p JOIN user u ON p.author_id = u.id'
#         ' WHERE p.id = ?',
#         (id,)
#     ).fetchone()

#     if post is None:
#         abort(404, "Post id {0} doesn't exist.".format(id))

#     if check_author and post['author_id'] != g.user['id']:
#         abort(403)

#     return post


# @bp.route('/create', methods=('GET', 'POST'))
# @login_required
# def create():
#     """Create a new post for the current user."""
#     if request.method == 'POST':
#         title = request.form['title']
#         body = request.form['body']
#         error = None

#         if not title:
#             error = 'Title is required.'

#         if error is not None:
#             flash(error)
#         else:
#             db = get_db()
#             db.execute(
#                 'INSERT INTO post (title, body, author_id)'
#                 ' VALUES (?, ?, ?)',
#                 (title, body, g.user['id'])
#             )
#             db.commit()
#             return redirect(url_for('island.index'))

#     return render_template('island/create.html')


# @bp.route('/<int:id>/update', methods=('GET', 'POST'))
# @login_required
# def update(id):
#     """Update a post if the current user is the author."""
#     post = get_post(id)

#     if request.method == 'POST':
#         title = request.form['title']
#         body = request.form['body']
#         error = None

#         if not title:
#             error = 'Title is required.'

#         if error is not None:
#             flash(error)
#         else:
#             db = get_db()
#             db.execute(
#                 'UPDATE post SET title = ?, body = ? WHERE id = ?',
#                 (title, body, id)
#             )
#             db.commit()
#             return redirect(url_for('island.index'))

#     return render_template('island/update.html', post=post)


# @bp.route('/<int:id>/delete', methods=('POST',))
# @login_required
# def delete(id):
#     """Delete a post.

#     Ensures that the post exists and that the logged in user is the
#     author of the post.
#     """
#     get_post(id)
#     db = get_db()
#     db.execute('DELETE FROM post WHERE id = ?', (id,))
#     db.commit()
#     return redirect(url_for('island.index'))
