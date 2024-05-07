#!/usr/bin/env bash

#run `bash unitTests.sh` to run bb's unit tests,
#output results to stdout and testResults.md

echo "# Beardless Bot Unit Test Results" > testResults.md;
python3 -m coverage run --include=$(echo $PWD)/* --omit=*/lib/* -m \
	pytest -Wignore --ignore=*/lib/* --tb=line |& tee -a testResults.md;
python3 -m coverage report -m |& tee -a testResults.md;
rm resources/images/coverage.svg 2>/dev/null;
python3 -m coverage_badge -q -o resources/images/coverage.svg;
rm .coverage 2>/dev/null;
