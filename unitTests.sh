#!/usr/bin/env bash

#Run `bash unitTests.sh` to run bb's unit tests,
#output results to stdout and testResults.md

echo "# Beardless Bot Unit Test Results" > testResults.md;
python3 -m coverage run --include=$(echo $PWD)/* --omit=*/lib/* -m \
	pytest -Wignore --ignore=*/lib/* --tb=line |& tee -a testResults.md;
python3 -m coverage report -m |& tee -a testResults.md;
python3 -m coverage xml;
rm resources/images/coverage.svg 2>/dev/null;
genbadge coverage -i coverage.xml -o resources/images/coverage.svg
rm .coverage 2>/dev/null;
rm coverage.xml 2>/dev/null;

#Truncate decimals in coverage badge. Very hacky; I wish there was an arg for significant figures.
python3 -c '
import re
with open("resources/images/coverage.svg", "r") as f: svg = f.read()
with open("resources/images/coverage.svg", "w") as g: g.write(re.sub(r"((\.\d{2})%+)", "%", svg))'
