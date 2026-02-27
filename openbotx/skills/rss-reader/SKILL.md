---
name: rss-reader
description: Read RSS/Atom feeds to get latest articles, news, and updates from any source. Use when the user wants to monitor news feeds, check blog updates, or pull latest posts from a website.
---

# RSS Reader

Use the `rss_reader` tool to fetch and parse RSS/Atom feeds.

## Tool: `rss_reader`

### Basic usage

```
rss_reader(url="https://www.coindesk.com/arc/outboundfeeds/rss/")
```

### Limit entries

```
rss_reader(url="https://cointelegraph.com/rss", count=5)
```

## Common Feeds

### Crypto & Web3
- CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
- CoinTelegraph: `https://cointelegraph.com/rss`
- The Block: `https://www.theblock.co/rss.xml`
- Decrypt: `https://decrypt.co/feed`

### Tech
- TechCrunch: `https://techcrunch.com/feed/`
- Hacker News: `https://hnrss.org/frontpage`
- The Verge: `https://www.theverge.com/rss/index.xml`
- Ars Technica: `https://feeds.arstechnica.com/arstechnica/index`

### General News
- BBC World: `https://feeds.bbci.co.uk/news/world/rss.xml`
- NPR: `https://feeds.npr.org/1001/rss.xml`

## Tips

- Each entry returns: `title`, `link`, `published`, `summary`.
- Use `count` to limit entries when you only need recent headlines.
- Combine with `cron` to set up recurring feed monitoring.
- HTML tags are automatically stripped from summaries.
- If a site's feed URL is unknown, try `/feed`, `/rss`, `/atom.xml`, or `/rss.xml`.
