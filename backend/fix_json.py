import json
import re

# Read the corrupted JSON file
with open('AI/training_metrics.json', 'r') as f:
    content = f.read()

# Replace all problematic values
content = content.replace('NaN', 'null')
content = content.replace('Infinity', 'null')
content = content.replace('-Infinity', 'null')

# Use regex to catch any remaining problematic values
content = re.sub(r'\b(?:inf|infinity|-inf|-infinity)\b', 'null', content, flags=re.IGNORECASE)

# Write back the fixed JSON
with open('AI/training_metrics.json', 'w') as f:
    f.write(content)

print("Fixed training_metrics.json - replaced NaN/Infinity values with null")

# Validate the JSON is now parseable
try:
    with open('AI/training_metrics.json', 'r') as f:
        json.load(f)
    print("JSON validation successful!")
except Exception as e:
    print(f"JSON validation failed: {e}")
