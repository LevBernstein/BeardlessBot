#!/usr/bin/env bash

#Run `bash unitTests.sh` to run bb's unit tests,
#output results to stdout and testResults.md

echo "# Beardless Bot Unit Test Results" > testResults.md;
python3 -m coverage run --include=$(echo $PWD)/* --omit=./*env/* \
	-m pytest -W ignore::DeprecationWarning --ignore=./*env/* --tb=line \
	--junitxml=junit.xml;
python3 -m coverage report -m --precision=2 |& tee -a testResults.md;
python3 -m coverage xml 1> /dev/null;
rm resources/images/coverage.svg 2> /dev/null;
genbadge coverage -i coverage.xml -o \
	resources/images/coverage.svg >> /dev/null;
rm .coverage 2> /dev/null;
rm coverage.xml 2> /dev/null;
python3 -m flake8 --exclude="*env/*" --ignore=W191,W503 --statistics \
	--exit-zero --output-file flake8stats.txt;
genbadge flake8 -i flake8stats.txt -o \
	resources/images/flake8-badge.svg >> /dev/null;
rm flake8stats.txt 2> /dev/null;
genbadge tests -i junit.xml -o resources/images/tests.svg >> /dev/null;
rm junit.xml 2> /dev/null;
docstr-coverage ./ -e ".*bb_test.py/*|.*env/*" -v 0 --badge \
	resources/images/docstr-coverage.svg 2> /dev/null;

#Truncate decimals in coverage badge. Very hacky; I wish
#there was an arg for significant figures.
python3 -c '
import re
with open("resources/images/coverage.svg") as f:
	svg = f.read()
with open("resources/images/coverage.svg", "w") as g:
	g.write(re.sub(r"((\.\d{2})%+)", ".00%", svg))'
