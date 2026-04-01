#!/bin/sh

ollama serve &

until curl -s http://localhost:11434/api/tags >/dev/null; do
  echo "Waiting for Ollama API..."
  sleep 2
done

echo "Pulling model..."
ollama pull llama3:8b-instruct-q4_0

echo "Ollama ready."

wait
