from distutils.core import setup

setup(name='url_service',
      version='0.1dev',
      description='Service that manages a queue of URLs',
      author='Javier Ruere',
      author_email='javier@ruere.com.ar',
      py_modules=['url_service', 'test_url_service'],
      requires=[
          'pyramid',
          'requests',
      ])
