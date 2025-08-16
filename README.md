# Flask URL Shortener - Full Featured Edition

A complete, professional-grade URL shortener web application built with Python and Flask. This application provides comprehensive URL management with advanced analytics, custom aliases, expiration controls, and a full administrative dashboard.

## Core Features

### URL Shortening & Management
- **Smart URL Shortening**: Convert long URLs into short, memorable 6-character alphanumeric codes
- **Custom Aliases**: Create personalized short URLs with custom keywords (3-50 characters)
- **URL Validation**: Advanced URL validation with malicious pattern detection
- **Automatic Deduplication**: Returns existing short URL if the long URL has already been shortened
- **Expiration Control**: Set expiration dates for URLs (1 day to 1 year or never expires)
- **URL Descriptions**: Add descriptions to help organize and remember your links
- **Bulk Management**: Search, filter, activate/deactivate, and delete URLs in bulk

### Analytics & Insights
- **Comprehensive Analytics Dashboard**: Overview of all URL statistics and performance
- **Individual URL Analytics**: Detailed statistics for each shortened URL
- **Click Tracking**: Real-time tracking of all clicks with visitor information
- **Interactive Charts**: Visual representation of click patterns over time
- **Visitor Details**: IP addresses, user agents, and referrer information
- **Performance Metrics**: Average clicks per URL, most popular links, recent activity

### Advanced Features
- **URL Status Management**: Activate/deactivate URLs without deletion
- **Search & Filter**: Advanced search across URLs, descriptions, and codes
- **Pagination**: Efficient handling of large URL collections
- **RESTful API**: JSON API endpoints for programmatic access
- **Error Handling**: Custom 404/500 pages with user-friendly messages
- **Responsive Design**: Bootstrap-powered dark theme optimized for all devices

### Security & Reliability
- **URL Validation**: Prevents malicious URLs (javascript:, data:, file: schemes)
- **Database Integrity**: PostgreSQL support with proper foreign key constraints
- **Session Management**: Secure session handling with environment-based secrets
- **Error Recovery**: Comprehensive error handling with automatic rollback

## Application Structure

```
flask_url_shortener/
├── app.py                 # Main Flask application with routes and logic
├── models.py              # Database models (Urls, UrlClick)
├── main.py                # Application entry point
├── templates/             # Jinja2 templates
│   ├── base.html         # Base template with Bootstrap styling
│   ├── index.html        # Homepage with URL shortening form
│   ├── analytics.html    # Analytics dashboard
│   ├── manage.html       # URL management interface
│   ├── url_analytics.html # Individual URL analytics
│   ├── 404.html          # Custom 404 error page
│   └── 500.html          # Custom 500 error page
├── README.md             # Project documentation
└── pyproject.toml        # Python dependencies

```

## API Documentation

### POST /api/shorten
Create a new short URL.

**Request Body:**
```json
{
  "url": "https://example.com/very-long-url",
  "alias": "my-custom-link",  // Optional custom alias
  "description": "My important link",  // Optional description
  "expires_in": 30  // Optional expiration in days
}
```

**Response:**
```json
{
  "short_url": "https://yoursite.com/abc123",
  "long_url": "https://example.com/very-long-url",
  "created_at": "2024-01-01T12:00:00Z",
  "expires_at": "2024-01-31T12:00:00Z",
  "existing": false
}
```

### GET /api/stats/{identifier}
Get statistics for a short URL.

**Response:**
```json
{
  "short_code": "abc123",
  "custom_alias": "my-custom-link",
  "long_url": "https://example.com/very-long-url",
  "description": "My important link",
  "click_count": 42,
  "created_at": "2024-01-01T12:00:00Z",
  "is_active": true,
  "expires_at": "2024-01-31T12:00:00Z",
  "is_expired": false
}
```

## Navigation

- **Homepage (/)**: Create new short URLs with advanced options
- **Analytics (/analytics)**: View comprehensive dashboard with charts and statistics
- **Manage URLs (/manage)**: Search, filter, and manage all your URLs
- **Individual Analytics (/url/{id}/analytics)**: Detailed analytics for specific URLs
- **API Endpoints**: RESTful API for programmatic access

## Prerequisites

- Python 3.11 or higher
- PostgreSQL database (auto-configured in Replit)
- Modern web browser with JavaScript enabled

## Setup Instructions

### 1. Environment Setup
The application automatically configures itself in the Replit environment with:
- PostgreSQL database connection
- Session secrets
- Proper networking configuration
