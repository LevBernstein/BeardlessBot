#run `bash unitTests.sh' to run bb's unit tests
echo "# Beardless Bot Unit Test Results" > testResults.md;
pytest --tb=line |& tee -a testResults.md; #outputs the result of pytest to stdout and to testResults.md