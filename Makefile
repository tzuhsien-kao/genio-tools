all: html pdf whl

html:
	sphinx-build -b html docs build

pdf:
	sphinx-build -M latexpdf docs build

whl:
	python3 setup.py bdist_wheel
