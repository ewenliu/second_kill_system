# -*- coding: utf-8 -*-#
import config
from redis import Redis

redis_conn = Redis(host=config.REDIS_HOST, password=config.REDIS_PWD)
