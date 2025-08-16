from app import db
from datetime import datetime, timezone

class Urls(db.Model):
    """Database model for storing URL mappings."""
    __tablename__ = 'urls'
    
    id = db.Column(db.Integer, primary_key=True)
    long_url = db.Column(db.String(2048), nullable=False)
    short_code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    custom_alias = db.Column(db.String(50), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(255), nullable=True)
    
    # Analytics relationship
    clicks = db.relationship('UrlClick', backref='url', lazy=True, cascade='all, delete-orphan')
    
    @property
    def click_count(self):
        return db.session.query(UrlClick).filter_by(url_id=self.id).count()
    
    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def __repr__(self):
        return f'<Urls {self.short_code}: {self.long_url}>'

class UrlClick(db.Model):
    """Database model for tracking URL clicks and analytics."""
    __tablename__ = 'url_clicks'
    
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('urls.id'), nullable=False)
    clicked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 support
    user_agent = db.Column(db.String(500), nullable=True)
    referer = db.Column(db.String(500), nullable=True)
    
    def __repr__(self):
        return f'<UrlClick {self.id}: {self.url_id} at {self.clicked_at}>'
