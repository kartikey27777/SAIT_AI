#!/bin/bash
echo "===================================="
echo "   SAIT AI - Quick Setup"
echo "===================================="
echo

echo "[1/4] Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found! Install Docker first."
    echo "https://docs.docker.com/engine/install/"
    exit 1
fi
echo "Docker OK!"

echo
echo "[2/4] Creating data directories..."
mkdir -p data/uploads data/postgres

echo
echo "[3/4] Starting SAIT AI..."
docker compose up -d

echo
echo "[4/4] Waiting for services to start..."
sleep 30

echo
echo "===================================="
echo "   SAIT AI is ready!"
echo "===================================="
echo
echo "   Chat UI:    http://localhost:3005"
echo "   Backend:    http://localhost:8083"
echo "   Documents:  http://localhost:8083/documents"
echo
echo "   Upload a PDF and start chatting!"
echo "===================================="