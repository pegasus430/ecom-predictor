from setuptools import setup, find_packages
import os
import itertools


setup(
    name='product-ranking',
    version='1.0',
    packages=find_packages(),
    entry_points={'scrapy': ['settings = product_ranking.settings']},
    zip_safe=False,  # Because of Captcha Breaker.
    include_package_data=True,
    data_files=[
        (root, [os.path.join(root, f) for f in files])
        for root, _, files in itertools.chain(
            os.walk('train_captchas_data'),
            os.walk('product_ranking/data'),
            os.walk('monitoring'),
            os.walk('../product_ranking_auto_tests'),
            os.walk('spiders_shared_code'),  # TODO: test!
            os.walk('product_ranking/validators')
        )
    ],
    install_requires=[
        "Scrapy>=0.22",
    ],
    extras_require={
        'Captcha Breaker': ["numpy"],
    }
)
