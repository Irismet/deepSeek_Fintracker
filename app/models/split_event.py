# app/models/split_event.py
from app.extensions import db
from datetime import datetime

class SplitEvent(db.Model):
    """Модель для учета сплитов и обратных сплитов"""
    __tablename__ = 'split_events'
    
    id = db.Column(db.BigInteger, primary_key=True)
    asset_id = db.Column(db.BigInteger, db.ForeignKey('assets.id'), nullable=False, index=True)
    split_type = db.Column(db.String(30), nullable=False)  # split, reverse_split
    old_quantity = db.Column(db.Numeric(10, 4), nullable=False)  # старое количество
    new_quantity = db.Column(db.Numeric(10, 4), nullable=False)  # новое количество
    ratio = db.Column(db.Numeric(10, 6), nullable=False)  # коэффициент (new/old)
    split_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_split_asset', 'asset_id'),
        db.Index('idx_split_date', 'split_date'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'split_type': self.split_type,
            'old_quantity': float(self.old_quantity),
            'new_quantity': float(self.new_quantity),
            'ratio': float(self.ratio),
            'split_date': self.split_date.isoformat()
        }