# -*- coding: utf-8 -*-
from exts import redis_conn
import time
import uuid


def test_data_add():
    for i in range(5):
        time.sleep(2)
        order_id = str(uuid.uuid1())
        cur_time = time.time()
        print(order_id, cur_time)
        redis_conn.zadd('test', mapping={order_id: cur_time})


def overtime_process(set_wait_for_ot, overtime_set):
    overtime_limit = 60*5  # 5分钟=300秒
    while True:
        time.sleep(1)
        cur_time = time.time()
        len_set_wait_for_ot = redis_conn.zcard(set_wait_for_ot)
        if len_set_wait_for_ot:
            # 获取订单日期最早的set
            longest_order_set = redis_conn.zrange(set_wait_for_ot, start=0, end=0, withscores=True)
            # 获取订单号
            longest_order_id = longest_order_set[0][0]
            # 获取下单时间
            longest_order_time = longest_order_set[0][1]
            # 判断是否超时
            if cur_time-longest_order_time > overtime_limit:
                # 如果超时，则订单号存入redis超时set以供其他模块消费
                redis_conn.sadd(overtime_set, longest_order_id)
                # 从zset删除已超时订单
                redis_conn.zrem(set_wait_for_ot, longest_order_id)
                print('订单 %s 已经过时，移入超时集合 %s' % (longest_order_id, overtime_set))
            else:
                print('没有超时订单，继续检测......')
        else:
            print('延时队列为空，等待订单接入......')


if __name__ == '__main__':
    # test_data_add()
    overtime_process(set_wait_for_ot='zset_goods_1', overtime_set="order:" + str(1) + ":" + "overtime")
