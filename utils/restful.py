# -*- coding: utf-8 -*-#

from flask import jsonify


class HttpCode(object):
    ok = 200
    un_process = 202
    server_error = 500


def restful_result(code, message, data=None):
    return jsonify({'code': code, 'message': message, 'data': data or {}})


def success(message='', data=None):
    return restful_result(code=HttpCode.ok, message=message, data=data)


def un_process(message='', data=None):
    return restful_result(code=HttpCode.un_process, message=message, data=data)
