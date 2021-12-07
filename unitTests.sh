#run `bash unitTests.sh` to run bb's unit tests, output results to stdout and testResults.md
echo "# Beardless Bot Unit Test Results" > testResults.md;
python3 -m coverage run -m pytest -Wignore --tb=line |& tee -a testResults.md;
python3 -m coverage report -m --include=$(echo $PWD)/* |& tee -a testResults.md;
rm resources/coverage.svg;
python3 -m coverage_badge -q -p -o resources/coverage.svg;
rm .coverage;
