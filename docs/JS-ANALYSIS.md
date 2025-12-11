# JavaScript Code Analysis - SBNC Photo Gallery

## Summary

| File | Lines | Functions | Hardcoded Values |
|------|-------|-----------|------------------|
| `sbnc-gallery-widget.js` | 469 | 14 | CDN URLs, gallery options, labels |
| `admin.js` | 75 | 4 | Keyboard shortcuts, toast timing |
| `gallery.html` (inline) | ~225 | 12 | Same as widget |
| `embed.html` (inline) | ~145 | 10 | Same as widget |
| `upload.html` (inline) | ~180 | 8 | Valid file types |
| `editor.html` (inline) | ~193 | 12 | None significant |
| **Total** | **~1,287** | **~60** | |

## Hardcoded Values Identified

### 1. File Upload Types (upload.html:343)
```javascript
const validTypes = ['image/jpeg', 'image/png', 'image/heic'];
```
**Impact**: Medium - new image formats would require code change
**Recommendation**: Move to config

### 2. CDN Library Versions (widget.js:47-52)
```javascript
'https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/...'
'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/...'
'https://cdn.jsdelivr.net/npm/jquery@3/dist/...'
```
**Impact**: Low - versions are stable, upgrades are intentional
**Recommendation**: Move to config for easier upgrades

### 3. Gallery Display Options (widget.js:420-438)
```javascript
thumbnailHeight: 180,
thumbnailGutterWidth: 8,
galleryMaxRows: 20,
```
**Impact**: Low - aesthetic preferences
**Recommendation**: Move to config for customization

### 4. UI Labels/Strings
```javascript
'SBNC Photo Gallery'
'Browse photos from Santa Barbara Newcomers Club events'
'Browse Events', 'Event Photos', 'Member Photos'
'Find Member', 'Activity', 'Event', 'Year'
```
**Impact**: Low - branding changes are rare
**Recommendation**: Optional config, or leave hardcoded

### 5. Keyboard Shortcuts (admin.js:59-63)
```javascript
'A' -> Approve
'R' -> Reject
'→' -> Next
'←' -> Previous
```
**Impact**: Very low - standard shortcuts
**Recommendation**: Leave hardcoded

## What's NOT Hardcoded (Good Design)

- **Members list** - Fetched from `/api/members.json`
- **Activities list** - Fetched from `/api/activities.json`
- **Events list** - Fetched from `/api/events.json`
- **Years** - Dynamically extracted from event dates
- **API base URL** - Auto-detected or configurable

## Recommended Config Structure

```javascript
// /api/config.json
{
  "gallery": {
    "title": "SBNC Photo Gallery",
    "subtitle": "Browse photos from Santa Barbara Newcomers Club events",
    "thumbnailHeight": 180,
    "maxRows": 20
  },
  "upload": {
    "validTypes": ["image/jpeg", "image/png", "image/heic", "image/heif"],
    "maxFileSize": 20971520
  },
  "libraries": {
    "jquery": "https://cdn.jsdelivr.net/npm/jquery@3/dist/jquery.min.js",
    "nanogallery2Js": "https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/jquery.nanogallery2.min.js",
    "nanogallery2Css": "https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/css/nanogallery2.min.css",
    "select2Js": "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js",
    "select2Css": "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css"
  },
  "labels": {
    "findMember": "Find Member",
    "activity": "Activity",
    "event": "Event",
    "year": "Year",
    "clearAll": "Clear",
    "browseEvents": "Browse Events",
    "eventPhotos": "Event Photos",
    "memberPhotos": "Member Photos",
    "activityEvents": "Activity Events"
  }
}
```

## Maintenance Difficulty Assessment

| Task | Difficulty | Where to Change |
|------|------------|-----------------|
| Add new image format | Easy | Config file |
| Change gallery layout | Easy | Config or nanogallery2 options |
| Update library version | Easy | Config file |
| Change labels/branding | Easy | Config file |
| Add new filter type | Medium | JS code + API |
| Change face recognition threshold | Easy | Python config |
| Add new photo status | Medium | Python + JS + DB |

## Skill Level Required

**To maintain**: Intermediate JavaScript
- Comfortable with DOM manipulation
- Understands async/fetch
- Can read jQuery syntax
- Familiar with JSON APIs

**To extend**: Intermediate+ JavaScript
- Can add new event handlers
- Understands module patterns
- Can debug with browser DevTools
