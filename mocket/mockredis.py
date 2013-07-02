import shlex
from itertools import chain
from mocket import Mocket, MocketEntry, CRLF


class Request(object):
    def __init__(self, data):
        self.data = data


class Response(object):
    def __init__(self, reply):
        self.reply = reply

    def __str__(self):
        return Redisizer.redisize(self.reply)


class Redisizer(str):
    @staticmethod
    def tokens(mapping):
        """
        >>> Redisizer.tokens({'f1': 'one', 'f2': 'two'})
        ['*2', '$2', 'f1', '$2', 'f2']
        >>> Redisizer.tokens(['SET', 'mocket', 'is awesome!'])
        ['*3', '$3', 'SET', '$6', 'mocket', '$11', 'is awesome!']
        """
        return ['*{0}'.format(len(mapping))] + list(chain(*zip(['${0}'.format(len(x)) for x in mapping], mapping)))

    @classmethod
    def redisize(cls, data):
        r"""
        >>> Redisizer.redisize(10)
        ':10\r\n'
        >>> Redisizer.redisize({'f1': 'one', 'f2': 'two'})
        '*4\r\n$2\r\nf1\r\n$3\r\none\r\n$2\r\nf2\r\n$3\r\ntwo\r\n'
        >>> Redisizer.redisize(Redisizer.command('OK'))
        '+OK\r\n'
        >>> Redisizer.redisize('is awesome!')
        '$11\r\nis awesome!\r\n'
        >>> Redisizer.redisize(['1st', '2nd', 'and 3rd'])
        '*3\r\n$3\r\n1st\r\n$3\r\n2nd\r\n$7\r\nand 3rd\r\n'
        """
        if isinstance(data, cls):
            return data
        CONVERSION = {
            dict: lambda x: CRLF.join(cls.tokens(list(chain(*tuple(x.items()))))),
            int: lambda x: ':{0}'.format(x),
            str: lambda x: CRLF.join(['${0}'.format(len(x)), x]),
            list: lambda x: CRLF.join(cls.tokens(x)),
        }
        return cls(CONVERSION.get(type(data), lambda x: x)(data) + CRLF)

    @classmethod
    def command(cls, description, _type='+'):
        r"""
        >>> Redisizer.command('OK')
        '+OK\r\n'
        """
        return cls(''.join([_type, description, CRLF]))

    @classmethod
    def error(cls, description):
        r"""
        >>> Redisizer.error('ERR this is ugly!')
        '-ERR this is ugly!\r\n'
        """
        return cls.command(description, _type='-')

OK = Redisizer.command('OK')
QUEUED = Redisizer.command('QUEUED')


class Entry(MocketEntry):
    request_cls = Request
    response_cls = Response

    def __init__(self, addr, command, responses):
        super(Entry, self).__init__(addr or ('localhost', 6379), responses)
        self.command = self._redisize(command)

    @classmethod
    def _redisize(cls, command):
        """
        >>> Entry._redisize('SET "mocket" "is awesome!"')
        ['*3', '$3', 'SET', '$6', 'mocket', '$11', 'is awesome!']
        >>> Entry._redisize('set "mocket" "is awesome!"')
        ['*3', '$3', 'SET', '$6', 'mocket', '$11', 'is awesome!']
        """
        d = shlex.split(command)
        d[0] = d[0].upper()
        return Redisizer.tokens(d)

    def can_handle(self, data):
        return data.splitlines() == self.command

    @staticmethod
    def register(addr, command, *responses):
        responses = [Entry.response_cls(r) for r in responses]
        Mocket.register(Entry(addr, command, responses))

    @staticmethod
    def single_register(command, response, addr=None):
        Entry.register(addr, command, response)

    @staticmethod
    def multi_register(command, responses, addr=None):
        Entry.register(addr, command, *responses)
