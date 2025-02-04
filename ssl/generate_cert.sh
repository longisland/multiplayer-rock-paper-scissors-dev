#!/bin/bash

# Generate SSL certificate for rockpaperscissors.fun
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout rockpaperscissors.fun.key \
    -out rockpaperscissors.fun.crt \
    -subj "/C=US/ST=New York/L=New York/O=RPS Game/CN=rockpaperscissors.fun" \
    -addext "subjectAltName=DNS:rockpaperscissors.fun,DNS:www.rockpaperscissors.fun"