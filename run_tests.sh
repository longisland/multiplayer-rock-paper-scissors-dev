#!/bin/bash

# Exit on error
set -e

echo "Running tests in Docker..."
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml build
docker-compose -f docker-compose.test.yml up --abort-on-container-exit