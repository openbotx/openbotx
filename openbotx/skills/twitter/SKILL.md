---
name: twitter
description: Post tweets on Twitter/X. Use when the user wants to tweet, post on X, create threads, or share content on Twitter. Requires the "twitter" auth profile configured in http_client.
always: false
---

# Twitter / X Posting

Use the `http_client` tool with `auth: "twitter"` to interact with the Twitter/X API.

## Post a text tweet

```
http_client(
  method="POST",
  url="https://api.twitter.com/2/tweets",
  auth="twitter",
  body="{\"text\": \"Hello from OpenBotX!\"}"
)
```

Response includes `data.id` (the tweet ID) and `data.text`.

## Reply to a tweet (threads)

Use `reply.in_reply_to_tweet_id` to create a reply or thread:

```
http_client(
  method="POST",
  url="https://api.twitter.com/2/tweets",
  auth="twitter",
  body="{\"text\": \"This is a reply\", \"reply\": {\"in_reply_to_tweet_id\": \"1234567890\"}}"
)
```

To create a thread, post the first tweet, then reply to it with the returned tweet ID.

## Upload media and attach to tweet

### Step 1: Upload the image

Upload the image file to Twitter's media endpoint using multipart form data:

```
http_client(
  method="POST",
  url="https://upload.twitter.com/1.1/media/upload.json",
  auth="twitter",
  upload_file="/path/to/image.jpg",
  upload_field="media"
)
```

The response includes `media_id_string`.

### Step 2: Post tweet with media

```
http_client(
  method="POST",
  url="https://api.twitter.com/2/tweets",
  auth="twitter",
  body="{\"text\": \"Check this out!\", \"media\": {\"media_ids\": [\"MEDIA_ID_HERE\"]}}"
)
```

## Delete a tweet

```
http_client(
  method="DELETE",
  url="https://api.twitter.com/2/tweets/TWEET_ID_HERE",
  auth="twitter"
)
```

## Tips

- Tweet text max: 280 characters.
- The `auth: "twitter"` parameter applies OAuth 1.0a signing automatically.
- Media upload uses the v1.1 endpoint; tweet creation uses the v2 endpoint.
- For threads, always save the `data.id` from each tweet to chain replies.
- Supported image formats: JPEG, PNG, GIF, WEBP (max 5MB for images, 15MB for GIFs).
