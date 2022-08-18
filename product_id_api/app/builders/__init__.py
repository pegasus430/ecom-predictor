import inspect

from importlib import import_module
from pkgutil import iter_modules


def load_builders(path):

    def walk_modules(path):
        mods = []
        mod = import_module(path)
        mods.append(mod)
        if hasattr(mod, '__path__'):
            for _, subpath, ispkg in iter_modules(mod.__path__):
                fullpath = path + '.' + subpath
                if ispkg:
                    mods += walk_modules(fullpath)
                else:
                    submod = import_module(fullpath)
                    mods.append(submod)
        return mods

    builders = {}

    for module in walk_modules(path):
        for obj in vars(module).itervalues():
            if inspect.isclass(obj)\
                    and issubclass(obj, Builder)\
                    and obj.__module__ == module.__name__\
                    and getattr(obj, 'retailer', None):
                builders[obj.retailer] = obj

    return builders


class Builder(object):
    retailer = None

    @staticmethod
    def build_url(web_id):
        raise NotImplementedError
