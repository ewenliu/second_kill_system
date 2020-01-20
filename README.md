## 基于python flask web框架的秒杀系统实现

### 写在前面

尝试用python+redis实现秒杀系统的架构设计，侧重于架构，故省略了很多业务相关的**消息队列**接口代码，这也是本系统的不足之处，将来有机会还是慢慢补全接口吧。

本文假设你拥有 redis/flask/python 的使用基础。

秒杀系统，无非是并发流量极大，比如阿里的双11，京东的618等，并发流量上来了，数据库就成了速度瓶颈，redis是一种**内存型键值非关系数据库**，众所周知，redis的读写速度极快，而且从架构上来说，其也具有高可用特性（**集群，哨兵，主从**等等），redis+mysql的组合方式能最大限度地承受突然的并发流量，使得数据库不至于突然挂掉。

### 更多的承受秒杀系统的策略

1. 前端
    - 限制连续提交，比如点击了一次下单之后，不管成功与否，将该提交按钮置为不可提交
    - 采用验证码

2. 网络
    - 限制一个IP的请求次数

3. nginx
    - 负载均衡
    - 缓存
    - CDN

4. 服务级别
    - redis
    - 消息队列解耦

5. 数据库
    - 读写分离
    - 主从结构
    - 分库分表

### 订单请求

**Redis库存校验**

秒杀上线前，将库存提前写入redis，以供库存接口调用查询，这里由于redis本身的单线程特性，所以不需要加锁。


```python
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

```

**订单处理**


```python
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

```

### 支付请求

下单后，会返回一个订单号给用户，用户必须在指定的时间内付款，支付前需要判断：

1. 订单号对应的用户是否是当前请求用户(相关代码省略没写)
2. 订单是否超时

**支付处理**

```python
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

```

### Redis zset延列检测

下单后，订单号和订单时间作为value和score放入zset，以下代码用来检测最小的score（对应zset延时队列现存的最早的订单）和现在的时间差值是否超过一定间隔，比如本例采用了60*5（即300秒）为间隔，如果订单下单后5分钟还未支付，即视为订单超时，如下代码用来检测并且将超时订单写入超时set中以供支付api查询。


```python
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


```


### 总结

本系统的核心是：
1. redis承担库存读写和订单存储相关任务
2. 未来使用消息队列异步来处理订单/支付等操作

总结整体流程：
1. 用户下单
    - 判断商品库存
    - 有库存，redis存入订单相关信息，订单相关消息队列接口产生消息
        - 用户ID存入相关订单信息，供后续支付接口判断当前用户是否为下单用户
        - 订单信息进入redis zset延时队列
        - 订单队列产生消息，消费者消费消息后，执行对应的操作，如mysql库存/订单操作（代码省略）
    - 没库存或内部异常， 直接返回
    - 下单结束

2. 请求支付
    - 从redis的订单信息中取出订单对用的用户，判断是否为当前请求支付用户（代码省略）
    - 判断是否超时
        - 如果没超时，那么支付成功，从延时队列/订单信息中删除对应的订单
        - 将订单信息写入已支付订单
        - 触发支付消息队列生产，供后台支付/mysql/商家等接口调用
    - 如果超时直接返回失败
    - 支付结束

3. 总结
    - 本文省略消息队列相关的接口处理，专注于业务层面的架构实现，许多细节地方均为涉及（比如异常处理，redis高可用等待）
    - 省略mysql相关操作，高并发情况下尽量使用redis，mysql可以用消息队列来异步执行



