---
name: browser
description: Automate browser interactions for web scraping, testing, and navigation. Use when the user needs to visit a webpage, interact with UI elements, take screenshots, or extract content from rendered pages.
requires:
  bins:
    - google-chrome
---

# Browser

Control a headless Chrome browser to navigate pages, interact with elements, capture screenshots, and extract content.

## Tool: `browser`

All browser interactions go through the `browser` tool with an `action` parameter.

## Actions

### navigate

Load a URL in the browser.

```
browser(action="navigate", url="https://example.com")
```

### snapshot

Return an accessibility-tree snapshot of the current page. Use this to understand page structure and find element references for click/type actions.

```
browser(action="snapshot")
```

The snapshot returns a text representation of the DOM with element references (e.g., `[ref=42]`). Use these references in `click` and `type` actions.

### screenshot

Capture a PNG screenshot of the current viewport.

```
browser(action="screenshot")
```

Use screenshots to visually verify page state or capture rendered content.

### click

Click on an element identified by its reference from a snapshot.

```
browser(action="click", ref=42)
```

Always take a snapshot first to find the correct element reference.

### type

Type text into an input field identified by its reference from a snapshot.

```
browser(action="type", ref=15, text="search query")
```

To submit a form after typing, add `submit=True`:
```
browser(action="type", ref=15, text="search query", submit=True)
```

### evaluate

Execute arbitrary JavaScript in the page context and return the result.

```
browser(action="evaluate", expression="document.title")
```

Use for extracting data, scrolling, or any DOM manipulation:
```
browser(action="evaluate", expression="window.scrollTo(0, document.body.scrollHeight)")
```

### wait

Wait for a specified number of seconds before proceeding.

```
browser(action="wait", seconds=2)
```

Use after navigation or clicks to allow dynamic content to load.

## Typical Workflow

1. **Navigate** to the target URL
2. **Snapshot** to get the accessibility tree and element references
3. **Click** or **type** to interact with elements
4. **Wait** if dynamic content needs time to load
5. **Snapshot** or **screenshot** to verify the result
6. **Evaluate** JavaScript for advanced extraction or interaction

## Tips

- Always snapshot before clicking or typing to get fresh element references.
- After navigation, wait briefly if the page has dynamic content.
- Use evaluate for scroll, extracting `innerText`, or running custom JS.
- For pages behind login, navigate to the login page first, then type credentials and submit.
- If an element is not visible in the snapshot, try scrolling with evaluate before retrying.
