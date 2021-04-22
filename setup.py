# flake8: noqa
"""Installation script for fastapi-redis-cache."""
from pathlib import Path

from setuptools import find_packages, setup

DESCRIPTION = "`fastapi-redis-cache` provides a simple way to cache response data for API endpoints using Redis."
APP_ROOT = Path(__file__).parent
README = (APP_ROOT / "README.md").read_text().strip()
AUTHOR = "Aaron Luna"
AUTHOR_EMAIL = "contact@aaronluna.dev"
PROJECT_URLS = {
    "Bug Tracker": "https://github.com/a-luna/fastapi-redis-cache/issues",
    "Source Code": "https://github.com/a-luna/fastapi-redis-cache",
}
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Natural Language :: English",
    "Operating System :: MacOS :: MacOS X",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Unix",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3 :: Only",
]
INSTALL_REQUIRES = [
    "fastapi",
    "pydantic",
    "python-dateutil",
    "redis",
]

exec(open(str(APP_ROOT / "src/fastapi_redis_cache/version.py")).read())
setup(
    name="fastapi-redis-cache",
    description=DESCRIPTION,
    long_description=README,
    long_description_content_type="text/markdown",
    version=__version__,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    maintainer=AUTHOR,
    maintainer_email=AUTHOR_EMAIL,
    license="MIT",
    url=PROJECT_URLS["Source Code"],
    project_urls=PROJECT_URLS,
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.8",
    classifiers=CLASSIFIERS,
    install_requires=INSTALL_REQUIRES,
)
