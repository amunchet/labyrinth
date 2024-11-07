#!/bin/sh
CODECOV="95"
DOCKER_PROD_NAME="labyrinth-backend-1"
ARGS="$@"
# Running Python unit tests and coverage
echo "Running Pytest..."
# -x is stop on first failure


docker
if [ $? -eq 127 ]; then
    echo "No docker found.  Assuming we're inside of backend docker."
    cd /src && PYTHONPATH=/src pytest --cov=/src --cov-report term-missing -vvvv --cov-fail-under=95 --cov-report=html $ARGS . 

else
    docker ps
    docker logs $DOCKER_PROD_NAME
    echo "Running tests in local"
    docker start $DOCKER_PROD_NAME
    docker exec $DOCKER_PROD_NAME sh -c "cd /src && PYTHONPATH=/src pytest --cov=/src --cov-report term-missing -vvvv --cov-fail-under=95 --cov-report=html $ARGS . "
fi