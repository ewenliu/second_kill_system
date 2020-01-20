# -*- coding: utf-8 -*-#

from exts import redis_conn


def stock_check(goods_id):
    """
        通过商品id 找到对应的redis库存keys
        如果还有库存，那么库存减一，返回成功flag，否则返回失败flag
    :param goods_id:
    :return:
    """

    # 每一次请求，库存减一
    count = redis_conn.decr("stock:"+str(goods_id))

    # 当redis库存不足，拒绝库存申请
    if count < 0:
        return False
    else:
        return True


def order_create(order_info):
    """
        order_info = {
        'goods_id': goods_id,
        'user_id':  user_id,
        'order_id': order_id,
        'order_time': order_time
        }
    """
    goods_id = order_info.get('goods_id')
    order_id = order_info.get('order_id')
    user_id = order_info.get('user_id')

    # redis订单hash: hash[订单号：用户id]
    order_hash_key = 'order' + goods_id
    redis_conn.hset(name=order_hash_key, key=order_id, value=user_id)


def overtime_zset_push(order_info):
    """
        order_info = {
        'goods_id': goods_id,
        'user_id':  user_id,
        'order_id': order_id,
        'order_time': order_time
        }
    """
    goods_id = order_info.get('goods_id')
    order_id = order_info.get('order_id')
    order_time = order_info.get('order_time')

    order_overtime_zset = 'zset_goods_' + goods_id     # redis订单延时队列zset
    redis_conn.zadd(order_overtime_zset, mapping={order_id: order_time})


def overtime_check(order_info):
    order_id = order_info.get("order_id")
    goods_id = order_info.get("goods_id")

    if redis_conn.sismember("order:" + str(goods_id) + ":" + "overtime", order_id):
        return True
    return False


def pay_order(order_info):
    order_id = order_info.get("order_id")
    goods_id = order_info.get("goods_id")
    # 放入已支付订单set
    redis_conn.sadd("order:" + str(goods_id) + ":" + "deal", order_id)
    # 删掉原始订单
    redis_conn.hdel('order' + goods_id, order_id)
    # 删除延迟队列中的key
    redis_conn.zrem('zset_goods_' + goods_id, order_id)
