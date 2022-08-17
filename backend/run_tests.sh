#!/bin/sh
CODECOV="95"
DOCKER_PROD_NAME="labyrinth_backend_1"
ARGS="$@"
# Running Python unit tests and coverage
echo "Running Pytest..."
# -x is stop on first failure


docker
if [ $? -eq 127 ]; then
    echo "No docker found.  Assuming we're inside of backend docker."
    cd /src && PYTHONPATH=/src pytest --cov=/src --cov-report term-missing -vvvv --cov-fail-under=95 --cov-report=html $1 . 

else
    echo "Running tests in local"
    docker exec $DOCKER_PROD_NAME sh -c "cd /src && PYTHONPATH=/src pytest --cov=/src --cov-report term-missing -vvvv --cov-fail-under=95 --cov-report=html $ARGS . "
fi