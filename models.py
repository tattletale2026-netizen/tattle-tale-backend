from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    full_name = db.Column(db.String(200))
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    workshop = db.Column(db.String(255))
    event_date = db.Column(db.String(100))
    event_time = db.Column(db.String(100))
    seats = db.Column(db.String(20))
    venue_link = db.Column(db.Text)
    message = db.Column(db.Text)
    raw_data = db.Column(db.JSON)
    status = db.Column(db.String(50), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SurveyResponse(db.Model):
    __tablename__ = 'survey_responses'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255))
    name = db.Column(db.String(255))
    answers = db.Column(db.JSON)
    raw_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    rating = db.Column(db.String(50))
    message = db.Column(db.Text)
    feedback_text = db.Column(db.Text)
    raw_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    subject = db.Column(db.String(255))
    message = db.Column(db.Text, nullable=False)
    raw_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
