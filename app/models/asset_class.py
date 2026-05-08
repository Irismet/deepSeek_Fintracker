# app/models/asset_class.py
from app import db
from datetime import datetime

class AssetClass(db.Model):
    __tablename__ = 'asset_classes'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    risk_level = db.Column(db.Integer, nullable=True)  # 1-10, где 10 - максимальный риск
    parent_id = db.Column(db.BigInteger, db.ForeignKey('asset_classes.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for hierarchy
    children = db.relationship('AssetClass', backref=db.backref('parent', remote_side=[id]))
    
    # Relationships with assets
    assets = db.relationship('Asset', backref='asset_class', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'risk_level': self.risk_level,
            'parent_id': self.parent_id
        }
    
    def __repr__(self):
        return f'<AssetClass {self.name}>'