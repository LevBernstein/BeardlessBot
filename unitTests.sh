#run `bash unitTests.sh` to run bb's unit tests, output results to stdout and testResults.md
echo "# Beardless Bot Unit Test Results" > testResults.md;
coverage run -m pytest -Wignore --tb=line |& tee -a testResults.md;
coverage report --include=$(echo $PWD)/* |& tee -a testResults.md;