#!/bin/bash

poetry install

# Run both scripts in the background and save their output to log files
poetry run python flask_oauth.py > flask_oauth.log 2>&1 &
poetry run python diplomacy_bot.py > diplomacy_bot.log 2>&1 &

# Wait for both background processes to finish
wait

echo "Both scripts have finished running."
