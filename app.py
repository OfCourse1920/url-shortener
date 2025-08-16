import os
import string
import random
import logging
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, flash, url_for, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import desc, func
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///urls.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

def generate_short_code(length=6):
    """Generate a unique alphanumeric short code."""
    characters = string.ascii_letters + string.digits
    
    while True:
        short_code = ''.join(random.choice(characters) for _ in range(length))
        # Import here to avoid circular import
        from models import Urls
        # Check if the code already exists in the database
        existing = Urls.query.filter_by(short_code=short_code).first()
        if not existing:
            return short_code

def validate_url(url):
    """Validate URL format and accessibility."""
    if not url:
        return False, "URL cannot be empty"
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic URL validation
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format"
        
        # Check for malicious patterns
        malicious_patterns = ['javascript:', 'data:', 'file:', 'ftp:']
        if any(pattern in url.lower() for pattern in malicious_patterns):
            return False, "URL scheme not allowed"
            
        return True, url
    except Exception:
        return False, "Invalid URL format"

def is_valid_custom_alias(alias):
    """Validate custom alias format."""
    if not alias:
        return True  # Optional field
    
    # Check length
    if len(alias) < 3 or len(alias) > 50:
        return False
    
    # Check format (alphanumeric, hyphens, underscores only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', alias):
        return False
    
    return True

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route for the URL shortener homepage."""
    if request.method == 'POST':
        long_url = request.form.get('long_url', '').strip()
        custom_alias = request.form.get('custom_alias', '').strip()
        description = request.form.get('description', '').strip()
        expires_in = request.form.get('expires_in', '')
        
        # Validate URL
        is_valid, validated_url_or_error = validate_url(long_url)
        if not is_valid:
            flash(validated_url_or_error, 'error')
            return redirect(url_for('index'))
        
        long_url = validated_url_or_error
        
        # Validate custom alias
        if custom_alias and not is_valid_custom_alias(custom_alias):
            flash('Custom alias must be 3-50 characters and contain only letters, numbers, hyphens, and underscores.', 'error')
            return redirect(url_for('index'))
        
        # Import here to avoid circular import
        from models import Urls
        
        # Check if custom alias already exists
        if custom_alias:
            existing_alias = Urls.query.filter_by(custom_alias=custom_alias).first()
            if existing_alias:
                flash('Custom alias already exists. Please choose a different one.', 'error')
                return redirect(url_for('index'))
        
        # Check if URL already exists in database (deduplication)
        existing_url = Urls.query.filter_by(long_url=long_url).first()
        if existing_url and existing_url.is_active and not existing_url.is_expired:
            short_identifier = existing_url.custom_alias or existing_url.short_code
            short_url = request.url_root + short_identifier
            flash('This URL has already been shortened!', 'info')
            return render_template('index.html', short_url=short_url, long_url=long_url)
        
        # Calculate expiration date
        expires_at = None
        if expires_in:
            try:
                expires_in_days = int(expires_in)
                if expires_in_days > 0:
                    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            except ValueError:
                flash('Invalid expiration period.', 'error')
                return redirect(url_for('index'))
        
        # Generate new short code
        short_code = custom_alias or generate_short_code()
        
        # Create new URL entry
        new_url = Urls()
        new_url.long_url = long_url
        new_url.short_code = short_code
        new_url.custom_alias = custom_alias if custom_alias else None
        new_url.description = description if description else None
        new_url.expires_at = expires_at
        
        try:
            db.session.add(new_url)
            db.session.commit()
            short_identifier = custom_alias or short_code
            short_url = request.url_root + short_identifier
            flash('URL shortened successfully!', 'success')
            return render_template('index.html', short_url=short_url, long_url=long_url, 
                                 url_entry=new_url)
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while shortening the URL. Please try again.', 'error')
            app.logger.error(f"Error saving URL: {e}")
            return redirect(url_for('index'))
    
    return render_template('index.html')

@app.route('/<identifier>')
def redirect_to_url(identifier):
    """Redirect short code or custom alias to the original long URL with analytics tracking."""
    from models import Urls, UrlClick
    
    # Try to find by short_code or custom_alias
    url_entry = Urls.query.filter(
        (Urls.short_code == identifier) | (Urls.custom_alias == identifier)
    ).first()
    
    if not url_entry:
        abort(404)
    
    # Check if URL is active and not expired
    if not url_entry.is_active:
        flash('This short URL has been deactivated.', 'error')
        return redirect(url_for('index'))
    
    if url_entry.is_expired:
        flash('This short URL has expired.', 'error')
        return redirect(url_for('index'))
    
    # Record analytics
    try:
        click = UrlClick()
        click.url_id = url_entry.id
        click.ip_address = request.environ.get('REMOTE_ADDR')
        click.user_agent = request.environ.get('HTTP_USER_AGENT', '')[:500]
        click.referer = request.environ.get('HTTP_REFERER', '')[:500]
        
        db.session.add(click)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error recording click analytics: {e}")
    
    return redirect(url_entry.long_url, code=301)

@app.route('/analytics')
def analytics_dashboard():
    """Analytics dashboard showing URL statistics."""
    from models import Urls, UrlClick
    
    # Get recent URLs with click counts
    recent_urls = db.session.query(Urls).order_by(desc(Urls.created_at)).limit(10).all()
    
    # Get popular URLs by click count
    popular_urls = db.session.query(
        Urls, func.count(UrlClick.id).label('click_count')
    ).outerjoin(UrlClick).group_by(Urls.id).order_by(
        desc(func.count(UrlClick.id))
    ).limit(10).all()
    
    # Get total statistics
    total_urls = Urls.query.count()
    total_clicks = UrlClick.query.count()
    active_urls = Urls.query.filter_by(is_active=True).count()
    
    # Get click data for charts (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_clicks = db.session.query(
        func.date(UrlClick.clicked_at).label('date'),
        func.count(UrlClick.id).label('clicks')
    ).filter(UrlClick.clicked_at >= seven_days_ago).group_by(
        func.date(UrlClick.clicked_at)
    ).order_by(func.date(UrlClick.clicked_at)).all()
    
    return render_template('analytics.html', 
                         recent_urls=recent_urls,
                         popular_urls=popular_urls,
                         total_urls=total_urls,
                         total_clicks=total_clicks,
                         active_urls=active_urls,
                         daily_clicks=daily_clicks)

@app.route('/manage')
def manage_urls():
    """URL management dashboard."""
    from models import Urls
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    
    query = Urls.query
    if search:
        query = query.filter(
            (Urls.long_url.contains(search)) |
            (Urls.short_code.contains(search)) |
            (Urls.custom_alias.contains(search)) |
            (Urls.description.contains(search))
        )
    
    urls = query.order_by(desc(Urls.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('manage.html', urls=urls, search=search)

@app.route('/url/<int:url_id>/analytics')
def url_analytics(url_id):
    """Detailed analytics for a specific URL."""
    from models import Urls, UrlClick
    
    url_entry = Urls.query.get_or_404(url_id)
    
    # Get click history
    clicks = UrlClick.query.filter_by(url_id=url_id).order_by(desc(UrlClick.clicked_at)).limit(100).all()
    
    # Get click statistics
    total_clicks = UrlClick.query.filter_by(url_id=url_id).count()
    
    # Daily click data for last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_clicks = db.session.query(
        func.date(UrlClick.clicked_at).label('date'),
        func.count(UrlClick.id).label('clicks')
    ).filter(
        UrlClick.url_id == url_id,
        UrlClick.clicked_at >= thirty_days_ago
    ).group_by(func.date(UrlClick.clicked_at)).order_by(func.date(UrlClick.clicked_at)).all()
    
    return render_template('url_analytics.html',
                         url_entry=url_entry,
                         clicks=clicks,
                         total_clicks=total_clicks,
                         daily_clicks=daily_clicks)

@app.route('/url/<int:url_id>/toggle', methods=['POST'])
def toggle_url_status(url_id):
    """Toggle URL active status."""
    from models import Urls
    
    url_entry = Urls.query.get_or_404(url_id)
    url_entry.is_active = not url_entry.is_active
    
    try:
        db.session.commit()
        status = 'activated' if url_entry.is_active else 'deactivated'
        flash(f'URL {status} successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating URL status.', 'error')
        app.logger.error(f"Error toggling URL status: {e}")
    
    return redirect(url_for('manage_urls'))

@app.route('/url/<int:url_id>/delete', methods=['POST'])
def delete_url(url_id):
    """Delete a URL and all its analytics."""
    from models import Urls
    
    url_entry = Urls.query.get_or_404(url_id)
    
    try:
        db.session.delete(url_entry)
        db.session.commit()
        flash('URL deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting URL.', 'error')
        app.logger.error(f"Error deleting URL: {e}")
    
    return redirect(url_for('manage_urls'))

# API Routes
@app.route('/api/shorten', methods=['POST'])
def api_shorten():
    """API endpoint for URL shortening."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        long_url = data.get('url', '').strip()
        custom_alias = data.get('alias', '').strip()
        description = data.get('description', '').strip()
        expires_in = data.get('expires_in')
        
        # Validate URL
        is_valid, validated_url_or_error = validate_url(long_url)
        if not is_valid:
            return jsonify({'error': validated_url_or_error}), 400
        
        long_url = validated_url_or_error
        
        # Validate custom alias
        if custom_alias and not is_valid_custom_alias(custom_alias):
            return jsonify({'error': 'Invalid custom alias format'}), 400
        
        from models import Urls
        
        # Check if custom alias already exists
        if custom_alias:
            existing_alias = Urls.query.filter_by(custom_alias=custom_alias).first()
            if existing_alias:
                return jsonify({'error': 'Custom alias already exists'}), 400
        
        # Check for existing URL
        existing_url = Urls.query.filter_by(long_url=long_url).first()
        if existing_url and existing_url.is_active and not existing_url.is_expired:
            short_identifier = existing_url.custom_alias or existing_url.short_code
            return jsonify({
                'short_url': request.url_root + short_identifier,
                'long_url': long_url,
                'existing': True
            })
        
        # Calculate expiration
        expires_at = None
        if expires_in:
            try:
                expires_in_days = int(expires_in)
                if expires_in_days > 0:
                    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            except ValueError:
                return jsonify({'error': 'Invalid expiration period'}), 400
        
        # Create new URL
        short_code = custom_alias or generate_short_code()
        new_url = Urls()
        new_url.long_url = long_url
        new_url.short_code = short_code
        new_url.custom_alias = custom_alias if custom_alias else None
        new_url.description = description if description else None
        new_url.expires_at = expires_at
        
        db.session.add(new_url)
        db.session.commit()
        
        short_identifier = custom_alias or short_code
        return jsonify({
            'short_url': request.url_root + short_identifier,
            'long_url': long_url,
            'created_at': new_url.created_at.isoformat(),
            'expires_at': new_url.expires_at.isoformat() if new_url.expires_at else None,
            'existing': False
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stats/<identifier>')
def api_stats(identifier):
    """API endpoint for URL statistics."""
    from models import Urls, UrlClick
    
    url_entry = Urls.query.filter(
        (Urls.short_code == identifier) | (Urls.custom_alias == identifier)
    ).first()
    
    if not url_entry:
        return jsonify({'error': 'URL not found'}), 404
    
    click_count = UrlClick.query.filter_by(url_id=url_entry.id).count()
    
    return jsonify({
        'short_code': url_entry.short_code,
        'custom_alias': url_entry.custom_alias,
        'long_url': url_entry.long_url,
        'description': url_entry.description,
        'click_count': click_count,
        'created_at': url_entry.created_at.isoformat(),
        'is_active': url_entry.is_active,
        'expires_at': url_entry.expires_at.isoformat() if url_entry.expires_at else None,
        'is_expired': url_entry.is_expired
    })

@app.errorhandler(404)
def not_found_error(error):
    """Custom 404 error handler."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 error handler."""
    db.session.rollback()
    return render_template('500.html'), 500

@app.shell_context_processor
def make_shell_context():
    """Make database and models available in flask shell."""
    from models import Urls, UrlClick
    return {'db': db, 'Urls': Urls, 'UrlClick': UrlClick}

# Initialize database tables
with app.app_context():
    # Import models to ensure they're registered
    import models  # noqa: F401
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
