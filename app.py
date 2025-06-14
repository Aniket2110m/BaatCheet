from flask import Flask, render_template, redirect, url_for, request, flash
from flask_socketio import SocketIO, join_room, emit
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from models import db, User
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SESSION_COOKIE_SECURE'] = False  # For local dev
db.init_app(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)

login_manager.login_view = 'login'

users_in_rooms = defaultdict(set)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        remember = bool(request.form.get("remember"))
        if not username:
            error = "Username is required."
        else:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username)
                db.session.add(user)
                db.session.commit()
            login_user(user, remember=remember)
            return redirect(url_for("chat"))
    return render_template("login.html", error=error)


@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html", username=current_user.username)


@socketio.on('join')
def handle_join(data):
    join_room(data['room'])
    users_in_rooms[data['room']].add(data['username'])
    emit(
        "message",
        {
            "msg": f"{data['username']} has joined {data['room']}",
            "username": None
        },
        room=data['room']
    )
    emit(
        "user_list",
        {"users": list(users_in_rooms[data['room']])},
        room=data['room']
    )


@socketio.on('send_message')
def handle_message(data):
    emit(
        "message",
        {"msg": data['msg'], "username": data['username']},
        room=data['room']
    )


@socketio.on('disconnect')
def handle_disconnect():
    # This event doesn't provide username/room directly.
    # You may want to handle user leaving
    # via a custom event from the client if needed.
    pass


@socketio.on('leave')
def handle_leave(data):
    room = data['room']
    username = data['username']
    users_in_rooms[room].discard(username)
    emit(
        "message",
        {
            "msg": f"{username} has left {room}",
            "username": None
        },
        room=room
    )
    emit(
        "user_list",
        {"users": list(users_in_rooms[room])},
        room=room
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("login"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
