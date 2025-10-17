A step by step guide on how to install the TWS API Python package.

1. Download [TWS API](https://interactivebrokers.github.io/#)
2. Navigate to twsapi_macunix.1037.02/IBJts/source/pythonclient
3. Create a new virtual environment using ```python -m venv .venv```
4. Change into the new virtual environment ```source .venv/bin/activate```
5. ```python setup.py sdist```
   1. Sometimes Python is missing setuptools, then install using ```pip install setuptools```
6. Buld the wheel ```python setup.py bdist_wheel```
7. Copy and use the **ibapi-10.37.2-py3-none-any.whl** file!
