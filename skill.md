---
name: emotion
description: Change the ASCII hamster's emotion on the local dev server
user_invocable: true
arguments:
  - name: emotion
    description: "The emotion to set. One of: happy, sad, angry, surprised, sleepy, love, excited, neutral"
    required: true
---

# Emotion Skill

Set the ASCII hamster's emotion by sending a POST request to the local dev server.

## Available Emotions
happy, sad, angry, surprised, sleepy, love, excited, neutral

## Instructions

Run this curl command to change the emotion:

```bash
curl -s -X POST http://localhost:3000/api/emotion \
  -H "Content-Type: application/json" \
  -d "{\"emotion\": \"$ARGUMENTS_EMOTION\"}"
```

Then confirm to the user that the emotion was changed.
