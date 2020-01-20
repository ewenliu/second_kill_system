# -*- coding: utf-8 -*-#

from flask import Flask
import config
from apps.front import bp as front_bp


def creat_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(config)
    flask_app.register_blueprint(front_bp)
    return flask_app


if __name__ == '__main__':
    app = creat_app()
    app.run()
