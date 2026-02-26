---
name: twitter
description: Post tweets on Twitter/X with text and optional images. Use when the user wants to publish content, announcements, or updates on Twitter.
---

# Twitter

Post tweets using the `twitter_post` tool.

## Tool: `twitter_post`

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Tweet text (max 280 characters) |
| `media_path` | string | No | Storage path to an image to attach |
| `reply_to_id` | string | No | Tweet ID to reply to (for creating threads) |

### Text-only tweet

```
twitter_post(text="Hello from our bot!")
```

### Tweet with image

```
twitter_post(text="Check out this visual!", media_path="images/chart.png")
```

### Thread

Post a series of connected tweets. The first call returns a `tweet_id`, use it as `reply_to_id` for subsequent tweets:

```
twitter_post(text="A thread about productivity (1/3)...")
twitter_post(text="Second insight (2/3)...", reply_to_id="<tweet_id from previous>")
twitter_post(text="Final takeaway (3/3)...", reply_to_id="<tweet_id from previous>")
```

## Response

On success the tool returns JSON with:
- `success`: true
- `tweet_id`: the ID of the created tweet
- `text`: the posted text

On error it returns:
- `error`: error description
- `details`: API error body (if available)

## Tips

- Twitter enforces a 280 character limit per tweet.
- Supported media formats: PNG, JPEG, GIF, WEBP.
- For threads, always chain `reply_to_id` from the previous tweet's response.
- The user decides the content and tone of the tweet.
