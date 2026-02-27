---
name: browser
description: Automate browser interactions for web scraping, testing, and navigation. Use when the user needs to visit a webpage, interact with UI elements, take screenshots, or extract content from rendered pages.
requires:
  bins:
    - google-chrome
---

# Browser

Control Chrome browser to navigate pages, interact with elements, capture screenshots, and extract content.

## Tool: `browser`

All browser interactions go through the `browser` tool with an `action` parameter.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | One of: `navigate`, `snapshot`, `screenshot`, `click`, `type`, `press`, `inspect`, `evaluate`, `wait`. |
| `url` | string | Conditional | URL to navigate to. Required for `navigate`. |
| `selector` | string | Conditional | CSS selector. Required for `click` and `type`. |
| `text` | string | Conditional | Text to type. Required for `type`. |
| `key` | string | Conditional | Key name. Required for `press`. |
| `script` | string | Conditional | JavaScript expression. Required for `evaluate`. |
| `seconds` | integer | No | Seconds to wait (default: 2). |
| `max_chars` | integer | No | Max characters for snapshot (default: 50000). |
| `headless` | boolean | No | Run in headless mode (default: false). |

## Actions

### navigate

Load a URL in the browser.

```
browser(action="navigate", url="https://example.com")
```

### inspect

Discover interactive elements on the current page. Returns up to 50 visible elements with their CSS selectors, type, and label. **Always use this after navigating to find selectors for click/type.**

```
browser(action="inspect")
```

### snapshot

Return the visible text content of the page (`document.body.innerText`).

```
browser(action="snapshot")
```

### screenshot

Capture a PNG screenshot of the current viewport.

```
browser(action="screenshot")
```

### click

Click on an element by CSS selector.

```
browser(action="click", selector="#submit-button")
browser(action="click", selector="[aria-label='Search']")
```

### type

Type text into an input field by CSS selector. Clicks to focus first, then types character by character.

```
browser(action="type", selector="input[name='q']", text="search query")
```

### press

Press a special key: Enter, Tab, Escape, Backspace, Delete, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Home, End, Space.

```
browser(action="press", key="Enter")
browser(action="press", key="Escape")
```

### evaluate

Execute JavaScript in the page context and return the result.

```
browser(action="evaluate", script="document.title")
browser(action="evaluate", script="window.scrollTo(0, document.body.scrollHeight)")
```

### wait

Wait for a specified number of seconds.

```
browser(action="wait", seconds=3)
```

## Typical Workflow

1. **Navigate** to the target URL
2. **Inspect** to discover interactive elements and their CSS selectors
3. **Click** or **type** to interact with elements
4. **Press** Enter to submit forms, Escape to dismiss dialogs
5. **Wait** if dynamic content needs time to load
6. **Snapshot** or **screenshot** to verify the result
7. **Evaluate** JavaScript for advanced extraction or interaction

## Tips

- Always **inspect** before clicking or typing to get correct CSS selectors.
- After navigation, wait briefly if the page has dynamic content.
- Use **press** with Escape to dismiss overlays or dialogs before clicking.
- Use **evaluate** for scrolling, extracting `innerText`, or running custom JS.
- For pages behind login, navigate to the login page first, then type credentials and press Enter.
- If an element is not visible, try scrolling with evaluate before retrying.
- Set `headless=true` for background tasks that don't need a visible window.
