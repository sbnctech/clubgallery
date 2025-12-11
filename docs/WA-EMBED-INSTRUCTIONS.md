# Embedding SBNC Photo Gallery in Wild Apricot

## Option 1: JavaScript Widget (Recommended)

Add this to a Wild Apricot page using the HTML widget gadget:

```html
<div id="sbnc-gallery"></div>
<script src="https://mail.sbnewcomers.org/gallery/widget.js"></script>
```

That's it! The widget will:

- Load all required libraries (jQuery, nanogallery2, Select2)
- Inject its own CSS (scoped to avoid conflicts)
- Fetch photo data from the API
- Render the gallery with filters

### Customization Options

```html
<div id="my-custom-gallery"></div>
<script>
  window.SBNC_GALLERY_CONFIG = {
    container: '#my-custom-gallery',  // Custom container ID
    showFilters: true,                // Show/hide filter bar
    showHeader: false,                // Hide the header
    apiBase: 'https://mail.sbnewcomers.org'  // API server
  };
</script>
<script src="https://mail.sbnewcomers.org/gallery/widget.js"></script>
```

### Filter to Specific Content

Pre-filter to show only specific content:

```html
<div id="sbnc-gallery"></div>
<script>
  window.SBNC_GALLERY_CONFIG = {
    showFilters: false  // Hide filters for a cleaner look
  };
</script>
<script src="https://mail.sbnewcomers.org/gallery/widget.js"></script>
<script>
  // After widget loads, filter to Happy Hikers only
  setTimeout(function() {
    document.querySelector('#sbnc-filter-activity').value = 'Happy Hikers';
    window.SBNCGallery.applyFilters();
  }, 1000);
</script>
```

---

## Option 2: iframe Embed

If you prefer complete isolation from WA styles:

```html
<iframe
  src="https://mail.sbnewcomers.org/gallery/embed"
  width="100%"
  height="800px"
  frameborder="0"
  style="border: none;">
</iframe>
```

### Auto-resize iframe

The embed page sends height messages. Add this to auto-resize:

```html
<iframe id="gallery-frame" src="https://mail.sbnewcomers.org/gallery/embed"
        width="100%" frameborder="0" style="border: none;"></iframe>
<script>
  window.addEventListener('message', function(e) {
    if (e.data.type === 'sbnc-gallery-height') {
      document.getElementById('gallery-frame').style.height = e.data.height + 'px';
    }
  });
</script>
```

---

## Wild Apricot Page Setup

1. **Create a new page** in WA admin
2. **Add Content → Gadgets → HTML**
3. **Paste** one of the embed codes above
4. **Save** the page

### Recommended WA Page Settings

- **Page Layout**: Full width (no sidebar)
- **Access**: Members only (for members_only photos) or Public (for public photos only)
- **Navigation**: Add to main menu as "Photo Gallery"

---

## Troubleshooting

### Gallery not loading

- Check browser console for errors
- Verify `https://mail.sbnewcomers.org` is accessible
- Check CORS headers are configured on the server

### Photos not appearing

- Verify photos have been approved (status = 'members_only' or 'public')
- Check the API endpoint: `https://mail.sbnewcomers.org/api/gallery.json`

### Styles look wrong

- The widget uses scoped CSS with `.sbnc-` prefixes
- If WA styles interfere, try the iframe option instead

---

## API Endpoints

The gallery uses these JSON APIs:

| Endpoint | Description |
|----------|-------------|
| `/api/gallery.json` | Photos/events (supports filters) |
| `/api/events.json` | List of events with photo counts |
| `/api/members.json` | Members who appear in photos |
| `/api/activities.json` | Activity groups |

### Query Parameters for gallery.json

- `?member=12345` - Photos of a specific member
- `?event=67890` - Photos from a specific event
- `?activity=Happy%20Hikers` - Events in an activity
- `?year=2024` - Events from a year
