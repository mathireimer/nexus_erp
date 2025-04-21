from app import app, db

with app.app_context():
    # Create all database tables
    db.drop_all()  # Drop all existing tables
    db.create_all()  # Create all tables
    print("Database tables created successfully!") 