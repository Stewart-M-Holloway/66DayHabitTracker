import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..')))

# Must be imported after system path
import lambda_function
import habit_tracker_utils
