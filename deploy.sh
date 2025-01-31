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
            actual_commit=$(echo $response | grep -o '"git_commit":"[^"]*' | cut -d'"' -f4)
            
            if [ "$actual_commit" = "$expected_commit" ]; then
                echo "Version check passed! Running expected commit: $expected_commit"
                return 0
            else
                echo "Wrong version running. Expected: $expected_commit, Got: $actual_commit"
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
docker-compose up -d

# Check if the correct version is running
if ! check_version "$GIT_COMMIT"; then
    echo "Deployment failed: Version check failed"
    docker-compose logs web
    docker-compose down -v
    exit 1
fi

echo "Deployment successful!"