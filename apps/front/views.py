# -*- coding: utf-8 -*-#
from flask import Blueprint, request
from utils.order_process import stock_check, order_create, overtime_zset_push, overtime_check, pay_order
from utils import restful
from uuid import uuid1
from time import time

bp = Blueprint('front', __name__)


@bp.route('/')
def index():
    return '你好'


# 下单接口
@bp.route('/purchase/')
def purchase():
    """
        流程：
        1. 库存申请
            - 判断redis有没有库存
            - 当库存消耗完，直接返回失败。
            - 无需考虑多线程竞争问题，因为redis本身是单线程执行
        2. 订单处理
            - 将用户信息，商品信息，订单号 写入redis
            - 写入redis订单 + 超时队列
        3. 不足
            - 省略消息队列部分
    :return:
    """

    user_id = str((request.args.get("user_id")) or '1')
    goods_id = str((request.args.get("goods_id")) or '1')
    order_time = time()

    stock_flag = stock_check(goods_id)

    # 如果有库存
    if stock_flag:
        # 使用uuid1()根据mac和时间戳产生唯一的订单号
        order_id = str(uuid1())

        # 订单信息
        # order_time用于记录订单生成时间，用于redis zset的score，用于排序用，每次按照时间提取出最早的订单，判断是否超时
        order_info = {
            'goods_id': goods_id,
            'user_id': user_id,
            'order_id': order_id,
            'order_time': order_time
        }

        try:
            # 更好的做法是，订单redis相关操作也放在消息队列里供消费，同时直接返回给用户秒杀成功界面。

            # redis hash记录订单号和用户号
            order_create(order_info)
            # redis zset订单入队
            overtime_zset_push(order_info)

            # 订单消息队列相关处理待加入

            return restful.success(message='秒杀成功，请尽快付款！', data={'order_id': order_id})

        except Exception as e:
            print(e)
            return restful.un_process(message='抢购失败，请重试!')

    else:
        return restful.success(message='无此物库存!')


@bp.route('/pay/')
def pay():
    user_id = str((request.args.get("user_id")) or '1')
    goods_id = str((request.args.get("goods_id")) or '1')
    order_id = str(request.args.get("order_id"))

    order_info = {
        "goods_id": goods_id,
        "user_id": user_id,
        "order_id": order_id
    }

    # 不足：支付时应该判断当前用户是否和订单用户一致
    # 超时标志位
    overtime_flag = overtime_check(order_info)

    if overtime_flag:
        return restful.un_process(message='对不起，订单已超时！')
    else:
        # redis相关订单操作
        pay_order(order_info)
        # 支付相关的消息队列待加入
        return restful.success(message='支付成功')
