#!/bin/bash
set -e

# Function to check if the version endpoint returns the expected commit
check_version() {
    local expected_commit=$1
    local max_attempts=30
    local attempt=1
    local wait_time=2

    echo "Waiting for application to start and checking version..."
    
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt of $max_attempts..."
        
        # Try to get version info
        if response=$(curl -s http://localhost:5000/api/version); then
            actual_commit=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('git_commit', ''))")
            build_time=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('build_time', ''))")
            
            if [ "$actual_commit" = "$expected_commit" ]; then
                echo "Version check passed!"
                echo "Running commit: $actual_commit"
                echo "Build time: $build_time"
                return 0
            else
                echo "Wrong version running."
                echo "Expected commit: $expected_commit"
                echo "Actual commit: $actual_commit"
                echo "Build time: $build_time"
            fi
        else
            echo "Service not responding yet..."
        fi
        
        attempt=$((attempt + 1))
        sleep $wait_time
    done
    
    echo "Version check failed after $max_attempts attempts"
    return 1
}

# Get the current git commit hash
GIT_COMMIT=$(git rev-parse HEAD)
echo "Deploying commit: $GIT_COMMIT"

# Stop any running containers and remove them along with their volumes
echo "Stopping existing containers..."
docker-compose down -v

# Remove all images related to the application
echo "Removing old images..."
docker images | grep 'rps-game-web' | awk '{print $3}' | xargs -r docker rmi -f

# Build with the current commit hash
echo "Building new image..."
GIT_COMMIT=$GIT_COMMIT docker-compose build --no-cache web

# Start the services
echo "Starting services..."
GIT_COMMIT=$GIT_COMMIT docker-compose up -d

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Apply database migrations
echo "Applying database migrations..."
for migration in migrations/*.sql; do
    if [ -f "$migration" ]; then
        echo "Applying migration: $migration"
        docker exec rps-game-db-1 psql -U postgres -d rps_game -f "/app/migrations/$migration"
    fi
done

# Check if the correct version is running
if ! check_version "$GIT_COMMIT"; then
    echo "Deployment failed: Version check failed"
    docker-compose logs web
    docker-compose down -v
    exit 1
fi

echo "Deployment successful!"