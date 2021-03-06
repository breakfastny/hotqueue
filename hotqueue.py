# -*- coding: utf-8 -*-

"""HotQueue is a Python library that allows you to use Redis as a message queue
within your Python programs.
"""

from functools import wraps
try:
    import cPickle as pickle
except ImportError:
    import pickle

from redis import Redis


__all__ = ['HotQueue', 'HotStack']

__version__ = '0.2.3'


def key_for_name(name):
    """Return the key name used to store the given queue name in Redis."""
    return 'hotqueue:%s' % name


class HotQueue(object):
    
    """Simple FIFO message queue stored in a Redis list. Example:

    >>> from hotqueue import HotQueue
    >>> queue = HotQueue("myqueue", host="localhost", port=6379, db=0)
    
    :param name: name of the queue
    :param serializer: the class or module to serialize msgs with, must have
        methods or functions named ``dumps`` and ``loads``,
        `pickle <http://docs.python.org/library/pickle.html>`_ will be used
        if ``None`` is given
    :param kwargs: additional kwargs to pass to :class:`Redis`, most commonly
        :attr:`host`, :attr:`port`, :attr:`db`
    """

    redis_block_pop_method = 'blpop'
    redis_pop_method = 'lpop'
    
    def __init__(self, name, serializer=None, **kwargs):
        self.name = name
        if serializer is not None:
            self.serializer = serializer
        else:
            self.serializer = pickle
        self.__redis = Redis(**kwargs)
    
    def __len__(self):
        return self.__redis.llen(self.key)
    
    def __repr__(self):
        return ('<%s: \'%s\', host=\'%s\', port=%d, db=%d>' %
            (self.__class__.__name__, self.name, self.__redis.host, self.__redis.port, self.__redis.db))
    
    @property
    def key(self):
        """Return the key name used to store this queue in Redis."""
        return key_for_name(self.name)
    
    def clear(self):
        """Clear the queue of all messages, deleting the Redis key."""
        self.__redis.delete(self.key)
    
    def consume(self, **kwargs):
        """Return a generator that yields whenever a message is waiting in the
        queue. Will block otherwise. Example:

        >>> for msg in queue.consume(timeout=1):
        ...     print msg
        my message
        another message
        
        :param kwargs: any arguments that :meth:`~hotqueue.HotQueue.get` can
            accept (:attr:`block` will default to ``True`` if not given)
        """
        kwargs.setdefault('block', True)
        try:
            while True:
                msg = self.get(**kwargs)
                if msg is None:
                    break
                yield msg
        except KeyboardInterrupt:
            print; return
    
    def get(self, block=False, timeout=None):
        """Return a message from the queue. Example:
    
        >>> queue.get()
        'my message'
        >>> queue.get()
        'another message'
        
        :param block: whether or not to wait until a msg is available in
            the queue before returning; ``False`` by default
        :param timeout: when using :attr:`block`, if no msg is available
            for :attr:`timeout` in seconds, give up and return ``None``
        """
        if block:
            if timeout is None:
                timeout = 0
            msg = getattr(self.__redis, self.redis_block_pop_method)(self.key, timeout=timeout)
            if msg is not None:
                msg = msg[1]
        else:
            msg = getattr(self.__redis, self.redis_pop_method)(self.key)
        if msg is not None:
            msg = self.serializer.loads(msg)
        return msg
    
    def put(self, *msgs):
        """Put one or more messages onto the queue. Example:
    
        >>> queue.put("my message")
        >>> queue.put("another message")
        """
        for msg in msgs:
            msg = self.serializer.dumps(msg)
            self.__redis.rpush(self.key, msg)
    
    def put_head(self, *msgs):
        """Put one or more message onto the front of the queue"""
        for msg in msgs:
            msg = self.serializer.dumps(msg)
            self.__redis.lpush(self.key, msg)
    
    def worker(self, *args, **kwargs):
        """Decorator for using a function as a queue worker. Example:
    
        >>> @queue.worker(timeout=1)
        ... def printer(msg):
        ...     print msg
        >>> printer()
        my message
        another message
        
        You can also use it without passing any keyword arguments:
        
        >>> @queue.worker
        ... def printer(msg):
        ...     print msg
        >>> printer()
        my message
        another message
        
        :param kwargs: any arguments that :meth:`~hotqueue.HotQueue.get` can
            accept (:attr:`block` will default to ``True`` if not given)
        """
        def decorator(worker):
            @wraps(worker)
            def wrapper():
                for msg in self.consume(**kwargs):
                    worker(msg)
            return wrapper
        if args:
            return decorator(*args)
        return decorator


class HotStack(HotQueue):
    
    """Simple LIFO message queue stored in a Redis list.
    """
    
    redis_block_pop_method = 'brpop'
    redis_pop_method = 'rpop'
    