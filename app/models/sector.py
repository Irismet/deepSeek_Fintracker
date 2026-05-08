# app/models/sector.py
from app.extensions import db
from datetime import datetime

class Sector(db.Model):
    __tablename__ = 'sectors'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    gics_code = db.Column(db.String(10), nullable=True)  # GICS код сектора
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with assets
    assets = db.relationship('Asset', backref='sector', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'gics_code': self.gics_code
        }
    
    def __repr__(self):
        return f'<Sector {self.name}>'