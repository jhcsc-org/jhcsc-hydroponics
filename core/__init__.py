from flask import Flask
from flask_socketio import SocketIO
from config.settings import FlaskConfig

app = Flask(__name__)
app.config['SECRET_KEY'] = FlaskConfig.SECRET_KEY
socketio = SocketIO(app) 