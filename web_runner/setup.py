import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

requires = [
    'pyramid>=1.5.1',
    # 'pyramid_chameleon',
    # 'pyramid_debugtoolbar',
    'waitress',

    'enum34>=1.0',
    'requests>=2.3.0',
    'subprocess32>=3.2.6',
    'toolz>=0.6',
]

setup(name='web_runner',
      version='0.0',
      description='Service to run Scrapyd spiders and filters over their output',
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
      ],
      author='',
      author_email='',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires + [
          'mock>=1.0.1',
          'pyspecs>=2.2',
      ],
      #test_suite="web_runner",
      entry_points="""\
      [paste.app_factory]
      main = web_runner:main
      """,
      )
