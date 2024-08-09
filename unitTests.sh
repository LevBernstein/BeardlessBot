#!/usr/bin/env bash

#Run `bash unitTests.sh` to run bb's unit tests,
#output results to stdout and testResults.md

docstr-coverage ./ -e ".*/venv" -v 0 --badge resources/images/docstr-coverage.svg;
echo "# Beardless Bot Unit Test Results" > testResults.md;
python3 -m coverage run --include=$(echo $PWD)/* --omit=*/lib/* \
	-m pytest -W ignore::DeprecationWarning --ignore=*/lib/* --tb=line \
	--junitxml=junit.xml |& tee -a testResults.md;
python3 -m coverage report -m |& tee -a testResults.md;
python3 -m coverage xml 1> /dev/null;
rm resources/images/coverage.svg 2> /dev/null;
genbadge coverage -i coverage.xml -o resources/images/coverage.svg >> /dev/null;
rm .coverage 2> /dev/null;
rm coverage.xml 2> /dev/null;
python3 -m flake8 --exclude="venv/*" --ignore=W191,W503 --statistics \
	--exit-zero --output-file flake8stats.txt;
genbadge flake8 -i flake8stats.txt -o resources/images/flake8-badge.svg >> /dev/null;
rm flake8stats.txt 2> /dev/null;
genbadge tests -i junit.xml -o resources/images/tests.svg >> /dev/null;
rm junit.xml 2> /dev/null;

#Truncate decimals in coverage badge. Very hacky; I wish there was an arg for significant figures.
python3 -c '
import re
with open("resources/images/coverage.svg", "r") as f: svg = f.read()
with open("resources/images/coverage.svg", "w") as g: g.write(re.sub(r"((\.\d{2})%+)", ".00%", svg))'
