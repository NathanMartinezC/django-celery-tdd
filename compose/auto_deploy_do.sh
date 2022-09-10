#! /bin/bash

# This shell script quickly deploys your project to your
# Digital Ocean Droplet

if [ -z "$DIGITAL_OCEAN_IP_ADDRESS"]
then
    echo "DIGITAL_OCEAN_IP_ADDRESS not defined"
    exit 0
fi

# Generate TAR file from git
git archive --format tar --output ./project.tar main

echo 'Uploading project...'
rsync ./project.tar root@$DIGITAL_OCEAN_IP_ADDRESS:/tmp/project.tar
echo 'Uploaded complete.'

echo 'Building image...'
ssh -o StrictHostKeyChecking=no root@$DIGITAL_OCEAN_IP_ADDRESS << 'ENDSSH'
    mkdir -p /app
    rm -rf /app/* && tar -xf /tmp/project.tar -C /app
    docker-compose -f /app/docker-compose.prod.yml build
ENDSSH
echo 'Build complete.'