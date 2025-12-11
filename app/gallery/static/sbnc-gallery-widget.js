/**
 * SBNC Photo Gallery Widget
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * This file contains the embeddable photo gallery widget for Santa Barbara
 * Newcomers Club. It is designed to be embedded in Wild Apricot pages.
 *
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  CODE ORGANIZATION - READ THIS FIRST                                   │
 * ├─────────────────────────────────────────────────────────────────────────┤
 * │                                                                         │
 * │  This code has TWO distinct parts:                                     │
 * │                                                                         │
 * │  1. EXTERNAL LIBRARIES (loaded from CDN - we don't maintain these)     │
 * │     - jQuery: DOM manipulation                                         │
 * │     - nanogallery2: Photo gallery display and lightbox                 │
 * │     - Select2: Enhanced dropdown for member search                     │
 * │                                                                         │
 * │  2. SBNC SHIM (this file - we maintain this code)                      │
 * │     Organized into three broad categories:                             │
 * │                                                                         │
 * │     A. SETTINGS (Sections 1-2) - What to show and how it looks         │
 * │        ├── Configuration: Default values, feature flags                │
 * │        └── CSS Overrides: Styling to match WA theme                    │
 * │                                                                         │
 * │     B. DATA LAYER (Section 3) - Where data comes from                  │
 * │        └── API Integration: Fetches members, events, photos            │
 * │                                                                         │
 * │     C. UI LAYER (Sections 4-6) - How it all works together             │
 * │        ├── Widget Integration: HTML, filters, gallery rendering        │
 * │        ├── Public API: External access points                          │
 * │        └── Initialization: Startup sequence                            │
 * │                                                                         │
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 *
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  CODE ANALYSIS - Maintenance Guide                                     │
 * ├─────────────────────────────────────────────────────────────────────────┤
 * │                                                                         │
 * │  SECTION BREAKDOWN (% of code, dependencies, stability)                │
 * │                                                                         │
 * │  ┌─────────────────────────────────────────────────────────────────┐   │
 * │  │ CATEGORY A: SETTINGS (~25% of code)                             │   │
 * │  │ Overall stability: HIGH - Changes rarely needed                 │   │
 * │  ├─────────────────────────────────────────────────────────────────┤   │
 * │  │                                                                 │   │
 * │  │ Section 1: Configuration                                        │   │
 * │  │   Lines: ~50 (~4%)                                              │   │
 * │  │   Dependencies: None                                            │   │
 * │  │   Stability: HIGH                                               │   │
 * │  │   Break risk: LOW - Only breaks if server URL changes           │   │
 * │  │   Reason to change: Server migration, new features              │   │
 * │  │                                                                 │   │
 * │  │ Section 2: CSS Overrides                                        │   │
 * │  │   Lines: ~220 (~19%)                                            │   │
 * │  │   Dependencies: None (pure CSS)                                 │   │
 * │  │   Stability: HIGH                                               │   │
 * │  │   Break risk: LOW - Visual only, won't break functionality      │   │
 * │  │   Reason to change: WA theme update, design refresh             │   │
 * │  │                                                                 │   │
 * │  └─────────────────────────────────────────────────────────────────┘   │
 * │                                                                         │
 * │  ┌─────────────────────────────────────────────────────────────────┐   │
 * │  │ CATEGORY B: DATA LAYER (~10% of code)                           │   │
 * │  │ Overall stability: MEDIUM - May need updates with backend       │   │
 * │  ├─────────────────────────────────────────────────────────────────┤   │
 * │  │                                                                 │   │
 * │  │ Section 3: API Integration                                      │   │
 * │  │   Lines: ~100 (~9%)                                             │   │
 * │  │   Dependencies: fetch API (browser built-in)                    │   │
 * │  │   Stability: MEDIUM                                             │   │
 * │  │   Break risk: MEDIUM - Breaks if API changes                    │   │
 * │  │   Reason to change: Backend API changes, new data fields        │   │
 * │  │   Watch for: Endpoint URL changes, response format changes      │   │
 * │  │                                                                 │   │
 * │  └─────────────────────────────────────────────────────────────────┘   │
 * │                                                                         │
 * │  ┌─────────────────────────────────────────────────────────────────┐   │
 * │  │ CATEGORY C: UI LAYER (~65% of code)                             │   │
 * │  │ Overall stability: MEDIUM - Core functionality lives here       │   │
 * │  ├─────────────────────────────────────────────────────────────────┤   │
 * │  │                                                                 │   │
 * │  │ Section 4: Widget Integration                                   │   │
 * │  │   Lines: ~500 (~43%)                                            │   │
 * │  │   Dependencies: jQuery, nanogallery2, Select2                   │   │
 * │  │   Stability: MEDIUM                                             │   │
 * │  │   Break risk: MEDIUM-HIGH                                       │   │
 * │  │   Reason to change: New filters, layout changes, lib updates    │   │
 * │  │   Watch for: Library version updates, API changes               │   │
 * │  │   Sub-sections:                                                 │   │
 * │  │     - Dependency Loading: LOW risk (stable CDN URLs)            │   │
 * │  │     - HTML Construction: LOW risk (pure string templates)       │   │
 * │  │     - Filter Logic: MEDIUM risk (ties to data & UI)             │   │
 * │  │     - Gallery Rendering: MEDIUM-HIGH (nanogallery2 dependent)   │   │
 * │  │                                                                 │   │
 * │  │ Section 5: Public API                                           │   │
 * │  │   Lines: ~30 (~3%)                                              │   │
 * │  │   Dependencies: Internal functions only                         │   │
 * │  │   Stability: HIGH                                               │   │
 * │  │   Break risk: LOW - Simple function exports                     │   │
 * │  │   Reason to change: Adding new public methods                   │   │
 * │  │   IMPORTANT: Don't remove methods (external code may use them)  │   │
 * │  │                                                                 │   │
 * │  │ Section 6: Initialization                                       │   │
 * │  │   Lines: ~40 (~3%)                                              │   │
 * │  │   Dependencies: All other sections                              │   │
 * │  │   Stability: HIGH                                               │   │
 * │  │   Break risk: LOW - Simple orchestration                        │   │
 * │  │   Reason to change: New startup steps, loading order changes    │   │
 * │  │                                                                 │   │
 * │  └─────────────────────────────────────────────────────────────────┘   │
 * │                                                                         │
 * │  EXTERNAL LIBRARY RISK ASSESSMENT                                      │
 * │  ─────────────────────────────────────────────────────────────────────  │
 * │                                                                         │
 * │  jQuery (v3.x)                                                         │
 * │    Risk: LOW - Extremely stable, rarely has breaking changes           │
 * │    Pinned to: Major version 3 (auto-updates minors)                    │
 * │                                                                         │
 * │  nanogallery2 (v3.x)                                                   │
 * │    Risk: MEDIUM - Gallery libs occasionally change options             │
 * │    Pinned to: Major version 3                                          │
 * │    Watch for: Options renamed, deprecated features                     │
 * │    Mitigation: Test after any version update                           │
 * │                                                                         │
 * │  Select2 (v4.1.x)                                                      │
 * │    Risk: LOW - Mature library, stable API                              │
 * │    Pinned to: 4.1.0-rc.0 (release candidate, but very stable)          │
 * │                                                                         │
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 * @version 1.0.0
 * @author SBNC Technology Team
 */

(function() {
    'use strict';

/* ╔═══════════════════════════════════════════════════════════════════════════╗
   ║                                                                           ║
   ║                     EXTERNAL LIBRARIES DOCUMENTATION                      ║
   ║                                                                           ║
   ║  These libraries are loaded from CDN. We DO NOT maintain this code.      ║
   ║  Documentation links for reference when troubleshooting:                 ║
   ║                                                                           ║
   ║  jQuery (v3.x)                                                           ║
   ║  ─────────────────────────────────────────────────────────────────────   ║
   ║  Purpose: DOM manipulation, event handling                               ║
   ║  Docs: https://api.jquery.com/                                           ║
   ║  CDN: https://cdn.jsdelivr.net/npm/jquery@3/                             ║
   ║                                                                           ║
   ║  nanogallery2 (v3.x)                                                     ║
   ║  ─────────────────────────────────────────────────────────────────────   ║
   ║  Purpose: Photo grid display, lightbox viewer, album navigation          ║
   ║  Docs: https://nanogallery2.nanostudio.org/                              ║
   ║  CDN: https://cdn.jsdelivr.net/npm/nanogallery2@3/                       ║
   ║  Key methods we use:                                                     ║
   ║    - $(selector).nanogallery2(options) - Initialize gallery              ║
   ║    - $(selector).nanogallery2('destroy') - Clean up before reinit        ║
   ║  Data format: Array of {src, srct, title, album} objects                 ║
   ║                                                                           ║
   ║  Select2 (v4.1.x)                                                        ║
   ║  ─────────────────────────────────────────────────────────────────────   ║
   ║  Purpose: Searchable dropdown for member search                          ║
   ║  Docs: https://select2.org/                                              ║
   ║  CDN: https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/                   ║
   ║  Key methods we use:                                                     ║
   ║    - $(selector).select2(options) - Initialize searchable dropdown       ║
   ║    - templateResult: Custom formatting for dropdown options              ║
   ║                                                                           ║
   ╚═══════════════════════════════════════════════════════════════════════════╝ */


/* ╔═══════════════════════════════════════════════════════════════════════════╗
   ║                                                                           ║
   ║                         SBNC SHIM - START                                 ║
   ║                                                                           ║
   ║  Everything below this line is SBNC-specific code that we maintain.      ║
   ║                                                                           ║
   ╚═══════════════════════════════════════════════════════════════════════════╝ */


// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║  CATEGORY A: SETTINGS                                                     ║
// ║  What to show and how it looks                                            ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// ═══════════════════════════════════════════════════════════════════════════
// SECTION 1: CONFIGURATION                                    [~4% of code]
// ═══════════════════════════════════════════════════════════════════════════
// Dependencies: None
// Stability: HIGH | Break risk: LOW
//
// This section contains SBNC-specific default settings.
// These can be overridden by setting window.SBNC_GALLERY_CONFIG before loading.
//
// WHAT YOU MIGHT NEED TO CHANGE:
// - API endpoint URLs if server location changes
// - Default filter settings
// - Feature flags (showFilters, showHeader)
// ═══════════════════════════════════════════════════════════════════════════

    /**
     * @typedef {Object} GalleryConfig
     * @property {string} container - CSS selector for gallery container
     * @property {string} apiBase - Base URL for SBNC API endpoints
     * @property {string} photosBase - Base path for photo file URLs
     * @property {boolean} showFilters - Whether to show filter controls
     * @property {boolean} showHeader - Whether to show gallery header
     * @property {string} defaultView - Initial view mode ('events' or 'photos')
     */

    /**
     * Default configuration values.
     * Override by setting window.SBNC_GALLERY_CONFIG before this script loads.
     *
     * @type {GalleryConfig}
     * @constant
     */
    const DEFAULT_CONFIG = {
        container: '#sbnc-gallery',      // Where to render the gallery
        apiBase: '',                      // Auto-detected from script URL
        photosBase: '/photos',            // Path prefix for photo files
        showFilters: true,                // Show member/event/activity filters
        showHeader: true,                 // Show "SBNC Photo Gallery" header
        defaultView: 'events'             // Start by showing events (not individual photos)
    };

    /**
     * Remote configuration loaded from /api/config.json
     * This allows admin-configurable settings without code changes.
     * @type {Object|null}
     */
    let remoteConfig = null;

    /**
     * Merged configuration (defaults + remote + user overrides)
     * @type {GalleryConfig}
     */
    let CONFIG = Object.assign({}, DEFAULT_CONFIG, window.SBNC_GALLERY_CONFIG || {});

    // Auto-detect API base URL from script src if not explicitly set
    if (!CONFIG.apiBase) {
        CONFIG.apiBase = detectApiBase();
    }


// ═══════════════════════════════════════════════════════════════════════════
// SECTION 2: CSS OVERRIDE / THEME INTEGRATION                 [~19% of code]
// ═══════════════════════════════════════════════════════════════════════════
// Dependencies: None (pure CSS)
// Stability: HIGH | Break risk: LOW (visual only)
//
// This section contains CSS that styles the widget to match the SBNC/WA theme.
// All class names use the .sbnc- prefix to avoid conflicts with host pages.
//
// WHAT YOU MIGHT NEED TO CHANGE:
// - Colors to match WA theme updates (search for #2c5aa0, #d4a800)
// - Font sizes if design changes
// - Layout spacing/margins
// ═══════════════════════════════════════════════════════════════════════════

    /**
     * Injects widget CSS styles into the document.
     * Uses .sbnc-* scoped class names to avoid conflicts.
     *
     * COLOR MAPPING TO WA THEME:
     *   #2c5aa0 - WA primary blue (header, links, focus states)
     *   #d4a800 - WA secondary gold (not currently used, available for accents)
     *   #f8f9fa - Light gray background (filter bar)
     *   #333333 - Primary text color
     *   #666666 - Secondary/muted text
     *
     * @returns {void}
     */
    function injectStyles() {
        // Skip if already injected
        if (document.getElementById('sbnc-gallery-styles')) {
            return;
        }

        const css = `
/* ═══════════════════════════════════════════════════════════════════════════
   SBNC Gallery Widget Styles

   These styles override/extend the external library styles to match WA theme.
   ═══════════════════════════════════════════════════════════════════════════ */

/* --- Base Container --- */
.sbnc-gallery-widget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    color: #333;
    line-height: 1.5;
}

/* --- Header Styling --- */
.sbnc-gallery-header {
    padding: 15px 0;
    margin-bottom: 15px;
    border-bottom: 2px solid #2c5aa0;  /* WA primary blue */
}
.sbnc-gallery-header h2 {
    margin: 0;
    color: #2c5aa0;  /* WA primary blue */
    font-size: 24px;
    font-weight: 600;
}
.sbnc-gallery-header p {
    margin: 5px 0 0;
    color: #666;
    font-size: 14px;
}

/* --- Filter Bar --- */
.sbnc-filter-bar {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: flex-end;
    margin-bottom: 15px;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 8px;
}
.sbnc-filter-group {
    display: flex;
    flex-direction: column;
    min-width: 150px;
}
.sbnc-filter-group.sbnc-member-search {
    flex: 1;
    min-width: 200px;
    max-width: 300px;
}
.sbnc-filter-group label {
    font-size: 11px;
    color: #666;
    margin-bottom: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.sbnc-filter-group select {
    padding: 8px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
    background: white;
}
.sbnc-filter-group select:focus {
    outline: none;
    border-color: #2c5aa0;  /* WA primary blue */
    box-shadow: 0 0 0 2px rgba(44, 90, 160, 0.2);
}

/* --- Clear Button --- */
.sbnc-btn-clear {
    padding: 8px 16px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: background-color 0.2s;
}
.sbnc-btn-clear:hover {
    background: #f0f0f0;
}

/* --- Active Filter Tags --- */
.sbnc-active-filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 15px;
}
.sbnc-active-filters:empty {
    display: none;
}
.sbnc-filter-tag {
    display: inline-flex;
    align-items: center;
    background: #e3f2fd;
    color: #1565c0;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 13px;
}
.sbnc-filter-tag .remove {
    margin-left: 8px;
    cursor: pointer;
    font-weight: bold;
    opacity: 0.7;
    transition: opacity 0.2s;
}
.sbnc-filter-tag .remove:hover {
    opacity: 1;
}
.sbnc-filter-tag.person {
    background: #fce4ec;
    color: #c2185b;
}
.sbnc-filter-tag.event {
    background: #e8f5e9;
    color: #2e7d32;
}

/* --- Results Bar --- */
.sbnc-results-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    font-size: 14px;
    color: #666;
}
.sbnc-results-bar strong {
    color: #333;
}
.sbnc-view-mode {
    background: #f0f0f0;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
}

/* --- Gallery Content Area --- */
.sbnc-gallery-content {
    min-height: 200px;
}
.sbnc-loading {
    text-align: center;
    padding: 40px;
    color: #888;
}
.sbnc-error {
    text-align: center;
    padding: 40px;
    color: #c00;
    background: #fee;
    border-radius: 8px;
}

/* --- Select2 Library Overrides --- */
/* These adjust the Select2 dropdown to match our theme */
.sbnc-gallery-widget .select2-container {
    width: 100% !important;
}
.sbnc-gallery-widget .select2-container--default .select2-selection--single {
    height: 36px;
    border: 1px solid #ddd;
    border-radius: 4px;
}
.sbnc-gallery-widget .select2-container--default .select2-selection--single .select2-selection__rendered {
    line-height: 34px;
}

/* --- Member Search Dropdown Option Styling --- */
.sbnc-member-option {
    display: flex;
    align-items: center;
    gap: 8px;
}
.sbnc-member-option img {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    object-fit: cover;
}

/* --- Responsive Layout --- */
@media (max-width: 768px) {
    .sbnc-filter-bar {
        flex-direction: column;
    }
    .sbnc-filter-group {
        width: 100%;
        min-width: unset !important;
        max-width: none !important;
    }
}
        `;

        const style = document.createElement('style');
        style.id = 'sbnc-gallery-styles';
        style.textContent = css;
        document.head.appendChild(style);
    }


// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║  CATEGORY B: DATA LAYER                                                   ║
// ║  Where data comes from                                                    ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// ═══════════════════════════════════════════════════════════════════════════
// SECTION 3: EVENT DATA ACCESS (API Integration)               [~9% of code]
// ═══════════════════════════════════════════════════════════════════════════
// Dependencies: fetch API (browser built-in)
// Stability: MEDIUM | Break risk: MEDIUM (breaks if API changes)
//
// This section handles all communication with the SBNC backend API.
// Data is fetched from JSON endpoints and stored in module-level variables.
//
// API ENDPOINTS (relative to CONFIG.apiBase):
//   /api/config.json    - Remote configuration (gallery options, labels)
//   /api/members.json   - Members who appear in photos
//   /api/activities.json - Activity groups (Happy Hikers, Golf, etc.)
//   /api/events.json    - Events with photos
//   /api/gallery.json   - Photo data for nanogallery2 (accepts filter params)
//
// WHAT YOU MIGHT NEED TO CHANGE:
// - API endpoint paths if backend routes change
// - Data transformation if API response format changes
// ═══════════════════════════════════════════════════════════════════════════

    // --- Data Storage ---
    /** @type {Array} Members who appear in photos */
    let members = [];

    /** @type {Array} Activity groups (Happy Hikers, Golf, Wine Club, etc.) */
    let activities = [];

    /** @type {Array} Events that have photos */
    let events = [];

    /** @type {Object} Current filter state */
    let currentFilters = { member: null, activity: null, event: null, year: null };

    /**
     * Detects API base URL from the script's src attribute.
     * Allows the widget to work without explicit configuration.
     *
     * @returns {string} Detected base URL or empty string
     * @example
     * // If loaded from https://mail.sbnewcomers.org/gallery/sbnc-gallery-widget.js
     * // Returns: 'https://mail.sbnewcomers.org'
     */
    function detectApiBase() {
        const scripts = document.getElementsByTagName('script');
        for (let s of scripts) {
            if (s.src && s.src.includes('sbnc-gallery-widget')) {
                return s.src.replace(/\/gallery\/.*$/, '');
            }
        }
        return '';
    }

    /**
     * Loads remote configuration from the API.
     * This allows admins to change gallery settings without code changes.
     *
     * @returns {Promise<void>}
     */
    async function loadRemoteConfig() {
        try {
            const response = await fetch(CONFIG.apiBase + '/api/config.json');
            if (response.ok) {
                remoteConfig = await response.json();
            }
        } catch (error) {
            // Config is optional - continue with defaults
            console.log('SBNC Gallery: Using default config (remote config not available)');
        }
    }

    /**
     * Gets a configuration value, checking remote config first.
     *
     * @param {string} path - Dot-notation path (e.g., 'gallery.thumbnailHeight')
     * @param {*} defaultValue - Fallback value
     * @returns {*} Configuration value
     */
    function getConfigValue(path, defaultValue) {
        const parts = path.split('.');

        // Try remote config first
        if (remoteConfig) {
            let value = remoteConfig;
            for (const part of parts) {
                if (value && typeof value === 'object' && part in value) {
                    value = value[part];
                } else {
                    value = undefined;
                    break;
                }
            }
            if (value !== undefined) return value;
        }

        return defaultValue;
    }

    /**
     * Loads all data needed for the gallery from the API.
     * Fetches members, activities, and events in parallel.
     *
     * @returns {Promise<void>}
     * @throws {Error} If all API calls fail
     */
    async function loadData() {
        try {
            const [membersData, activitiesData, eventsData] = await Promise.all([
                fetch(CONFIG.apiBase + '/api/members.json').then(r => r.ok ? r.json() : []).catch(() => []),
                fetch(CONFIG.apiBase + '/api/activities.json').then(r => r.ok ? r.json() : []).catch(() => []),
                fetch(CONFIG.apiBase + '/api/events.json').then(r => r.ok ? r.json() : []).catch(() => [])
            ]);

            members = membersData;
            activities = activitiesData;
            events = eventsData;

        } catch (error) {
            console.error('SBNC Gallery: Failed to load data:', error);
            throw error;
        }
    }


// ═══════════════════════════════════════════════════════════════════════════
// SECTION 4: WIDGET INTEGRATION (Connects SBNC data to libraries)
// CATEGORY C: UI LAYER | ~43% of code | Dependencies: jQuery, nanogallery2, Select2
// Risk: MEDIUM-HIGH | Breaks if: Library APIs change, HTML structure assumptions fail
// ═══════════════════════════════════════════════════════════════════════════
//
// This section contains the "glue" code that:
// - Builds the HTML structure
// - Populates filter dropdowns with SBNC data
// - Initializes nanogallery2 and Select2 with our settings
// - Handles filter changes and gallery updates
//
// WHAT YOU MIGHT NEED TO CHANGE:
// - HTML structure if layout redesign
// - Filter logic if new filter types added
// - Gallery options if display requirements change
// ═══════════════════════════════════════════════════════════════════════════

    // --- Utility Functions ---

    /**
     * Escapes HTML special characters to prevent XSS.
     * @param {string} str - String to escape
     * @returns {string} Safe HTML string
     */
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // --- Dependency Loading ---

    /**
     * Loads external library dependencies (jQuery, nanogallery2, Select2).
     * Checks if already loaded to avoid duplicates.
     *
     * @param {Function} callback - Called when all dependencies ready
     */
    function loadDependencies(callback) {
        const dependencies = [
            {
                type: 'css',
                url: getConfigValue('libraries.nanogallery2Css',
                    'https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/css/nanogallery2.min.css')
            },
            {
                type: 'css',
                url: getConfigValue('libraries.select2Css',
                    'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css')
            },
            {
                type: 'js',
                url: getConfigValue('libraries.jquery',
                    'https://cdn.jsdelivr.net/npm/jquery@3/dist/jquery.min.js'),
                check: () => window.jQuery
            },
            {
                type: 'js',
                url: getConfigValue('libraries.nanogallery2Js',
                    'https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/jquery.nanogallery2.min.js'),
                check: () => window.jQuery && window.jQuery.fn.nanogallery2
            },
            {
                type: 'js',
                url: getConfigValue('libraries.select2Js',
                    'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js'),
                check: () => window.jQuery && window.jQuery.fn.select2
            }
        ];

        let loaded = 0;
        const total = dependencies.length;

        function onLoad() {
            loaded++;
            if (loaded === total) callback();
        }

        dependencies.forEach(dep => {
            // Skip if already loaded
            if (dep.check && dep.check()) {
                onLoad();
                return;
            }

            if (dep.type === 'css') {
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = dep.url;
                link.onload = onLoad;
                link.onerror = () => {
                    console.error('SBNC Gallery: Failed to load CSS:', dep.url);
                    onLoad(); // Continue anyway
                };
                document.head.appendChild(link);
            } else {
                const script = document.createElement('script');
                script.src = dep.url;
                script.onload = onLoad;
                script.onerror = () => {
                    console.error('SBNC Gallery: Failed to load JS:', dep.url);
                    onLoad(); // Continue anyway
                };
                document.head.appendChild(script);
            }
        });
    }

    // --- HTML Construction ---

    /**
     * Builds and inserts the widget HTML structure.
     * Creates header, filter bar, results display, and gallery container.
     *
     * @returns {boolean} True if successful, false if container not found
     */
    function buildWidget() {
        const container = document.querySelector(CONFIG.container);
        if (!container) {
            console.error('SBNC Gallery: Container not found:', CONFIG.container);
            return false;
        }

        // Get labels from config (allows admin customization)
        const labels = {
            title: getConfigValue('labels.title', 'SBNC Photo Gallery'),
            subtitle: getConfigValue('labels.subtitle', 'Browse photos from Santa Barbara Newcomers Club events'),
            findMember: getConfigValue('labels.findMember', 'Find Member'),
            activity: getConfigValue('labels.activity', 'Activity'),
            event: getConfigValue('labels.event', 'Event'),
            year: getConfigValue('labels.year', 'Year'),
            clear: getConfigValue('labels.clear', 'Clear'),
            loading: getConfigValue('labels.loading', 'Loading...')
        };

        // Get presentation settings (which elements to show)
        const showHeader = getConfigValue('presentation.header.show', true) && CONFIG.showHeader;
        const showSubtitle = getConfigValue('presentation.header.showSubtitle', true);
        const filters = {
            member: getConfigValue('presentation.filters.showMemberSearch', true),
            activity: getConfigValue('presentation.filters.showActivityFilter', true),
            event: getConfigValue('presentation.filters.showEventFilter', true),
            year: getConfigValue('presentation.filters.showYearFilter', true)
        };
        const anyFiltersVisible = filters.member || filters.activity || filters.event || filters.year;

        let html = '<div class="sbnc-gallery-widget">';

        // Header (optional)
        if (showHeader) {
            html += `
                <div class="sbnc-gallery-header">
                    <h2>${escapeHtml(labels.title)}</h2>
                    ${showSubtitle ? `<p>${escapeHtml(labels.subtitle)}</p>` : ''}
                </div>
            `;
        }

        // Filter bar (optional, respects individual filter visibility)
        if (CONFIG.showFilters && anyFiltersVisible) {
            html += '<div class="sbnc-filter-bar">';

            if (filters.member) {
                html += `
                    <div class="sbnc-filter-group sbnc-member-search">
                        <label>${escapeHtml(labels.findMember)}</label>
                        <select id="sbnc-member-search"><option value="">Search members...</option></select>
                    </div>
                `;
            }

            if (filters.activity) {
                html += `
                    <div class="sbnc-filter-group">
                        <label>${escapeHtml(labels.activity)}</label>
                        <select id="sbnc-filter-activity"><option value="">All Activities</option></select>
                    </div>
                `;
            }

            if (filters.event) {
                html += `
                    <div class="sbnc-filter-group">
                        <label>${escapeHtml(labels.event)}</label>
                        <select id="sbnc-filter-event"><option value="">All Events</option></select>
                    </div>
                `;
            }

            if (filters.year) {
                html += `
                    <div class="sbnc-filter-group">
                        <label>${escapeHtml(labels.year)}</label>
                        <select id="sbnc-filter-year"><option value="">All Years</option></select>
                    </div>
                `;
            }

            html += `
                    <button class="sbnc-btn-clear" onclick="window.SBNCGallery.clearFilters()">${escapeHtml(labels.clear)}</button>
                </div>
                <div class="sbnc-active-filters" id="sbnc-active-filters"></div>
            `;
        }

        // Results bar and gallery container
        html += `
            <div class="sbnc-results-bar">
                <div id="sbnc-results-count">${escapeHtml(labels.loading)}</div>
                <div class="sbnc-view-mode" id="sbnc-view-mode">Browse Events</div>
            </div>
            <div class="sbnc-gallery-content" id="sbnc-gallery-content">
                <div class="sbnc-loading">${escapeHtml(labels.loading)}</div>
            </div>
        </div>`;

        container.innerHTML = html;
        return true;
    }

    // --- Filter Logic ---

    /**
     * Populates filter dropdowns with data from the API.
     * - Activities: Sorted and filtered per admin config
     * - Years: Extracted from event dates
     * - Events: Grouped by year with optgroups
     * - Members: Initialized with Select2 for search
     */
    function populateFilters() {
        const $ = window.jQuery;

        // Get activity display settings from admin config
        const hiddenActivities = getConfigValue('presentation.activityGroups.hidden', []);
        const customNames = getConfigValue('presentation.activityGroups.customNames', {});
        const displayOrder = getConfigValue('presentation.activityGroups.displayOrder', []);

        // Filter out hidden activities and apply custom sort order
        let visibleActivities = activities.filter(a => !hiddenActivities.includes(a.id));

        if (displayOrder.length > 0) {
            visibleActivities.sort((a, b) => {
                const indexA = displayOrder.indexOf(a.id);
                const indexB = displayOrder.indexOf(b.id);
                if (indexA === -1 && indexB === -1) return 0;
                if (indexA === -1) return 1;
                if (indexB === -1) return -1;
                return indexA - indexB;
            });
        }

        // Populate activities dropdown
        visibleActivities.forEach(a => {
            const displayName = customNames[a.id] || a.name;
            $('#sbnc-filter-activity').append(
                `<option value="${escapeHtml(a.id)}">${escapeHtml(displayName)}</option>`
            );
        });

        // Extract and populate years dropdown
        const years = [...new Set(
            events
                .map(e => e.date?.substring(0, 4))
                .filter(Boolean)
        )].sort().reverse();

        years.forEach(y => {
            $('#sbnc-filter-year').append(`<option value="${y}">${y}</option>`);
        });

        // Populate events dropdown (grouped by year)
        let currentYear = null;
        events.forEach(e => {
            const year = e.date?.substring(0, 4);
            if (year && year !== currentYear) {
                $('#sbnc-filter-event').append(`<optgroup label="${year}">`);
                currentYear = year;
            }
            $('#sbnc-filter-event').append(
                `<option value="${escapeHtml(e.id)}">${escapeHtml(e.name)}</option>`
            );
        });

        // Initialize Select2 for member search
        if ($('#sbnc-member-search').length) {
            $('#sbnc-member-search').select2({
                placeholder: 'Search members...',
                allowClear: true,
                minimumInputLength: 1,
                data: members.map(m => ({
                    id: m.id,
                    text: m.name,
                    photoCount: m.photoCount,
                    thumb: m.thumb
                })),
                templateResult: formatMemberOption
            });
        }

        // Bind change events
        $('#sbnc-member-search, #sbnc-filter-activity, #sbnc-filter-event, #sbnc-filter-year')
            .on('change', applyFilters);

        // Apply any default filters from config
        applyDefaultFilters();
    }

    /**
     * Applies default filters on initial load (from admin config).
     */
    function applyDefaultFilters() {
        const $ = window.jQuery;

        const defaultActivity = getConfigValue('presentation.defaultView.activity', null);
        const defaultYear = getConfigValue('presentation.defaultView.year', null);

        if (defaultActivity && $('#sbnc-filter-activity').length) {
            $('#sbnc-filter-activity').val(defaultActivity);
            currentFilters.activity = defaultActivity;
        }

        if (defaultYear && $('#sbnc-filter-year').length) {
            $('#sbnc-filter-year').val(defaultYear);
            currentFilters.year = defaultYear;
        }

        if (defaultActivity || defaultYear) {
            updateActiveFilters();
        }
    }

    /**
     * Formats member option in Select2 dropdown (shows photo + name).
     */
    function formatMemberOption(member) {
        if (!member.id) return member.text;

        const $ = window.jQuery;
        const thumbUrl = member.thumb || CONFIG.apiBase + '/static/default-avatar.png';

        return $(`
            <div class="sbnc-member-option">
                <img src="${escapeHtml(thumbUrl)}" alt="">
                <div>
                    <strong>${escapeHtml(member.text)}</strong><br>
                    <small>${member.photoCount} photos</small>
                </div>
            </div>
        `);
    }

    /**
     * Reads current filter values and refreshes the gallery.
     */
    function applyFilters() {
        const $ = window.jQuery;

        currentFilters = {
            member: $('#sbnc-member-search').val() || null,
            activity: $('#sbnc-filter-activity').val() || null,
            event: $('#sbnc-filter-event').val() || null,
            year: $('#sbnc-filter-year').val() || null
        };

        updateActiveFilters();
        loadGallery();
    }

    /**
     * Updates the active filter tags display.
     */
    function updateActiveFilters() {
        const $ = window.jQuery;
        const $container = $('#sbnc-active-filters').empty();

        if (currentFilters.member) {
            const member = members.find(x => x.id === currentFilters.member);
            if (member) {
                $container.append(`
                    <span class="sbnc-filter-tag person">
                        ${escapeHtml(member.name)}
                        <span class="remove" onclick="window.SBNCGallery.removeFilter('member')">×</span>
                    </span>
                `);
            }
        }

        if (currentFilters.activity) {
            const activity = activities.find(x => x.id === currentFilters.activity);
            const name = activity ? activity.name : currentFilters.activity;
            $container.append(`
                <span class="sbnc-filter-tag">
                    ${escapeHtml(name)}
                    <span class="remove" onclick="window.SBNCGallery.removeFilter('activity')">×</span>
                </span>
            `);
        }

        if (currentFilters.event) {
            const event = events.find(x => x.id === currentFilters.event);
            if (event) {
                $container.append(`
                    <span class="sbnc-filter-tag event">
                        ${escapeHtml(event.name)}
                        <span class="remove" onclick="window.SBNCGallery.removeFilter('event')">×</span>
                    </span>
                `);
            }
        }

        if (currentFilters.year) {
            $container.append(`
                <span class="sbnc-filter-tag">
                    ${escapeHtml(currentFilters.year)}
                    <span class="remove" onclick="window.SBNCGallery.removeFilter('year')">×</span>
                </span>
            `);
        }
    }

    /**
     * Removes a specific filter and refreshes gallery.
     * @param {string} filterType - 'member', 'activity', 'event', or 'year'
     */
    function removeFilter(filterType) {
        const $ = window.jQuery;

        currentFilters[filterType] = null;

        if (filterType === 'member') {
            $('#sbnc-member-search').val(null).trigger('change.select2');
        } else {
            $(`#sbnc-filter-${filterType}`).val('');
        }

        applyFilters();
    }

    /**
     * Clears all filters and resets to default view.
     */
    function clearFilters() {
        const $ = window.jQuery;

        currentFilters = { member: null, activity: null, event: null, year: null };

        $('#sbnc-member-search').val(null).trigger('change.select2');
        $('#sbnc-filter-activity, #sbnc-filter-event, #sbnc-filter-year').val('');

        updateActiveFilters();
        loadGallery();
    }

    // --- Gallery Rendering (nanogallery2 integration) ---

    /**
     * Loads and renders the photo gallery using nanogallery2.
     * Passes current filters to the API and configures display options.
     */
    function loadGallery() {
        const $ = window.jQuery;

        // Build API URL with filter parameters
        const params = new URLSearchParams();
        if (currentFilters.member) params.set('member', currentFilters.member);
        if (currentFilters.activity) params.set('activity', currentFilters.activity);
        if (currentFilters.event) params.set('event', currentFilters.event);
        if (currentFilters.year) params.set('year', currentFilters.year);

        const url = CONFIG.apiBase + '/api/gallery.json?' + params.toString();

        // Update view mode label
        const viewModeLabels = {
            event: getConfigValue('labels.eventPhotos', 'Event Photos'),
            member: getConfigValue('labels.memberPhotos', 'Member Photos'),
            activity: getConfigValue('labels.activityEvents', 'Activity Events'),
            year: currentFilters.year ? `${currentFilters.year} Events` : null,
            default: getConfigValue('labels.browseEvents', 'Browse Events')
        };

        let viewMode = viewModeLabels.default;
        if (currentFilters.event) viewMode = viewModeLabels.event;
        else if (currentFilters.member) viewMode = viewModeLabels.member;
        else if (currentFilters.activity) viewMode = viewModeLabels.activity;
        else if (currentFilters.year) viewMode = viewModeLabels.year;

        $('#sbnc-view-mode').text(viewMode);

        // Destroy existing gallery
        try {
            $('#sbnc-gallery-content').nanogallery2('destroy');
        } catch(e) {
            // Ignore if no gallery exists
        }

        // Configure nanogallery2 options
        // See https://nanogallery2.nanostudio.org/ for all options
        const galleryOptions = {
            items: url,                    // URL to fetch gallery data from
            itemsBaseURL: '',
            thumbnailWidth: 'auto',
            thumbnailHeight: getConfigValue('gallery.thumbnailHeight', 180),
            thumbnailBorderHorizontal: 0,
            thumbnailBorderVertical: 0,
            thumbnailGutterWidth: getConfigValue('gallery.gutterWidth', 8),
            thumbnailGutterHeight: getConfigValue('gallery.gutterHeight', 8),
            thumbnailLabel: {
                display: true,
                position: 'overImageOnBottom',
                hideIcons: true
            },
            thumbnailHoverEffect2: 'imageScale150',
            galleryDisplayMode: 'rows',
            galleryMaxRows: getConfigValue('gallery.maxRows', 20),
            viewerToolbar: {
                display: true,
                standard: 'previousButton,label,nextButton'
            },
            fnGalleryRenderEnd: onGalleryRendered
        };

        // Initialize gallery
        $('#sbnc-gallery-content').nanogallery2(galleryOptions);
    }

    /**
     * Callback when gallery finishes rendering.
     * Updates results count display.
     */
    function onGalleryRendered(items) {
        const $ = window.jQuery;
        const type = currentFilters.event ? 'photos' : 'events';
        $('#sbnc-results-count').html(`<strong>${items.length}</strong> ${type}`);
    }

    /**
     * Displays an error message in the gallery area.
     */
    function showError(message) {
        const container = document.getElementById('sbnc-gallery-content');
        if (container) {
            container.innerHTML = `<div class="sbnc-error">${escapeHtml(message)}</div>`;
        }
    }


// ═══════════════════════════════════════════════════════════════════════════
// SECTION 5: PUBLIC API
// CATEGORY C: UI LAYER | ~3% of code | Dependencies: Internal functions only
// Risk: LOW | Breaks if: Function signatures change in other sections
// ═══════════════════════════════════════════════════════════════════════════
//
// Functions exposed on window.SBNCGallery for external use.
// These can be called from Wild Apricot page scripts or browser console.
//
// USAGE EXAMPLES:
//   SBNCGallery.clearFilters()           - Reset all filters
//   SBNCGallery.refresh()                - Reload gallery data
//   SBNCGallery.getFilters()             - Get current filter state
//   SBNCGallery.removeFilter('year')     - Remove a specific filter
// ═══════════════════════════════════════════════════════════════════════════

    /**
     * Public API for external interaction with the gallery.
     * @namespace SBNCGallery
     */
    window.SBNCGallery = {
        /** Initialize the gallery (called automatically) */
        init: init,

        /** Apply current filter values and refresh */
        applyFilters: applyFilters,

        /** Clear all filters */
        clearFilters: clearFilters,

        /** Remove a specific filter ('member', 'activity', 'event', 'year') */
        removeFilter: removeFilter,

        /** Refresh gallery with current filters */
        refresh: loadGallery,

        /** Get current configuration (for debugging) */
        getConfig: () => ({ ...CONFIG, remote: remoteConfig }),

        /** Get current filter state */
        getFilters: () => ({ ...currentFilters })
    };


// ═══════════════════════════════════════════════════════════════════════════
// SECTION 6: INITIALIZATION
// CATEGORY C: UI LAYER | ~3% of code | Dependencies: All previous sections
// Risk: LOW | Breaks if: Container element missing, script load order wrong
// ═══════════════════════════════════════════════════════════════════════════
//
// Main entry point that orchestrates setup.
// Auto-runs when DOM is ready.

    /**
     * Main initialization function.
     * 1. Injects CSS
     * 2. Loads external libraries
     * 3. Loads remote config
     * 4. Builds widget HTML
     * 5. Loads data
     * 6. Initializes gallery
     */
    function init() {
        injectStyles();

        loadDependencies(async function() {
            // Load remote config (optional)
            await loadRemoteConfig();

            // Build widget HTML
            if (!buildWidget()) {
                return;
            }

            try {
                // Load data and initialize
                await loadData();

                if (CONFIG.showFilters) {
                    populateFilters();
                }

                loadGallery();

            } catch (error) {
                showError('Failed to load gallery. Please try again later.');
            }
        });
    }

    // Auto-initialize when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

/* ╔═══════════════════════════════════════════════════════════════════════════╗
   ║                                                                           ║
   ║                         SBNC SHIM - END                                   ║
   ║                                                                           ║
   ╚═══════════════════════════════════════════════════════════════════════════╝ */

})();
